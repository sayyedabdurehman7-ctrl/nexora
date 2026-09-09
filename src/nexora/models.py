"""Typed task snapshots persisted as versioned JSON in SQLite."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Status(StrEnum):
    RECEIVED = "RECEIVED"
    CLASSIFIED = "CLASSIFIED"
    PLANNED = "PLANNED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    REPLANNED = "REPLANNED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    TIMED_OUT = "TIMED_OUT"


TERMINAL = {Status.COMPLETED, Status.FAILED, Status.CANCELLED, Status.BLOCKED, Status.TIMED_OUT}


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RequestType(StrEnum):
    QUESTION = "question"
    READ_ONLY = "low-risk read-only task"
    CHANGE = "state-changing task"
    SENSITIVE = "sensitive/destructive task"
    UNSUPPORTED = "unsupported or unsafe task"


class ToolResult(StrictModel):
    success: bool
    data: dict = Field(default_factory=dict)
    evidence: dict = Field(default_factory=dict)
    error_code: str | None = None
    safe_error: str | None = None
    duration_ms: float = 0


class PlanStep(StrictModel):
    id: str = Field(default_factory=new_id)
    order: int = Field(ge=1)
    description: str
    selected_tool: str
    inputs: dict = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    risk_level: Risk = Risk.LOW
    status: Status = Status.PLANNED
    expected_evidence: str
    retry_count: int = 0
    max_retries: int = 2
    result: ToolResult | None = None


class Plan(StrictModel):
    id: str = Field(default_factory=new_id)
    version: int = 1
    steps: list[PlanStep] = Field(default_factory=list)


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    USED = "used"
    EXPIRED = "expired"


class ApprovalRequest(StrictModel):
    id: str = Field(default_factory=new_id)
    action: str
    target: str
    risk: Risk
    consequence: str
    reversible: bool = True
    binding: str
    status: ApprovalState = ApprovalState.PENDING
    requested_at: datetime = Field(default_factory=now)
    decided_at: datetime | None = None


class TaskRun(StrictModel):
    id: str = Field(default_factory=new_id)
    user_text: str
    normalized_text: str
    request_type: RequestType = RequestType.UNSUPPORTED
    status: Status = Status.RECEIVED
    created_at: datetime = Field(default_factory=now)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    plan: Plan = Field(default_factory=Plan)
    approval: ApprovalRequest | None = None
    interventions: int = 0
    final_result: str = ""
    provider: str = "mock"


class GoalInput(StrictModel):
    user_text: str = Field(min_length=1, max_length=2000)
