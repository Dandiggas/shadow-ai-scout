from __future__ import annotations

import hashlib
from scout.models import EvidenceClaim, SourceRecord


TOOL_FIXTURE_TEXT = {
    "Cursor": {
        "https://cursor.com/security": (
            "security",
            "Cursor Security",
            "Enterprise customers can configure SSO, SAML, and admin controls. SOC 2 controls are documented for enterprise review."
        ),
        "https://cursor.com/privacy": (
            "privacy",
            "Cursor Privacy",
            "Customer code may be processed to provide AI coding assistance. Cursor states customer content is not used to train models when privacy controls are enabled. Users may request deletion of account data."
        ),
        "https://cursor.com/terms": (
            "terms",
            "Cursor Terms",
            "A data processing agreement may be available for enterprise customers upon request."
        ),
    },
    "Granola": {
        "https://www.granola.ai/privacy": (
            "privacy",
            "Granola Privacy",
            "Granola processes meeting notes and transcripts to provide AI meeting assistance. Retention and deletion controls are described for account data."
        ),
        "https://www.granola.ai/security": (
            "security",
            "Granola Security",
            "Granola provides security information for teams, but public SSO and audit log details may require vendor confirmation."
        ),
    },
    "Rewind AI": {
        "https://www.rewind.ai/privacy": (
            "privacy",
            "Rewind Privacy",
            "Rewind records what you have seen, said, or heard so you can search your digital history. Local device activity may include screen and audio content."
        ),
        "https://www.rewind.ai/security": (
            "security",
            "Rewind Security",
            "Security controls are described publicly, but enterprise SSO, audit logs, and DPA availability are unclear from this cached evidence."
        ),
    },
}


def cached_sources_for(tool_name: str) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    for url, (source_type, title, text) in TOOL_FIXTURE_TEXT.get(tool_name, {}).items():
        records.append(SourceRecord(
            tool_name=tool_name,
            source_url=url,
            source_title=title,
            source_type=source_type,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            snippet=text[:240],
        ))
    return records


def cached_claims_for(tool_name: str) -> list[EvidenceClaim]:
    if tool_name == "Cursor":
        return [
            EvidenceClaim(tool_name=tool_name, source_url="https://cursor.com/security", source_type="security", risk_category="SSO/SAML", claim_text="Cursor offers enterprise SSO/SAML and admin controls.", evidence_quote="Enterprise customers can configure SSO, SAML, and admin controls.", severity=1, confidence=0.9),
            EvidenceClaim(tool_name=tool_name, source_url="https://cursor.com/security", source_type="security", risk_category="SOC2 / ISO27001", claim_text="Cursor has documented enterprise security controls.", evidence_quote="SOC 2 controls are documented for enterprise review.", severity=1, confidence=0.75),
            EvidenceClaim(tool_name=tool_name, source_url="https://cursor.com/privacy", source_type="privacy", risk_category="Source code exposure", claim_text="Customer code may be processed to provide AI coding assistance.", evidence_quote="Customer code may be processed to provide AI coding assistance.", severity=4, confidence=0.86),
            EvidenceClaim(tool_name=tool_name, source_url="https://cursor.com/privacy", source_type="privacy", risk_category="Training on customer data", claim_text="Customer content is not used to train models when privacy controls are enabled.", evidence_quote="customer content is not used to train models when privacy controls are enabled.", severity=1, confidence=0.82),
            EvidenceClaim(tool_name=tool_name, source_url="https://cursor.com/privacy", source_type="privacy", risk_category="Deletion/export controls", claim_text="Users may request deletion of account data.", evidence_quote="Users may request deletion of account data.", severity=1, confidence=0.7),
            EvidenceClaim(tool_name=tool_name, source_url="https://cursor.com/terms", source_type="terms", risk_category="GDPR / DPA", claim_text="DPA may be available for enterprise customers.", evidence_quote="A data processing agreement may be available for enterprise customers upon request.", severity=1, confidence=0.72),
        ]
    if tool_name == "Granola":
        return [
            EvidenceClaim(tool_name=tool_name, source_url="https://www.granola.ai/privacy", source_type="privacy", risk_category="Meeting transcript exposure", claim_text="Granola processes meeting notes and transcripts.", evidence_quote="Granola processes meeting notes and transcripts to provide AI meeting assistance.", severity=4, confidence=0.88),
            EvidenceClaim(tool_name=tool_name, source_url="https://www.granola.ai/privacy", source_type="privacy", risk_category="Data retention", claim_text="Retention and deletion controls are described for account data.", evidence_quote="Retention and deletion controls are described for account data.", severity=2, confidence=0.65),
        ]
    if tool_name == "Rewind AI":
        return [
            EvidenceClaim(tool_name=tool_name, source_url="https://www.rewind.ai/privacy", source_type="privacy", risk_category="Local device access", claim_text="Rewind records local screen/audio history.", evidence_quote="Rewind records what you have seen, said, or heard so you can search your digital history.", severity=5, confidence=0.9),
            EvidenceClaim(tool_name=tool_name, source_url="https://www.rewind.ai/privacy", source_type="privacy", risk_category="Customer data exposure", claim_text="Local device activity may capture sensitive customer or internal data.", evidence_quote="Local device activity may include screen and audio content.", severity=5, confidence=0.82),
        ]
    return []
