from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

Status = Literal["pass", "fail", "unclear"]
VerdictLabel = Literal["approve", "conditional approve", "needs review", "reject/high risk"]


class Requirement(BaseModel):
    id: str
    label: str
    required: bool = True
    keywords: list[str] = Field(default_factory=list)
    fail_weight: int = 10


class EvidenceClaim(BaseModel):
    tool_name: str
    source_url: str
    source_type: str
    risk_category: str
    claim_text: str
    evidence_quote: str
    severity: int = Field(ge=0, le=5)
    confidence: float = Field(ge=0, le=1)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RequirementAssessment(BaseModel):
    requirement_id: str
    label: str
    status: Status
    evidence_quote: str = ""
    source_url: str = ""
    confidence: float = 0.0
    action: str
    score_delta: int


class ToolVerdict(BaseModel):
    tool_name: str
    risk_score: int = Field(ge=0, le=100)
    verdict: VerdictLabel
    failed_policy: list[str]
    summary: str
    recommended_policy: str
    requirements: list[RequirementAssessment] = Field(default_factory=list)


class SourceRecord(BaseModel):
    tool_name: str
    source_url: str
    source_title: str
    source_type: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str
    snippet: str


class ScanResult(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    verdicts: list[ToolVerdict]
    claims: list[EvidenceClaim]
    sources: list[SourceRecord]
    evidence_json: Path
    markdown_report: Path
    clickhouse_sql: Path
