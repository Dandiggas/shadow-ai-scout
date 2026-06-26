from scout.models import EvidenceClaim, Requirement
from scout.scorer import score_tool


def test_positive_control_claims_do_not_create_reject_verdict():
    requirements = [
        Requirement(id="sso", label="SSO required", keywords=["sso"], fail_weight=10),
        Requirement(id="no_training", label="No training on customer data", keywords=["never used for training", "not used for training"], fail_weight=15),
        Requirement(id="soc2", label="SOC2 preferred", keywords=["soc 2"], fail_weight=8),
    ]
    claims = [
        EvidenceClaim(tool_name="Cursor", source_url="https://cursor.com/security", source_type="security", risk_category="SSO/SAML", claim_text="Cursor supports SSO.", evidence_quote="Admins can enforce SSO", severity=0, confidence=1.0),
        EvidenceClaim(tool_name="Cursor", source_url="https://cursor.com/privacy", source_type="privacy", risk_category="Training on customer data", claim_text="Code is never used for training.", evidence_quote="code is never used for training", severity=0, confidence=1.0),
        EvidenceClaim(tool_name="Cursor", source_url="https://cursor.com/security", source_type="security", risk_category="SOC2 / ISO27001", claim_text="Cursor has SOC 2.", evidence_quote="SOC 2 Type 2 certified", severity=0, confidence=1.0),
    ]

    verdict = score_tool("Cursor", requirements, claims)

    assert verdict.failed_policy == []
    assert verdict.risk_score <= 25
    assert verdict.verdict == "approve"
