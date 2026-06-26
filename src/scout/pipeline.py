from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from scout.fixtures import cached_claims_for, cached_sources_for
from scout.models import EvidenceClaim, ScanResult, SourceRecord, ToolVerdict
from scout.policy import default_requirements
from scout.report import render_markdown_report
from scout.scorer import score_tool


def run_cached_scan(tools: list[str], company_context: str, output_dir: Path) -> ScanResult:
    run_id = str(uuid4())
    output_dir.mkdir(parents=True, exist_ok=True)

    sources: list[SourceRecord] = []
    claims: list[EvidenceClaim] = []
    verdicts: list[ToolVerdict] = []
    requirements = default_requirements()

    for tool_name in tools:
        tool_sources = cached_sources_for(tool_name)
        tool_claims = [claim for claim in cached_claims_for(tool_name) if claim.evidence_quote]
        sources.extend(tool_sources)
        claims.extend(tool_claims)
        verdicts.append(score_tool(tool_name, requirements, tool_claims))

    evidence_path = output_dir / "evidence.json"
    report_path = output_dir / "cited.md"
    sql_path = output_dir / "clickhouse_inserts.sql"

    evidence_payload = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "company_context": company_context,
        "sources": [s.model_dump(mode="json") for s in sources],
        "claims": [c.model_dump(mode="json") for c in claims],
        "verdicts": [v.model_dump(mode="json") for v in verdicts],
        "requirements": [r.model_dump(mode="json") for r in requirements],
    }
    evidence_path.write_text(json.dumps(evidence_payload, indent=2), encoding="utf-8")
    report_path.write_text(render_markdown_report(company_context, verdicts), encoding="utf-8")
    sql_path.write_text(render_clickhouse_inserts(run_id, company_context, tools, sources, claims, verdicts), encoding="utf-8")

    return ScanResult(
        run_id=run_id,
        verdicts=verdicts,
        claims=claims,
        sources=sources,
        evidence_json=evidence_path,
        markdown_report=report_path,
        clickhouse_sql=sql_path,
    )


def _sql(value: object) -> str:
    if isinstance(value, list):
        return "[" + ",".join(_sql(v) for v in value) + "]"
    text = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{text}'"


def render_clickhouse_inserts(run_id: str, company_context: str, tools: list[str], sources: list[SourceRecord], claims: list[EvidenceClaim], verdicts: list[ToolVerdict]) -> str:
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "-- ClickHouse-ready inserts for Shadow AI Scout demo evidence",
        f"INSERT INTO runs (run_id, created_at, company_context, policy_json, requested_tools) VALUES ({_sql(run_id)}, toDateTime('{created_at}'), {_sql(company_context)}, '{{}}', {_sql(tools)});",
    ]
    for source in sources:
        fetched = source.fetched_at.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(
            "INSERT INTO sources (run_id, tool_name, source_url, source_title, source_type, fetched_at, content_hash, snippet) VALUES "
            f"({_sql(run_id)}, {_sql(source.tool_name)}, {_sql(source.source_url)}, {_sql(source.source_title)}, {_sql(source.source_type)}, toDateTime('{fetched}'), {_sql(source.content_hash)}, {_sql(source.snippet)});"
        )
    for claim in claims:
        extracted = claim.extracted_at.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(
            "INSERT INTO risk_claims (run_id, tool_name, source_url, source_type, risk_category, claim_text, evidence_quote, severity, confidence, extracted_at) VALUES "
            f"({_sql(run_id)}, {_sql(claim.tool_name)}, {_sql(claim.source_url)}, {_sql(claim.source_type)}, {_sql(claim.risk_category)}, {_sql(claim.claim_text)}, {_sql(claim.evidence_quote)}, {claim.severity}, {claim.confidence}, toDateTime('{extracted}'));"
        )
    for verdict in verdicts:
        lines.append(
            "INSERT INTO verdicts (run_id, tool_name, risk_score, verdict, failed_policy, summary, recommended_policy, created_at) VALUES "
            f"({_sql(run_id)}, {_sql(verdict.tool_name)}, {verdict.risk_score}, {_sql(verdict.verdict)}, {_sql(verdict.failed_policy)}, {_sql(verdict.summary)}, {_sql(verdict.recommended_policy)}, toDateTime('{created_at}'));"
        )
    return "\n".join(lines) + "\n"
