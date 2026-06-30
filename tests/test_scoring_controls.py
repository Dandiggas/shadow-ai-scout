from scout.models import EvidenceClaim, Requirement
from scout.policy import default_requirements
from scout.scorer import assess_requirement, score_tool


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


def test_requirement_keywords_do_not_match_inside_unrelated_words():
    requirements = [Requirement(id="sso", label="SSO required", keywords=["sso"], fail_weight=10)]
    claims = [
        EvidenceClaim(
            tool_name="Cursor",
            source_url="https://cursor.com/terms",
            source_type="terms",
            risk_category="Source code exposure",
            claim_text="Auto-executed code has associated security risk.",
            evidence_quote="assuming all risks associated with the execution of automatically generated code",
            severity=4,
            confidence=1.0,
        )
    ]

    verdict = score_tool("Cursor", requirements, claims)

    assert verdict.requirements[0].status == "unclear"


def test_positive_no_training_wording_is_support_not_failure():
    requirements = [Requirement(id="no_training", label="No training on customer data", keywords=["training"], fail_weight=15)]
    claims = [
        EvidenceClaim(
            tool_name="Cursor",
            source_url="https://cursor.com/security",
            source_type="security",
            risk_category="Training on customer data",
            claim_text="Code is never stored or used for training.",
            evidence_quote="code data is never stored or used for training",
            severity=0,
            confidence=1.0,
        )
    ]

    verdict = score_tool("Cursor", requirements, claims)

    assert verdict.requirements[0].status == "pass"


def test_negative_control_claim_does_not_pass_requirement():
    requirements = [
        Requirement(id="audit_logs", label="Audit logs preferred", keywords=["audit log", "audit logs", "logging"], fail_weight=8),
    ]
    claims = [
        EvidenceClaim(
            tool_name="Cursor",
            source_url="https://example.com/cursor-review",
            source_type="security",
            risk_category="Audit logs",
            claim_text="Cursor does not offer client-exposed security or administrative audit logging.",
            evidence_quote="No Client-Exposed Audit Logging",
            severity=3,
            confidence=1.0,
        )
    ]

    verdict = score_tool("Cursor", requirements, claims)

    assert verdict.requirements[0].status == "fail"
    assert "No Client-Exposed Audit Logging" in verdict.requirements[0].evidence_quote


def test_clean_policy_pass_caps_adverse_claims_at_needs_review_not_reject():
    requirements = [
        Requirement(id="sso", label="SSO required", keywords=["sso"], fail_weight=10),
        Requirement(id="no_training", label="No training on customer data", keywords=["never used for training"], fail_weight=15),
        Requirement(id="dpa", label="DPA available", keywords=["data processing agreement"], fail_weight=12),
    ]
    claims = [
        EvidenceClaim(tool_name="Cursor", source_url="https://cursor.com/security", source_type="security", risk_category="SSO/SAML", claim_text="Cursor supports SSO.", evidence_quote="SSO is available", severity=0, confidence=1.0),
        EvidenceClaim(tool_name="Cursor", source_url="https://cursor.com/privacy", source_type="privacy", risk_category="Training on customer data", claim_text="Code is never used for training.", evidence_quote="code is never used for training", severity=0, confidence=1.0),
        EvidenceClaim(tool_name="Cursor", source_url="https://cursor.com/terms/dpa", source_type="terms", risk_category="GDPR / DPA", claim_text="Cursor offers a data processing agreement.", evidence_quote="Data Processing Agreement", severity=0, confidence=1.0),
        EvidenceClaim(tool_name="Cursor", source_url="https://third-party.example/cursor", source_type="security", risk_category="Source code exposure", claim_text="Independent review says source-code handling needs legal review.", evidence_quote="source-code handling needs legal review", severity=5, confidence=1.0),
        EvidenceClaim(tool_name="Cursor", source_url="https://third-party.example/cursor", source_type="security", risk_category="Local device access", claim_text="Independent review says local extension defaults create risk.", evidence_quote="local extension defaults create risk", severity=5, confidence=1.0),
    ]

    verdict = score_tool("Cursor", requirements, claims)

    assert verdict.failed_policy == []
    assert verdict.verdict == "needs review"
    assert 51 <= verdict.risk_score <= 75
    assert any(reason.label == "Source code exposure" and reason.source_url == "https://third-party.example/cursor" for reason in verdict.score_reasons)
    assert any("source-code" in step.action.lower() for step in verdict.remediation_steps)


def test_positive_control_claims_from_third_party_do_not_satisfy_required_vendor_controls():
    dpa = next(req for req in default_requirements() if req.id == "dpa")
    claim = EvidenceClaim(
        tool_name="Browserbase",
        source_url="https://jasper.ai/legal/dpa",
        source_type="terms",
        source_relation="third_party",
        risk_category="GDPR / DPA",
        claim_text="Jasper offers a data processing agreement.",
        evidence_quote="Data Processing Agreement",
        severity=0,
        confidence=1.0,
    )

    result = assess_requirement(dpa, [claim])

    assert result.status == "unclear"
    assert result.source_url == ""
    assert result.action == "vendor/security review required"


def test_sensitive_data_risk_cannot_be_unrestricted_approve():
    requirements = [Requirement(id="dpa", label="DPA available", keywords=["data processing agreement"], fail_weight=12)]
    claims = [
        EvidenceClaim(tool_name="Cursor", source_url="https://cursor.com/terms", source_type="terms", risk_category="GDPR / DPA", claim_text="Cursor offers a DPA.", evidence_quote="Data Processing Agreement", severity=0, confidence=1.0),
        EvidenceClaim(tool_name="Cursor", source_url="https://cursor.com/privacy", source_type="privacy", risk_category="Source code exposure", claim_text="Customer code may be processed.", evidence_quote="Customer code may be processed", severity=2, confidence=0.5),
    ]

    verdict = score_tool("Cursor", requirements, claims)

    assert verdict.verdict == "conditional approve"
    assert "Unmanaged source-code repositories" in verdict.blocked_usage
    assert "Restricted rollout" in verdict.allowed_usage[0]
