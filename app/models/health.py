from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.common import Observation


class OverallStatus(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ComponentObservation(Observation):
    latency_ms: float | None = Field(default=None, ge=0)
    sync_status: str | None = None
    running_pods: int | None = Field(default=None, ge=0)
    pending_pods: int | None = Field(default=None, ge=0)
    failed_pods: int | None = Field(default=None, ge=0)
    restarts_last_hour: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def unavailable_has_no_measurements(self) -> ComponentObservation:
        if not self.available and self.safe_error is None:
            self.safe_error = "Data source unavailable."
        return self


class AlertObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "mock"
    available: bool = True
    observed_at: datetime | None = None
    safe_error: str | None = None
    name: str
    severity: str
    status: str = "firing"
    service: str | None = None
    description: str
    started_at: datetime | None = None


class MetricObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "mock"
    available: bool = True
    observed_at: datetime | None = None
    status: str = "available"
    safe_error: str | None = None
    backend_p95_latency_ms: float | None = Field(default=None, ge=0)
    backend_error_rate_percent: float | None = Field(default=None, ge=0)
    backend_cpu_percent: float | None = Field(default=None, ge=0)
    backend_memory_percent: float | None = Field(default=None, ge=0)


class DeploymentObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "mock"
    available: bool = True
    status: str
    component: str | None = None
    commit_sha: str | None = None
    image_tag: str | None = None
    argocd_sync_status: str | None = None
    observed_at: datetime | None = None
    safe_error: str | None = None


class SystemSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: str
    source: str = "mock"
    available: bool = True
    status: str = "available"
    safe_error: str | None = None
    observed_at: datetime
    environment: str
    components: dict[str, ComponentObservation]
    active_alerts: list[AlertObservation] = Field(default_factory=list)
    metrics: MetricObservation = Field(default_factory=MetricObservation)
    deployment: DeploymentObservation


class DoctorResult(BaseModel):
    score: int = Field(ge=0, le=100)
    coverage_percent: int = Field(ge=0, le=100)
    deductions: list[str]
    recommendation: str
