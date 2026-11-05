from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ActivityEvent(BaseModel):
    timestamp: datetime = Field(default_factory=utcnow)
    agent: str
    action: str
    detail: str
    tool: str | None = None
    status: StepStatus = StepStatus.SUCCEEDED


class PlanStep(BaseModel):
    id: str
    title: str
    description: str
    agent: str
    status: StepStatus = StepStatus.PENDING


class RunState(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    requirement: str
    status: RunStatus = RunStatus.QUEUED
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    project_type: str | None = None
    workspace: str | None = None
    mode: str = "deterministic"
    analysis_summary: str = ""
    features: list[str] = Field(default_factory=list)
    model_name: str | None = None
    provider_name: str | None = None
    duration_seconds: float = 0.0
    plan: list[PlanStep] = Field(default_factory=list)
    logs: list[ActivityEvent] = Field(default_factory=list)
    generated_files: list[str] = Field(default_factory=list)
    validation_output: str = ""
    retries: int = 0
    error: str | None = None
    sequence: int = 0
    project_id: str = ""
    source_run_id: str | None = None
    request_id: str | None = None
    phase: str = "queued"


class CreateRunRequest(BaseModel):
    requirement: str = Field(min_length=5, max_length=4000)
    request_id: str | None = Field(default=None, min_length=8, max_length=100)

    @field_validator("requirement", mode="before")
    @classmethod
    def trim_requirement(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class IterateRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=2000)
    request_id: str | None = Field(default=None, min_length=8, max_length=100)

    @field_validator("instruction", mode="before")
    @classmethod
    def trim_instruction(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class CommandResult(BaseModel):
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


class RunSummary(BaseModel):
    id: str
    requirement: str
    status: RunStatus
    project_type: str | None
    created_at: datetime
    workspace: str | None
    retries: int
    files: int
    mode: str = "deterministic"
    sequence: int = 0
    project_id: str = ""
    source_run_id: str | None = None
    phase: str = "queued"
    updated_at: datetime

    @classmethod
    def from_state(cls, state: RunState) -> "RunSummary":
        return cls(
            id=state.id,
            requirement=state.requirement,
            status=state.status,
            project_type=state.project_type,
            created_at=state.created_at,
            workspace=state.workspace,
            retries=state.retries,
            files=len(state.generated_files),
            mode=state.mode,
            sequence=state.sequence,
            project_id=state.project_id,
            source_run_id=state.source_run_id,
            phase=state.phase,
            updated_at=state.updated_at,
        )


class RunResponse(BaseModel):
    run: RunState
    summary: dict[str, Any] = Field(default_factory=dict)
