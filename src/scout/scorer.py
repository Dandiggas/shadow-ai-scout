from __future__ import annotations

import re

from scout.models import EvidenceClaim, Requirement, RequirementAssessment, ToolVerdict

RISK_CATEGORY_WEIGHTS = {
    "Local device access": 20,
    "Browser access": 16,
    "Source code exposure": 18,
    "Meeting transcript exposure": 18,
    "Customer data exposure": 18,
    "Training on customer data": 15,
    "Data retention": 12,
    "Third-party subprocessors": 10,
    "Breach/news history": 15,
}

NEGATIVE_CONTROL_MARKERS = (
    " no ",
    " not ",
    "without ",
    "does not ",
    "do not ",
    "lacks ",
    "lack ",
    "disabled ",
    "not supported",
    "not currently supported",
    "not offer",
    "not available",
)

POSITIVE_CONTROL_MARKERS = (
    "never used for training",
    "never stored or used for training",
    "not used for training",
    "not train",
    "zero data retention",
    "data processing agreement",
    "dpa",
    "sso is available",
    "supports sso",
    "saml-based sso",
    "soc 2 type 2 certified",
    "soc 2 certified",
)



def _claim_text(claim: EvidenceClaim) -> str:
    return f" {claim.risk_category} {claim.claim_text} {claim.evidence_quote} ".lower()



def _matches(requirement: Requirement, claim: EvidenceClaim) -> bool:
    haystack = _claim_text(claim)
    for keyword in requirement.keywords:
        needle = keyword.lower().strip()
        if not needle:
            continue
        if " " in needle:
            if needle in haystack:
                return True
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack):
            return True
    return False


def _has_positive_control_marker(claim: EvidenceClaim) -> bool:
    text = _claim_text(claim)
    return any(marker in text for marker in POSITIVE_CONTROL_MARKERS)


def _is_negative_control_claim(claim: EvidenceClaim) -> bool:
    if _has_positive_control_marker(claim):
        return False
    text = _claim_text(claim)
    return claim.severity >= 2 and any(marker in text for marker in NEGATIVE_CONTROL_MARKERS)


def _is_supporting_control_claim(claim: EvidenceClaim) -> bool:
    return claim.severity <= 1 or _has_positive_control_marker(claim)



def assess_requirement(requirement: Requirement, claims: list[EvidenceClaim]) -> RequirementAssessment:
    matching = [claim for claim in claims if claim.evidence_quote and _matches(requirement, claim)]
    supporting = [claim for claim in matching if _is_supporting_control_claim(claim)]
    if supporting:
        best = max(supporting, key=lambda claim: (claim.confidence, -claim.severity))
        return RequirementAssessment(
            requirement_id=requirement.id,
            label=requirement.label,
            status="pass",
            evidence_quote=best.evidence_quote,
            source_url=best.source_url,
            confidence=best.confidence,
            action="meets requirement",
            score_delta=-8 if requirement.required else -4,
        )

    failing = [claim for claim in matching if _is_negative_control_claim(claim)]
    if failing:
        worst = max(failing, key=lambda claim: (claim.severity, claim.confidence))
        return RequirementAssessment(
            requirement_id=requirement.id,
            label=requirement.label,
            status="fail",
            evidence_quote=worst.evidence_quote,
            source_url=worst.source_url,
            confidence=worst.confidence,
            action="control gap needs vendor answer",
            score_delta=requirement.fail_weight if requirement.required else max(1, requirement.fail_weight // 2),
        )

    return RequirementAssessment(
        requirement_id=requirement.id,
        label=requirement.label,
        status="unclear" if requirement.required else "pass",
        action="vendor/security review required" if requirement.required else "optional control not found",
        score_delta=requirement.fail_weight if requirement.required else 0,
    )


def score_tool(tool_name: str, requirements: list[Requirement], claims: list[EvidenceClaim]) -> ToolVerdict:
    relevant_claims = [claim for claim in claims if claim.tool_name.lower() == tool_name.lower()]
    assessments = [assess_requirement(req, relevant_claims) for req in requirements]

    score = 20  # base risk for any unsanctioned AI vendor entering review
    for assessment in assessments:
        score += assessment.score_delta

    risk_deltas_by_category: dict[str, int] = {}
    for claim in relevant_claims:
        if claim.severity <= 1:
            continue
        category_weight = RISK_CATEGORY_WEIGHTS.get(claim.risk_category, 0)
        if category_weight == 0:
            continue
        severity_weight = claim.severity * 4
        confidence_factor = max(claim.confidence, 0.5)
        delta = round((category_weight + severity_weight) * confidence_factor)
        risk_deltas_by_category[claim.risk_category] = max(risk_deltas_by_category.get(claim.risk_category, 0), delta)

    score += sum(risk_deltas_by_category.values())
    failed_policy = [a.label for req, a in zip(requirements, assessments, strict=True) if req.required and a.status != "pass"]
    if not failed_policy and score > 75:
        # A clean policy-control matrix should escalate to human review, not an outright reject.
        # Reject is reserved for failed/unclear required controls plus risk evidence.
        score = 75

    score = max(0, min(100, score))
    if score <= 25:
        verdict = "approve"
    elif score <= 50:
        verdict = "conditional approve"
    elif score <= 75:
        verdict = "needs review"
    else:
        verdict = "reject/high risk"

    top_risks = sorted([c for c in relevant_claims if c.severity >= 2], key=lambda c: (c.severity, c.confidence), reverse=True)[:2]
    risk_summary = "; ".join(claim.claim_text for claim in top_risks) or "No high-confidence public risk claims found."
    recommended = _recommend(verdict, failed_policy)

    return ToolVerdict(
        tool_name=tool_name,
        risk_score=score,
        verdict=verdict,
        failed_policy=failed_policy,
        summary=risk_summary,
        recommended_policy=recommended,
        requirements=assessments,
    )


def _recommend(verdict: str, failed_policy: list[str]) -> str:
    if verdict == "approve":
        return "Approve for normal use, with periodic monitoring."
    if verdict == "conditional approve":
        return "Approve only with documented controls and restricted data use."
    if verdict == "needs review":
        return "Escalate to security/legal before rollout; require vendor answers for unclear controls."
    return "Do not approve for sensitive company data unless risk posture materially changes."
