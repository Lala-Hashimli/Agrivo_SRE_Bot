from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ObservationStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "mock"
    available: bool
    observed_at: datetime | None = None
    status: ObservationStatus = ObservationStatus.UNKNOWN
    safe_error: str | None = None
