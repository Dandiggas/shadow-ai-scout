from scout.extraction import discard_claims_without_quotes, classify_source_type
from scout.models import EvidenceClaim


def test_discard_claims_without_quotes_keeps_audit_trail_clean():
    good = EvidenceClaim(tool_name="Tool", source_url="https://example.com/security", source_type="security", risk_category="SSO/SAML", claim_text="Has SSO", evidence_quote="SSO is available", severity=1, confidence=0.8)
    bad = EvidenceClaim(tool_name="Tool", source_url="https://example.com/privacy", source_type="privacy", risk_category="Training on customer data", claim_text="May train", evidence_quote="", severity=4, confidence=0.5)

    assert discard_claims_without_quotes([good, bad]) == [good]


def test_classify_source_type_from_url():
    assert classify_source_type("https://vendor.com/privacy") == "privacy"
    assert classify_source_type("https://vendor.com/trust/security") == "security"
    assert classify_source_type("https://vendor.com/pricing") == "pricing"
    assert classify_source_type("https://news.example.com/vendor-breach") == "news"
