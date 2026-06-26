from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from scout.approvals import DecisionStore
from scout.models import ScanResult
from scout.pipeline import run_cached_scan

APPROVED_VERDICTS = {"approve", "conditional approve"}

ScanFunc = Callable[[list[str], str, Path], ScanResult]


def approved_tools_from_decisions(store: DecisionStore) -> list[str]:
    """Return currently approved/conditionally approved tools from saved decisions."""
    tools: list[str] = []
    seen: set[str] = set()
    for decision in store.list_decisions():
        key = decision.tool_name.lower()
        if key in seen:
            continue
        seen.add(key)
        if decision.verdict in APPROVED_VERDICTS:
            tools.append(decision.tool_name)
    return tools


def review_approved_products(
    store: DecisionStore,
    company_context: str,
    output_dir: Path,
    scan_func: ScanFunc = run_cached_scan,
) -> ScanResult:
    """Rescan approved tools and write a weekly compliance summary."""
    tools = approved_tools_from_decisions(store)
    if not tools:
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = output_dir / "weekly_review_summary.md"
        summary_path.write_text(
            "# Weekly compliance review\n\nNo approved products found in the decision store.\n",
            encoding="utf-8",
        )
        raise ValueError("No approved products found in the decision store")

    result = scan_func(tools, company_context, output_dir)
    _write_weekly_summary(result, output_dir)
    return result


def _write_weekly_summary(result: ScanResult, output_dir: Path) -> Path:
    path = output_dir / "weekly_review_summary.md"
    lines = [
        "# Weekly compliance review",
        "",
        f"Reviewed at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| Tool | Current verdict | Score | Action |",
        "|---|---|---:|---|",
    ]
    for verdict in result.verdicts:
        action = verdict.recommended_policy
        if verdict.verdict in {"reject/high risk", "needs review"}:
            action = "Escalate: previously approved tool now needs review. " + action
        lines.append(f"| {verdict.tool_name} | {verdict.verdict} | {verdict.risk_score} | {action} |")

    lines.extend([
        "",
        f"Full cited report: {result.markdown_report}",
        f"Evidence JSON: {result.evidence_json}",
        f"ClickHouse inserts: {result.clickhouse_sql}",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
