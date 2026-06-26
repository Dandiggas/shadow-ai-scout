from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from scout.errors import ScoutAPIError, provider_key_error
from scout.extraction import classify_source_type, discard_claims_without_quotes
from scout.models import EvidenceClaim, ScanResult, SourceRecord, ToolVerdict
from scout.policy import default_requirements
from scout.report import render_markdown_report
from scout.scorer import score_tool
from scout.pipeline import render_clickhouse_inserts

REQUIRED_SOURCE_TYPES = {"privacy", "security", "terms", "pricing", "docs", "news"}
RISK_CATEGORIES = [
    "Data collected",
    "Data retention",
    "Training on customer data",
    "Third-party subprocessors",
    "SSO/SAML",
    "SOC2 / ISO27001",
    "GDPR / DPA",
    "Admin controls",
    "Audit logs",
    "Local device access",
    "Browser access",
    "Source code exposure",
    "Meeting transcript exposure",
    "Customer data exposure",
    "Deletion/export controls",
    "Breach/news history",
]


@dataclass
class AgentStep:
    iteration: int
    tool_name: str
    thought: str
    action: str
    observation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "tool_name": self.tool_name,
            "thought": self.thought,
            "action": self.action,
            "observation": self.observation,
        }


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class TavilySearcher:
    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.client = client or httpx.Client(timeout=25, follow_redirects=True)

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if not self.api_key:
            raise RuntimeError("TAVILY_API_KEY is required for live agentic scans")
        response = self.client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
            },
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if response.status_code in {400, 401, 403}:
                raise provider_key_error("Tavily", response.status_code, f"{response.url}: {response.text}") from exc
            raise ScoutAPIError("Tavily", "Tavily search failed. Try again or reduce scan scope.", f"HTTP {response.status_code}: {response.text[:300]}") from exc
        payload = response.json()
        return [
            SearchResult(
                title=item.get("title") or item.get("url", ""),
                url=item.get("url", ""),
                snippet=item.get("content") or item.get("snippet") or "",
            )
            for item in payload.get("results", [])
            if item.get("url")
        ]


class PageFetcher:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "ShadowAIScout/0.1 security-review-bot"})

    def fetch_text(self, url: str) -> str:
        response = self.client.get(url)
        response.raise_for_status()
        text = response.text
        text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:18000]


class GeminiExtractor:
    def __init__(self, api_key: str | None = None, model: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.client = client or httpx.Client(timeout=45)

    def extract(self, tool_name: str, source_url: str, source_type: str, page_text: str, company_context: str) -> list[EvidenceClaim]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is required for live extraction")
        prompt = self._prompt(tool_name, source_url, source_type, page_text, company_context)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        response = self.client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if response.status_code in {400, 401, 403}:
                raise provider_key_error("Gemini", response.status_code, f"{response.url}: {response.text}") from exc
            if response.status_code == 429:
                raise ScoutAPIError(
                    "Gemini",
                    "Gemini quota is exhausted for this key. Check Google AI Studio quota/billing or use another GEMINI_API_KEY.",
                    f"HTTP 429: {response.text[:300]}",
                ) from exc
            raise ScoutAPIError("Gemini", "Gemini extraction failed. Try again or reduce fetched page size.", f"HTTP {response.status_code}: {response.text[:300]}") from exc
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        claims_payload = _parse_json_array(text)
        claims: list[EvidenceClaim] = []
        for item in claims_payload:
            quote = str(item.get("evidence_quote", "")).strip()
            if not quote:
                continue
            if quote.lower() not in page_text.lower():
                # Verification gate: no quote in source, no claim.
                continue
            category = str(item.get("risk_category", "Data collected"))
            if category not in RISK_CATEGORIES:
                category = "Data collected"
            claims.append(
                EvidenceClaim(
                    tool_name=tool_name,
                    source_url=source_url,
                    source_type=source_type,
                    risk_category=category,
                    claim_text=str(item.get("claim_text", "")).strip()[:500],
                    evidence_quote=quote[:500],
                    severity=max(0, min(5, int(item.get("severity", 2)))),
                    confidence=max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                )
            )
        return claims

    def _prompt(self, tool_name: str, source_url: str, source_type: str, page_text: str, company_context: str) -> str:
        cats = ", ".join(RISK_CATEGORIES)
        return f"""
You are the extraction step inside Shadow AI Scout, an autonomous security due-diligence agent.

Company context:
{company_context}

Tool under review: {tool_name}
Source URL: {source_url}
Source type: {source_type}

Extract only security/procurement risk or control claims that are directly supported by the page text.
Return ONLY a JSON array. No prose. Each item must have:
- risk_category: one of [{cats}]
- claim_text: concise normalized claim
- evidence_quote: exact short quote copied from the page text
- severity: integer 0-5 where 5 is highest risk
- confidence: float 0-1

If the page has no useful claims, return [].

Page text:
{page_text[:14000]}
""".strip()


def _parse_json_array(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _source_record(tool_name: str, result: SearchResult, page_text: str) -> SourceRecord:
    snippet = page_text[:240] if page_text else result.snippet[:240]
    return SourceRecord(
        tool_name=tool_name,
        source_url=result.url,
        source_title=result.title[:160],
        source_type=classify_source_type(result.url),
        content_hash=hashlib.sha256(page_text.encode("utf-8", errors="ignore")).hexdigest(),
        snippet=snippet,
    )


class AgenticScanner:
    """Plan-act-observe scanner: searches, reads, extracts, verifies, gap-checks, repeats."""

    def __init__(self, searcher: TavilySearcher | None = None, fetcher: PageFetcher | None = None, extractor: GeminiExtractor | None = None):
        load_dotenv()
        self.searcher = searcher or TavilySearcher()
        self.fetcher = fetcher or PageFetcher()
        self.extractor = extractor or GeminiExtractor()
        self.trace: list[AgentStep] = []

    def scan(self, tools: list[str], company_context: str, output_dir: Path, max_iterations: int = 3) -> ScanResult:
        run_id = str(uuid4())
        output_dir.mkdir(parents=True, exist_ok=True)
        all_sources: list[SourceRecord] = []
        all_claims: list[EvidenceClaim] = []
        seen_urls: set[str] = set()

        for tool_name in tools:
            wanted = set(REQUIRED_SOURCE_TYPES)
            for iteration in range(1, max_iterations + 1):
                queries = self._plan_queries(tool_name, wanted, iteration)
                self.trace.append(AgentStep(iteration, tool_name, f"Need evidence types: {sorted(wanted)}", "plan_queries", "; ".join(queries)))
                discovered: list[SearchResult] = []
                for query in queries:
                    results = self.searcher.search(query, max_results=4)
                    discovered.extend(results)
                    self.trace.append(AgentStep(iteration, tool_name, f"Search web for {query}", "tavily_search", f"{len(results)} results"))

                for result in self._rank_results(discovered):
                    if result.url in seen_urls:
                        continue
                    seen_urls.add(result.url)
                    try:
                        page_text = self.fetcher.fetch_text(result.url)
                    except Exception as exc:  # network pages fail; trace and continue
                        self.trace.append(AgentStep(iteration, tool_name, "Fetch candidate source", "fetch_page", f"failed {result.url}: {exc}"))
                        continue
                    source = _source_record(tool_name, result, page_text)
                    all_sources.append(source)
                    self.trace.append(AgentStep(iteration, tool_name, f"Read {source.source_type} source", "fetch_page", result.url))
                    try:
                        claims = self.extractor.extract(tool_name, result.url, source.source_type, page_text, company_context)
                    except ScoutAPIError:
                        raise
                    except Exception as exc:
                        self.trace.append(AgentStep(iteration, tool_name, "Extract risk claims", "gemini_extract", f"failed {result.url}: {exc}"))
                        continue
                    verified = discard_claims_without_quotes(claims)
                    all_claims.extend(verified)
                    self.trace.append(AgentStep(iteration, tool_name, "Verify claim quotes exist in source", "extract_and_verify", f"{len(verified)} claims from {result.url}"))

                observed_types = {s.source_type for s in all_sources if s.tool_name.lower() == tool_name.lower()}
                wanted = REQUIRED_SOURCE_TYPES - observed_types
                if not wanted:
                    self.trace.append(AgentStep(iteration, tool_name, "All required source types observed", "stop", "coverage complete"))
                    break
                self.trace.append(AgentStep(iteration, tool_name, "Coverage gaps remain", "continue", f"missing {sorted(wanted)}"))

        requirements = default_requirements()
        verdicts = [score_tool(tool_name, requirements, all_claims) for tool_name in tools]
        evidence_path = output_dir / "evidence.json"
        report_path = output_dir / "cited.md"
        sql_path = output_dir / "clickhouse_inserts.sql"
        trace_path = output_dir / "agent_trace.json"
        payload = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "company_context": company_context,
            "agent_trace": [s.as_dict() for s in self.trace],
            "sources": [s.model_dump(mode="json") for s in all_sources],
            "claims": [c.model_dump(mode="json") for c in all_claims],
            "verdicts": [v.model_dump(mode="json") for v in verdicts],
            "requirements": [r.model_dump(mode="json") for r in requirements],
        }
        evidence_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        trace_path.write_text(json.dumps(payload["agent_trace"], indent=2), encoding="utf-8")
        report_path.write_text(render_markdown_report(company_context, verdicts), encoding="utf-8")
        sql_path.write_text(render_clickhouse_inserts(run_id, company_context, tools, all_sources, all_claims, verdicts), encoding="utf-8")
        return ScanResult(run_id=run_id, verdicts=verdicts, claims=all_claims, sources=all_sources, evidence_json=evidence_path, markdown_report=report_path, clickhouse_sql=sql_path)

    def _plan_queries(self, tool_name: str, wanted: set[str], iteration: int) -> list[str]:
        base = f'"{tool_name}" AI tool'
        query_by_type = {
            "privacy": f'{base} privacy policy data retention training customer data',
            "security": f'{base} security trust SOC 2 SSO SAML admin controls',
            "terms": f'{base} terms of service data processing agreement DPA',
            "pricing": f'{base} pricing enterprise SSO admin audit logs',
            "docs": f'{base} docs security settings data controls',
            "news": f'{base} breach incident security review privacy concerns',
        }
        if iteration == 1:
            return [query_by_type[k] for k in ["privacy", "security", "terms"]]
        return [query_by_type[k] for k in sorted(wanted)[:4]]

    def _rank_results(self, results: list[SearchResult]) -> list[SearchResult]:
        dedup: dict[str, SearchResult] = {}
        for result in results:
            dedup.setdefault(result.url, result)

        def score(result: SearchResult) -> tuple[int, int]:
            url = result.url.lower()
            source_type = classify_source_type(url)
            official_bonus = 2 if _domain(result.url).split(".")[-2:] else 0
            type_bonus = 4 if source_type in REQUIRED_SOURCE_TYPES else 0
            return (type_bonus + official_bonus, len(result.snippet))

        return sorted(dedup.values(), key=score, reverse=True)[:10]


def run_agentic_scan(tools: list[str], company_context: str, output_dir: Path, max_iterations: int = 3) -> ScanResult:
    return AgenticScanner().scan(tools, company_context, output_dir, max_iterations=max_iterations)
