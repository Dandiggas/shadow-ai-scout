from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from scout.models import ToolVerdict


class ApprovalRequest(BaseModel):
    employee: str
    tool_name: str
    use_case: str
    data_involved: str
    requested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SavedDecision(BaseModel):
    tool_name: str
    verdict: str
    risk_score: int
    failed_policy: list[str]
    recommended_policy: str
    allowed_usage: list[str] = Field(default_factory=list)
    blocked_usage: list[str] = Field(default_factory=list)
    required_controls: list[str] = Field(default_factory=list)
    employee: str
    use_case: str
    data_involved: str
    decided_at: str
    action: str = "reuse previous decision or review changed use case"


class DecisionStore:
    def __init__(self, path: Path):
        self.path = path

    def _load(self) -> list[SavedDecision]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [SavedDecision.model_validate(item) for item in payload]

    def _save_all(self, decisions: list[SavedDecision]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([d.model_dump(mode="json") for d in decisions], indent=2), encoding="utf-8")

    def save_decision(self, request: ApprovalRequest, verdict: ToolVerdict) -> SavedDecision:
        decision = SavedDecision(
            tool_name=verdict.tool_name,
            verdict=verdict.verdict,
            risk_score=verdict.risk_score,
            failed_policy=verdict.failed_policy,
            recommended_policy=verdict.recommended_policy,
            allowed_usage=verdict.allowed_usage,
            blocked_usage=verdict.blocked_usage,
            required_controls=verdict.required_controls,
            employee=request.employee,
            use_case=request.use_case,
            data_involved=request.data_involved,
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
        decisions = [
            d
            for d in self._load()
            if not (
                d.tool_name.lower() == verdict.tool_name.lower()
                and d.use_case.lower() == request.use_case.lower()
                and d.data_involved.lower() == request.data_involved.lower()
            )
        ]
        decisions.append(decision)
        self._save_all(decisions)
        return decision

    def find_previous(self, tool_name: str, use_case: str | None = None, data_involved: str | None = None) -> SavedDecision | None:
        matching = [d for d in self._load() if d.tool_name.lower() == tool_name.lower()]
        if use_case is not None:
            matching = [d for d in matching if d.use_case.lower() == use_case.lower()]
        if data_involved is not None:
            matching = [d for d in matching if d.data_involved.lower() == data_involved.lower()]
        if not matching:
            return None
        return sorted(matching, key=lambda d: d.decided_at, reverse=True)[0]

    def list_decisions(self) -> list[SavedDecision]:
        return sorted(self._load(), key=lambda d: d.decided_at, reverse=True)
