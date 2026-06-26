from scout.models import RequirementAssessment, ToolVerdict
from scout.report import render_markdown_report


def test_report_renders_requirement_matrix_with_citations():
    verdict = ToolVerdict(
        tool_name="Cursor",
        risk_score=42,
        verdict="conditional approve",
        failed_policy=["Deletion controls unclear"],
        summary="Good enterprise posture, source-code handling needs review.",
        recommended_policy="Approve only for non-sensitive repos until enterprise controls are confirmed.",
        requirements=[
            RequirementAssessment(
                requirement_id="sso",
                label="SSO/admin controls required",
                status="pass",
                evidence_quote="SSO is available on enterprise plans.",
                source_url="https://cursor.com/security",
                confidence=0.9,
                action="meets requirement",
                score_delta=-8,
            )
        ],
    )

    md = render_markdown_report("Security-sensitive company", [verdict])

    assert "# Shadow AI Scout Report" in md
    assert "| Cursor | conditional approve | 42 |" in md
    assert "SSO/admin controls required" in md
    assert "https://cursor.com/security" in md
    assert "SSO is available on enterprise plans." in md


def test_report_renders_score_sources_and_compliance_roadmap():
    verdict = ToolVerdict(
        tool_name="Cursor",
        risk_score=75,
        verdict="needs review",
        failed_policy=[],
        summary="Source-code handling needs review.",
        recommended_policy="Approve only with documented controls.",
        score_reasons=[
            {
                "label": "Source code exposure",
                "score_delta": 38,
                "evidence_quote": "source-code handling needs legal review",
                "source_url": "https://example.com/cursor-security",
            }
        ],
        remediation_steps=[
            {
                "action": "Block source-code use until enterprise privacy mode is enforced.",
                "rationale": "Source-code exposure drove the score.",
                "source_url": "https://example.com/cursor-security",
            }
        ],
        requirements=[],
    )

    md = render_markdown_report("Security-sensitive company", [verdict])

    assert "### Why this score?" in md
    assert "| Source code exposure | +38 | source-code handling needs legal review | https://example.com/cursor-security |" in md
    assert "### Compliance roadmap" in md
    assert "Block source-code use until enterprise privacy mode is enforced." in md
