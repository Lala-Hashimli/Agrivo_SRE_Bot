from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricSummary(BaseModel):
    request_rate: float | None = None
    error_rate_percent: float | None = None
    p95_latency_ms: float | None = None
    cpu_percent: float | None = None
    memory_mib: float | None = None
    event_loop_p99_ms: float | None = None
    observed_at: datetime
    available: bool = True
    safe_error: str | None = None


class AlertInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    severity: str = "unknown"
    status: str = "firing"
    description: str = "No description"
    service: str | None = None
    started_at: datetime | None = None


class PodInfo(BaseModel):
    name: str
    namespace: str
    phase: str
    ready: str
    restarts: int = 0
    node: str | None = None
    age: str | None = None


class DeploymentInfo(BaseModel):
    name: str
    namespace: str
    ready: str
    available: int = 0
    desired: int = 0
    image: str | None = None


class HpaInfo(BaseModel):
    name: str
    namespace: str
    reference: str
    current_replicas: int
    min_replicas: int
    max_replicas: int
    metrics: str = "unavailable"


class WorkflowInfo(BaseModel):
    name: str
    status: str
    conclusion: str | None = None
    branch: str | None = None
    sha: str | None = None
    url: str | None = None
    created_at: datetime | None = None


class ArgoApplicationInfo(BaseModel):
    name: str
    sync: str
    health: str
    revision: str | None = None


class OperationResult(BaseModel):
    available: bool = True
    safe_error: str | None = None
    items: list[Any] = Field(default_factory=list)
