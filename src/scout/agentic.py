from __future__ import annotations

import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse
from uuid import uuid4

# Optional progress reporter: receives (event, message) e.g. ("search", "...").
ProgressFn = Optional[Callable[[str, str], None]]

import httpx
from dotenv import load_dotenv

from scout.errors import ScoutAPIError, provider_key_error
from scout.extraction import classify_source_type, discard_claims_without_quotes
from scout.models import EvidenceClaim, ScanResult, SourceRecord, SourceRelation, ToolVerdict
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


def _claims_from_payload(claims_payload: list[dict[str, Any]], tool_name: str, source_url: str, source_type: str, page_text: str) -> list[EvidenceClaim]:
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


class GeminiExtractor:
    def __init__(self, api_key: str | None = None, model: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-flash-latest")
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
        return _claims_from_payload(claims_payload, tool_name, source_url, source_type, page_text)

    def _prompt(self, tool_name: str, source_url: str, source_type: str, page_text: str, company_context: str) -> str:
        return _extraction_prompt(tool_name, source_url, source_type, page_text, company_context)


class AnthropicExtractor:
    def __init__(self, api_key: str | None = None, model: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
        self.max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "2048"))
        self.client = client or httpx.Client(timeout=45)

    def extract(self, tool_name: str, source_url: str, source_type: str, page_text: str, company_context: str) -> list[EvidenceClaim]:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for live extraction")
        prompt = self._prompt(tool_name, source_url, source_type, page_text, company_context)
        response = self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if response.status_code in {400, 401, 403}:
                raise provider_key_error("Anthropic", response.status_code, f"{response.url}: {response.text}") from exc
            if response.status_code == 429:
                raise ScoutAPIError(
                    "Anthropic",
                    "Anthropic rate limit/quota reached for this key. Check usage limits/billing at https://console.anthropic.com/ or use another ANTHROPIC_API_KEY.",
                    f"HTTP 429: {response.text[:300]}",
                ) from exc
            raise ScoutAPIError("Anthropic", "Anthropic extraction failed. Try again or reduce fetched page size.", f"HTTP {response.status_code}: {response.text[:300]}") from exc
        data = response.json()
        parts = data.get("content", [])
        text = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        claims_payload = _parse_json_array(text)
        return _claims_from_payload(claims_payload, tool_name, source_url, source_type, page_text)

    def _prompt(self, tool_name: str, source_url: str, source_type: str, page_text: str, company_context: str) -> str:
        return _extraction_prompt(tool_name, source_url, source_type, page_text, company_context)


def build_extractor():
    """Select the extraction LLM provider from env.

    LLM_PROVIDER=anthropic|gemini forces a provider. When unset, Anthropic is
    used if ANTHROPIC_API_KEY is present, otherwise Gemini.
    """
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if not provider:
        provider = "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "gemini"
    if provider == "anthropic":
        return AnthropicExtractor()
    if provider == "gemini":
        return GeminiExtractor()
    raise ScoutAPIError(
        provider or "LLM",
        "Unsupported LLM_PROVIDER. Set LLM_PROVIDER=anthropic or LLM_PROVIDER=gemini in .env.",
        f"LLM_PROVIDER={provider}",
    )


def _extraction_prompt(tool_name: str, source_url: str, source_type: str, page_text: str, company_context: str) -> str:
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


def _tool_tokens(tool_name: str) -> list[str]:
    stopwords = {"ai", "app", "tool", "the", "inc", "ltd", "io"}
    tokens = [token for token in re.findall(r"[a-z0-9]+", tool_name.lower()) if len(token) >= 3 and token not in stopwords]
    return tokens or [tool_name.lower().replace(" ", "")]


def classify_source_relation(tool_name: str, result: SearchResult) -> SourceRelation:
    """Classify whether a search result is usable for the reviewed vendor."""
    domain = _domain(result.url)
    haystack = f"{result.title} {result.url} {result.snippet}".lower()
    tokens = _tool_tokens(tool_name)
    if any(token in domain for token in tokens):
        return "official"
    if any(token in haystack for token in tokens):
        return "third_party"
    return "unrelated"


def _source_record(tool_name: str, result: SearchResult, page_text: str, source_relation: SourceRelation = "unknown") -> SourceRecord:
    snippet = page_text[:240] if page_text else result.snippet[:240]
    return SourceRecord(
        tool_name=tool_name,
        source_url=result.url,
        source_title=result.title[:160],
        source_type=classify_source_type(result.url),
        source_relation=source_relation,
        content_hash=hashlib.sha256(page_text.encode("utf-8", errors="ignore")).hexdigest(),
        snippet=snippet,
    )


class AgenticScanner:
    """Plan-act-observe scanner: searches, reads, extracts, verifies, gap-checks, repeats."""

    def __init__(self, searcher: TavilySearcher | None = None, fetcher: PageFetcher | None = None, extractor=None, max_workers: int = 5):
        load_dotenv()
        self.searcher = searcher or TavilySearcher()
        self.fetcher = fetcher or PageFetcher()
        self.extractor = extractor or build_extractor()
        self.max_workers = max(1, max_workers)
        self.trace: list[AgentStep] = []
        self._progress: ProgressFn = None

    def _emit(self, event: str, message: str) -> None:
        if self._progress is not None:
            try:
                self._progress(event, message)
            except Exception:
                pass  # progress reporting must never break a scan

    def _process_source(self, tool_name: str, company_context: str, iteration: int, result: SearchResult, source_relation: SourceRelation):
        """Fetch one page and extract claims. Returns (source, verified_claims) or None.

        Runs in a worker thread; re-raises ScoutAPIError so the caller can surface it.
        """
        try:
            page_text = self.fetcher.fetch_text(result.url)
        except Exception as exc:
            self.trace.append(AgentStep(iteration, tool_name, "Fetch candidate source", "fetch_page", f"failed {result.url}: {exc}"))
            self._emit("skip", f"Could not read {_domain(result.url)}")
            return None
        source = _source_record(tool_name, result, page_text, source_relation)
        self.trace.append(AgentStep(iteration, tool_name, f"Read {source.source_relation} {source.source_type} source", "fetch_page", result.url))
        self._emit("read", f"Reading {source.source_type} · {_domain(result.url)}")
        try:
            claims = self.extractor.extract(tool_name, result.url, source.source_type, page_text, company_context)
        except ScoutAPIError:
            raise
        except Exception as exc:
            self.trace.append(AgentStep(iteration, tool_name, "Extract risk claims", "llm_extract", f"failed {result.url}: {exc}"))
            self._emit("skip", f"Extraction failed for {_domain(result.url)}")
            return source, []
        verified = [claim.model_copy(update={"source_relation": source_relation}) for claim in discard_claims_without_quotes(claims)]
        self.trace.append(AgentStep(iteration, tool_name, "Verify claim quotes exist in source", "extract_and_verify", f"{len(verified)} claims from {result.url}"))
        self._emit("extract", f"{len(verified)} verified claim(s) from {_domain(result.url)}")
        return source, verified

    def scan(self, tools: list[str], company_context: str, output_dir: Path, max_iterations: int = 3, progress: ProgressFn = None, max_pages_per_iteration: int = 6) -> ScanResult:
        run_id = str(uuid4())
        self._progress = progress
        output_dir.mkdir(parents=True, exist_ok=True)
        all_sources: list[SourceRecord] = []
        all_claims: list[EvidenceClaim] = []
        seen_urls: set[str] = set()

        for tool_index, tool_name in enumerate(tools, start=1):
            self._emit("tool", f"Investigating {tool_name} ({tool_index}/{len(tools)})")
            wanted = set(REQUIRED_SOURCE_TYPES)
            for iteration in range(1, max_iterations + 1):
                queries = self._plan_queries(tool_name, wanted, iteration)
                self.trace.append(AgentStep(iteration, tool_name, f"Need evidence types: {sorted(wanted)}", "plan_queries", "; ".join(queries)))
                self._emit("plan", f"{tool_name}: pass {iteration} — looking for {', '.join(sorted(wanted))}")
                discovered: list[SearchResult] = []
                for query in queries:
                    results = self.searcher.search(query, max_results=4)
                    discovered.extend(results)
                    self.trace.append(AgentStep(iteration, tool_name, f"Search web for {query}", "tavily_search", f"{len(results)} results"))
                self._emit("search", f"{tool_name}: searched the web, found {len(discovered)} candidate page(s)")

                # Select candidate sources to read this iteration (dedup + drop unrelated).
                candidates: list[tuple[SearchResult, SourceRelation]] = []
                for result in self._rank_results(tool_name, discovered):
                    if result.url in seen_urls:
                        continue
                    seen_urls.add(result.url)
                    source_relation = classify_source_relation(tool_name, result)
                    if source_relation == "unrelated":
                        self.trace.append(AgentStep(iteration, tool_name, "Reject unrelated source", "reject_unrelated_source", result.url))
                        continue
                    candidates.append((result, source_relation))
                    if len(candidates) >= max_pages_per_iteration:
                        break

                # Read + extract candidates concurrently to cut wall-clock time.
                if candidates:
                    self._emit("read", f"{tool_name}: reading {len(candidates)} source(s) in parallel")
                    with ThreadPoolExecutor(max_workers=min(self.max_workers, len(candidates))) as pool:
                        futures = [pool.submit(self._process_source, tool_name, company_context, iteration, r, rel) for r, rel in candidates]
                        for future in futures:
                            outcome = future.result()  # ScoutAPIError propagates here
                            if not outcome:
                                continue
                            source, verified = outcome
                            all_sources.append(source)
                            all_claims.extend(verified)

                observed_types = {s.source_type for s in all_sources if s.tool_name.lower() == tool_name.lower()}
                wanted = REQUIRED_SOURCE_TYPES - observed_types
                if not wanted:
                    self.trace.append(AgentStep(iteration, tool_name, "All required source types observed", "stop", "coverage complete"))
                    self._emit("done", f"{tool_name}: evidence coverage complete")
                    break
                self.trace.append(AgentStep(iteration, tool_name, "Coverage gaps remain", "continue", f"missing {sorted(wanted)}"))

        self._emit("score", "Scoring tools against your policy and writing the audit packet")
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

    def _rank_results(self, tool_name: str, results: list[SearchResult]) -> list[SearchResult]:
        dedup: dict[str, SearchResult] = {}
        for result in results:
            dedup.setdefault(result.url, result)

        def score(result: SearchResult) -> tuple[int, int]:
            url = result.url.lower()
            source_type = classify_source_type(url)
            relation = classify_source_relation(tool_name, result)
            relation_bonus = {"official": 6, "third_party": 2, "unrelated": -20, "unknown": 0}[relation]
            type_bonus = 4 if source_type in REQUIRED_SOURCE_TYPES else 0
            return (type_bonus + relation_bonus, len(result.snippet))

        return sorted(dedup.values(), key=score, reverse=True)[:10]


def run_agentic_scan(tools: list[str], company_context: str, output_dir: Path, max_iterations: int = 3, progress: ProgressFn = None, max_pages_per_iteration: int = 6) -> ScanResult:
    return AgenticScanner().scan(
        tools,
        company_context,
        output_dir,
        max_iterations=max_iterations,
        progress=progress,
        max_pages_per_iteration=max_pages_per_iteration,
    )
