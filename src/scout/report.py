from __future__ import annotations

from scout.models import ToolVerdict


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def render_markdown_report(company_context: str, verdicts: list[ToolVerdict]) -> str:
    lines: list[str] = [
        "# Shadow AI Scout Report",
        "",
        "## Context",
        company_context.strip(),
        "",
        "## Executive verdict",
        "",
        "| Tool | Verdict | Score | Failed policy |",
        "|---|---:|---:|---|",
    ]
    for verdict in verdicts:
        failed = ", ".join(verdict.failed_policy) if verdict.failed_policy else "None found"
        lines.append(f"| {verdict.tool_name} | {verdict.verdict} | {verdict.risk_score} | {failed} |")

    for verdict in verdicts:
        lines.extend([
            "",
            f"## Tool: {verdict.tool_name}",
            "",
            f"Verdict: **{verdict.verdict}**  ",
            f"Risk score: **{verdict.risk_score}/100**",
            "",
            f"Summary: {verdict.summary}",
            "",
            f"Recommended policy: {verdict.recommended_policy}",
            "",
            "### Scoped approval profile",
            "",
            "**Allowed**",
            *_bullet_lines(verdict.allowed_usage or ["No approved usage until required controls are confirmed."]),
            "",
            "**Blocked**",
            *_bullet_lines(verdict.blocked_usage or ["Sensitive company data until explicitly approved."]),
            "",
            "**Required controls**",
            *_bullet_lines(verdict.required_controls or ["Reviewer sign-off and retained evidence packet."]),
            "",
            "### Requirement matrix",
            "",
            "| Requirement | Status | Evidence | Source | Action |",
            "|---|---|---|---|---|",
        ])
        for assessment in verdict.requirements:
            evidence = assessment.evidence_quote.replace("|", "\\|") if assessment.evidence_quote else "No public evidence found"
            source = assessment.source_url or "-"
            lines.append(f"| {assessment.label} | {assessment.status} | {evidence} | {source} | {assessment.action} |")

        lines.extend([
            "",
            "### Why this score?",
            "",
            "| Reason | Score impact | Evidence | Source |",
            "|---|---:|---|---|",
        ])
        for reason in verdict.score_reasons:
            evidence = reason.evidence_quote.replace("|", "\\|") if reason.evidence_quote else "-"
            source = reason.source_url or "-"
            sign = "+" if reason.score_delta >= 0 else ""
            lines.append(f"| {reason.label} | {sign}{reason.score_delta} | {evidence} | {source} |")

        lines.extend([
            "",
            "### Compliance roadmap",
            "",
            "| Action | Why | Source |",
            "|---|---|---|",
        ])
        for step in verdict.remediation_steps:
            rationale = step.rationale.replace("|", "\\|") if step.rationale else "-"
            source = step.source_url or "-"
            lines.append(f"| {step.action} | {rationale} | {source} |")

    lines.append("")
    return "\n".join(lines)
