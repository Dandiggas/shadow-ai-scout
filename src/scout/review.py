from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from scout.approvals import DecisionStore, SavedDecision
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

    previous_decisions = store.list_decisions()
    result = scan_func(tools, company_context, output_dir)
    _write_weekly_summary(result, output_dir, previous_decisions)
    return result


def _latest_by_tool(decisions: list[SavedDecision]) -> dict[str, SavedDecision]:
    latest: dict[str, SavedDecision] = {}
    for decision in sorted(decisions, key=lambda d: d.decided_at):
        latest[decision.tool_name.lower()] = decision
    return latest


def _write_weekly_summary(result: ScanResult, output_dir: Path, previous_decisions: list[SavedDecision] | None = None) -> Path:
    path = output_dir / "weekly_review_summary.md"
    previous_by_tool = _latest_by_tool(previous_decisions or [])
    lines = [
        "# Weekly compliance review",
        "",
        f"Reviewed at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| Tool | Previous verdict | Previous score | Current verdict | Current score | Delta | Action |",
        "|---|---|---:|---|---:|---:|---|",
    ]
    for verdict in result.verdicts:
        previous = previous_by_tool.get(verdict.tool_name.lower())
        previous_verdict = previous.verdict if previous else "new"
        previous_score = previous.risk_score if previous else 0
        delta = verdict.risk_score - previous_score
        delta_text = f"{delta:+d}"
        action = verdict.recommended_policy
        if previous and (verdict.verdict != previous.verdict or delta > 0):
            action = f"Drift detected from saved decision. {action}"
        if verdict.verdict in {"reject/high risk", "needs review"}:
            action = "Escalate: previously approved tool now needs review. " + action
        lines.append(f"| {verdict.tool_name} | {previous_verdict} | {previous_score} | {verdict.verdict} | {verdict.risk_score} | {delta_text} | {action} |")

    lines.extend([
        "",
        f"Full cited report: {result.markdown_report}",
        f"Evidence JSON: {result.evidence_json}",
        f"ClickHouse inserts: {result.clickhouse_sql}",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
