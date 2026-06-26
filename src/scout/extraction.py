from __future__ import annotations

from scout.models import EvidenceClaim


def discard_claims_without_quotes(claims: list[EvidenceClaim]) -> list[EvidenceClaim]:
    return [claim for claim in claims if claim.evidence_quote.strip()]


def classify_source_type(url: str) -> str:
    lower = url.lower()
    if "privacy" in lower:
        return "privacy"
    if "security" in lower or "trust" in lower:
        return "security"
    if "terms" in lower or "legal" in lower:
        return "terms"
    if "subprocessor" in lower:
        return "subprocessors"
    if "pricing" in lower or "enterprise" in lower:
        return "pricing"
    if "docs" in lower or "help" in lower:
        return "docs"
    if "news" in lower or "breach" in lower or "incident" in lower:
        return "news"
    return "other"
