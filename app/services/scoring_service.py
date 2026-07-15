from __future__ import annotations

from app.models.common import ObservationStatus
from app.models.health import DoctorResult, SystemSnapshot
from app.telemetry import HEALTH_SCORE


class ScoringService:
    WEIGHTS = {
        "frontend": 10,
        "backend": 15,
        "database": 15,
        "kubernetes": 15,
        "prometheus": 10,
        "grafana": 5,
        "alertmanager": 5,
        "argocd": 10,
        "alerts": 10,
        "deployment": 5,
    }

    def calculate(self, snapshot: SystemSnapshot) -> DoctorResult:
        score = 0
        covered = 0
        deductions: list[str] = []

        for name in (
            "frontend",
            "backend",
            "database",
            "kubernetes",
            "prometheus",
            "grafana",
            "alertmanager",
        ):
            weight = self.WEIGHTS[name]
            component = snapshot.components.get(name)
            if component is None or not component.available:
                deductions.append(f"{name.title()} data is unavailable: -{weight}")
                continue
            covered += weight
            if component.status == ObservationStatus.HEALTHY:
                score += weight
            elif component.status == ObservationStatus.DEGRADED:
                partial = weight // 2
                score += partial
                deductions.append(f"{name.title()} is degraded: -{weight - partial}")
            else:
                deductions.append(f"{name.title()} is unhealthy: -{weight}")

        argocd_weight = self.WEIGHTS["argocd"]
        argocd = snapshot.components.get("argocd")
        if argocd is None or not argocd.available:
            deductions.append(f"Argo CD data is unavailable: -{argocd_weight}")
        else:
            covered += argocd_weight
            if (
                argocd.status == ObservationStatus.HEALTHY
                and (argocd.sync_status or "").lower() == "synced"
            ):
                score += argocd_weight
            else:
                deductions.append(
                    f"Argo CD is not healthy and synced: -{argocd_weight}"
                )

        alert_weight = self.WEIGHTS["alerts"]
        covered += alert_weight
        critical = any(
            alert.status.lower() == "firing" and alert.severity.lower() == "critical"
            for alert in snapshot.active_alerts
        )
        if not critical:
            score += alert_weight
        else:
            deductions.append(f"A critical alert is active: -{alert_weight}")

        deployment_weight = self.WEIGHTS["deployment"]
        if not snapshot.deployment.available:
            deductions.append(f"Deployment data is unavailable: -{deployment_weight}")
        else:
            covered += deployment_weight
            if (
                snapshot.deployment.status.lower()
                in {"success", "successful", "healthy"}
                and (snapshot.deployment.argocd_sync_status or "").lower() == "synced"
            ):
                score += deployment_weight
            else:
                deductions.append(
                    "Last deployment is not successful and synced: "
                    f"-{deployment_weight}"
                )

        HEALTH_SCORE.set(score)
        coverage = round(covered / sum(self.WEIGHTS.values()) * 100)
        if score >= 90:
            recommendation = (
                "Platform signals are healthy; continue routine monitoring."
            )
        elif score >= 70:
            recommendation = "Review degraded components and active alerts."
        else:
            recommendation = (
                "Investigate critical components before the next deployment."
            )
        return DoctorResult(
            score=score,
            coverage_percent=coverage,
            deductions=deductions or ["No points deducted."],
            recommendation=recommendation,
        )
