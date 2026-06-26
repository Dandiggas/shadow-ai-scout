from scout.models import EvidenceClaim, Requirement
from scout.scorer import assess_requirement, score_tool


def test_requirement_passes_when_supporting_evidence_matches_keywords():
    requirement = Requirement(
        id="sso_required",
        label="SSO/admin controls required",
        required=True,
        keywords=["sso", "saml", "admin controls"],
        fail_weight=10,
    )
    claims = [
        EvidenceClaim(
            tool_name="Cursor",
            source_url="https://cursor.com/security",
            source_type="security",
            risk_category="SSO/SAML",
            claim_text="Cursor supports SSO and admin controls on enterprise plans.",
            evidence_quote="Enterprise customers can configure SSO, SAML, and admin controls.",
            severity=1,
            confidence=0.9,
        )
    ]

    result = assess_requirement(requirement, claims)

    assert result.status == "pass"
    assert result.evidence_quote == "Enterprise customers can configure SSO, SAML, and admin controls."
    assert result.source_url == "https://cursor.com/security"


def test_requirement_unclear_adds_weight_when_required_evidence_missing():
    requirement = Requirement(
        id="dpa_required",
        label="DPA available",
        required=True,
        keywords=["data processing agreement", "dpa"],
        fail_weight=12,
    )

    result = assess_requirement(requirement, [])

    assert result.status == "unclear"
    assert result.score_delta == 12
    assert result.action == "vendor/security review required"


def test_score_tool_combines_policy_gaps_and_risk_claims():
    requirements = [
        Requirement(id="sso", label="SSO required", required=True, keywords=["sso"], fail_weight=10),
        Requirement(id="no_training", label="No training on customer data", required=True, keywords=["not train", "training"], fail_weight=15),
    ]
    claims = [
        EvidenceClaim(
            tool_name="Rewind AI",
            source_url="https://example.com/privacy",
            source_type="privacy",
            risk_category="Local device access",
            claim_text="The app records local screen activity.",
            evidence_quote="Rewind records what you have seen, said, or heard.",
            severity=5,
            confidence=0.85,
        )
    ]

    verdict = score_tool("Rewind AI", requirements, claims)

    assert verdict.tool_name == "Rewind AI"
    assert verdict.risk_score >= 70
    assert verdict.verdict in {"needs review", "reject/high risk"}
    assert "SSO required" in verdict.failed_policy
