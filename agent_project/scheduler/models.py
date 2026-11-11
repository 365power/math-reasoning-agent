from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Status = Literal["success", "error", "timeout"]


class TaskSpec(BaseModel):
    """一个调度任务 = 一次 rollout（一次真实的 Agent 会话）。"""

    id: str
    case_path: str
    rollout_id: int = Field(default=1, ge=1)
    timeout_s: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerJob(BaseModel):
    run_id: str
    task: TaskSpec
    case_id: str
    case_path: str
    workspace: str
    record_path: str
    trajectory_path: str
    mock: bool
    use_llm_judge: bool
    model: str | None = None


class TaskOutcome(BaseModel):
    id: str
    case_id: str
    rollout_id: int
    status: Status
    answer: str | None = None
    accuracy: int | None = None
    step_score: float | None = None
    step_max: int | None = None
    tokens: int = 0
    tool_calls: int = 0
    duration_s: float = 0.0
    termination: str = ""
    error: str | None = None
    model: str = ""
    mock: bool = False
    run_id: str = ""
    record_path: str | None = None
    trajectory_path: str | None = None
    log_path: str | None = None
    workspace: str = ""
