from __future__ import annotations

from app.models.common import ObservationStatus
from app.models.health import OverallStatus, SystemSnapshot


class HealthService:
    CRITICAL_COMPONENTS = {"backend", "database"}

    def overall_status(self, snapshot: SystemSnapshot) -> OverallStatus:
        available = [item for item in snapshot.components.values() if item.available]
        if not available:
            return OverallStatus.UNKNOWN

        for name in self.CRITICAL_COMPONENTS:
            component = snapshot.components.get(name)
            if component is None or not component.available:
                return OverallStatus.CRITICAL
            if component.status == ObservationStatus.UNHEALTHY:
                return OverallStatus.CRITICAL

        if any(
            alert.status.lower() == "firing" and alert.severity.lower() == "critical"
            for alert in snapshot.active_alerts
        ):
            return OverallStatus.CRITICAL
        if snapshot.deployment.available and snapshot.deployment.status.lower() in {
            "failed",
            "failure",
        }:
            return OverallStatus.CRITICAL

        if any(
            not component.available
            or component.status
            in {ObservationStatus.DEGRADED, ObservationStatus.UNHEALTHY}
            for component in snapshot.components.values()
        ):
            return OverallStatus.DEGRADED
        if any(alert.status.lower() == "firing" for alert in snapshot.active_alerts):
            return OverallStatus.DEGRADED
        return OverallStatus.OPERATIONAL
