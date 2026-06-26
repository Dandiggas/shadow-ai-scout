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
