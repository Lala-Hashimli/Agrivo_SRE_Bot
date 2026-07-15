from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

from app.config import Settings
from app.models.common import ObservationStatus
from app.models.health import (
    AlertObservation,
    ComponentObservation,
    DeploymentObservation,
    MetricObservation,
    SystemSnapshot,
)
from app.models.operations import MetricSummary, OperationResult
from app.services.operations_service import OperationsService


class RealService:
    def __init__(self, settings: Settings, operations: OperationsService) -> None:
        self.settings = settings
        self.operations = operations

    async def get_snapshot(self, *, refresh: bool = False) -> SystemSnapshot:
        del refresh
        now = datetime.now(UTC)
        (
            frontend,
            backend,
            ready,
            metrics,
            alerts,
            pods,
            deployments,
            argo,
        ) = await asyncio.gather(
            self.operations.probe(self.settings.agrivo_frontend_url),
            self.operations.probe(self.settings.agrivo_backend_health_url),
            self.operations.probe(self.settings.agrivo_backend_ready_url),
            self.operations.metrics(),
            self.operations.alerts(),
            self.operations.pods(),
            self.operations.deployments(),
            self.operations.argocd_apps(),
        )
        frontend = cast(tuple[bool, float, dict[str, Any] | None], frontend)
        backend = cast(tuple[bool, float, dict[str, Any] | None], backend)
        ready = cast(tuple[bool, float, dict[str, Any] | None], ready)
        metrics = cast(MetricSummary, metrics)
        alerts = cast(OperationResult, alerts)
        pods = cast(OperationResult, pods)
        deployments = cast(OperationResult, deployments)
        argo = cast(OperationResult, argo)
        components: dict[str, ComponentObservation] = {
            "frontend": self._probe_component(frontend, now),
            "backend": self._probe_component(backend, now),
            "database": self._database_component(ready, now),
            "prometheus": await self._url_component(
                self.settings.prometheus_url, "-/healthy", now
            ),
            "grafana": await self._url_component(
                self.settings.grafana_url, "api/health", now
            ),
            "alertmanager": await self._url_component(
                self.settings.alertmanager_url, "-/healthy", now
            ),
        }
        components["kubernetes"] = self._kubernetes_component(pods, now)
        components["argocd"] = self._argocd_component(argo, now)

        alert_models = (
            [
                AlertObservation(
                    source="alertmanager",
                    observed_at=now,
                    name=item.name,
                    severity=item.severity,
                    status=item.status,
                    service=item.service,
                    description=item.description,
                    started_at=item.started_at,
                )
                for item in alerts.items
            ]
            if alerts.available
            else []
        )
        deployment_items = deployments.items
        deployment_ok = bool(deployment_items) and all(
            item.available >= item.desired for item in deployment_items
        )
        deployment = DeploymentObservation(
            source="kubernetes",
            available=deployments.available,
            status="successful"
            if deployment_ok
            else "degraded"
            if deployments.available
            else "unknown",
            image_tag=deployment_items[0].image if deployment_items else None,
            observed_at=now,
            safe_error=deployments.safe_error,
        )
        return SystemSnapshot(
            scenario="live",
            source="real",
            observed_at=now,
            environment=self.settings.app_env,
            components=components,
            active_alerts=alert_models,
            metrics=MetricObservation(
                source="prometheus",
                available=metrics.available,
                observed_at=metrics.observed_at,
                status="available" if metrics.available else "unavailable",
                safe_error=metrics.safe_error,
                backend_p95_latency_ms=metrics.p95_latency_ms,
                backend_error_rate_percent=metrics.error_rate_percent,
                backend_cpu_percent=metrics.cpu_percent,
            ),
            deployment=deployment,
        )

    @staticmethod
    def _probe_component(
        result: tuple[bool, float, dict[str, Any] | None], now: datetime
    ) -> ComponentObservation:
        ok, latency, _ = result
        return ComponentObservation(
            source="http",
            available=True,
            observed_at=now,
            status=ObservationStatus.HEALTHY if ok else ObservationStatus.UNHEALTHY,
            latency_ms=latency,
            safe_error=None if ok else "HTTP probe failed.",
        )

    @staticmethod
    def _database_component(
        result: tuple[bool, float, dict[str, Any] | None], now: datetime
    ) -> ComponentObservation:
        ok, latency, payload = result
        connected = (
            ok
            and payload is not None
            and str(payload.get("database", "")).lower() == "connected"
        )
        return ComponentObservation(
            source="backend-readiness",
            available=True,
            observed_at=now,
            status=ObservationStatus.HEALTHY
            if connected
            else ObservationStatus.UNHEALTHY,
            latency_ms=latency,
            safe_error=None
            if connected
            else "Backend readiness does not report a connected database.",
        )

    async def _url_component(
        self, base: str | None, path: str, now: datetime
    ) -> ComponentObservation:
        if not base:
            return ComponentObservation(
                source="http",
                available=False,
                observed_at=now,
                safe_error="URL is not configured.",
            )
        url = f"{base.rstrip('/')}/{path.lstrip('/')}"
        ok, latency, _ = await self.operations.probe(url)
        return ComponentObservation(
            source="http",
            available=True,
            observed_at=now,
            status=ObservationStatus.HEALTHY if ok else ObservationStatus.UNHEALTHY,
            latency_ms=latency,
            safe_error=None if ok else "Health endpoint is unreachable.",
        )

    @staticmethod
    def _kubernetes_component(result: object, now: datetime) -> ComponentObservation:
        available = getattr(result, "available", False)
        items = getattr(result, "items", [])
        if not available:
            return ComponentObservation(
                source="kubernetes",
                available=False,
                observed_at=now,
                safe_error=getattr(result, "safe_error", None),
            )
        failed = sum(item.phase not in {"Running", "Succeeded"} for item in items)
        restarts = sum(item.restarts for item in items)
        return ComponentObservation(
            source="kubernetes",
            available=True,
            observed_at=now,
            status=ObservationStatus.HEALTHY
            if failed == 0
            else ObservationStatus.DEGRADED,
            running_pods=sum(item.phase == "Running" for item in items),
            failed_pods=failed,
            pending_pods=sum(item.phase == "Pending" for item in items),
            restarts_last_hour=restarts,
        )

    @staticmethod
    def _argocd_component(result: object, now: datetime) -> ComponentObservation:
        available = getattr(result, "available", False)
        items = getattr(result, "items", [])
        if not available:
            return ComponentObservation(
                source="argocd",
                available=False,
                observed_at=now,
                safe_error=getattr(result, "safe_error", None),
            )
        healthy = bool(items) and all(
            item.sync == "Synced" and item.health == "Healthy" for item in items
        )
        sync = "Synced" if healthy else "OutOfSync" if items else "No applications"
        return ComponentObservation(
            source="argocd",
            available=True,
            observed_at=now,
            status=ObservationStatus.HEALTHY if healthy else ObservationStatus.DEGRADED,
            sync_status=sync,
        )
