from __future__ import annotations

import asyncio
import io
import json
import math
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings
from app.models.operations import (
    AlertInfo,
    ArgoApplicationInfo,
    DeploymentInfo,
    HpaInfo,
    MetricSummary,
    OperationResult,
    PodInfo,
    WorkflowInfo,
)


class OperationsService:
    """Read-only adapters for Agrivo's operational data sources."""

    def __init__(
        self, settings: Settings, client: httpx.AsyncClient | None = None
    ) -> None:
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=settings.http_timeout_seconds, follow_redirects=True
        )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _json(self, url: str, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.settings.http_max_retries + 1):
            try:
                response = await self.client.get(url, **kwargs)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
                if attempt < self.settings.http_max_retries:
                    await asyncio.sleep(min(0.2 * (2**attempt), 1.0))
        raise RuntimeError(
            type(last_error).__name__ if last_error else "request_failed"
        )

    async def probe(self, url: str) -> tuple[bool, float, dict[str, Any] | None]:
        started = time.monotonic()
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            payload = (
                response.json()
                if "json" in response.headers.get("content-type", "")
                else None
            )
            return True, round((time.monotonic() - started) * 1000, 1), payload
        except (httpx.HTTPError, ValueError):
            return False, round((time.monotonic() - started) * 1000, 1), None

    async def prometheus_query(self, query: str) -> float | None:
        if not self.settings.prometheus_url:
            return None
        payload = await self._json(
            urljoin(self.settings.prometheus_url.rstrip("/") + "/", "api/v1/query"),
            params={"query": query},
        )
        results = payload.get("data", {}).get("result", [])
        if not results:
            return None
        try:
            value = float(results[0]["value"][1])
            return value if math.isfinite(value) else None
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    async def metrics(self) -> MetricSummary:
        now = datetime.now(UTC)
        queries = {
            "request_rate": "sum(rate(agrivo_backend_http_requests_total[5m]))",
            "error_rate_percent": '100 * sum(rate(agrivo_backend_http_requests_total{status_code=~"5.."}[5m])) / clamp_min(sum(rate(agrivo_backend_http_requests_total[5m])), 0.001)',
            "p95_latency_ms": "1000 * histogram_quantile(0.95, sum by (le) (rate(agrivo_backend_http_request_duration_seconds_bucket[5m])))",
            "cpu_percent": "100 * rate(agrivo_backend_process_cpu_seconds_total[5m])",
            "memory_mib": "agrivo_backend_process_resident_memory_bytes / 1024 / 1024",
            "event_loop_p99_ms": "1000 * agrivo_backend_nodejs_eventloop_lag_p99_seconds",
        }
        if not self.settings.prometheus_url:
            return MetricSummary(
                observed_at=now,
                available=False,
                safe_error="PROMETHEUS_URL is not configured.",
            )
        try:
            values = await asyncio.gather(
                *(self.prometheus_query(query) for query in queries.values())
            )
            return MetricSummary(
                observed_at=now, **dict(zip(queries, values, strict=True))
            )
        except RuntimeError:
            return MetricSummary(
                observed_at=now,
                available=False,
                safe_error="Prometheus is unreachable.",
            )

    async def chart(self, hours: int = 1) -> bytes | None:
        if not self.settings.prometheus_url:
            return None
        end = datetime.now(UTC)
        start = end - timedelta(hours=hours)
        url = urljoin(
            self.settings.prometheus_url.rstrip("/") + "/", "api/v1/query_range"
        )
        series_queries = {
            "CPU %": "100 * rate(agrivo_backend_process_cpu_seconds_total[5m])",
            "Memory MiB": "agrivo_backend_process_resident_memory_bytes / 1024 / 1024",
            "p95 latency ms": "1000 * histogram_quantile(0.95, sum by (le) (rate(agrivo_backend_http_request_duration_seconds_bucket[5m])))",
        }
        series: dict[str, list[tuple[datetime, float]]] = {}
        try:
            for label, query in series_queries.items():
                payload = await self._json(
                    url,
                    params={
                        "query": query,
                        "start": start.timestamp(),
                        "end": end.timestamp(),
                        "step": 60,
                    },
                )
                results = payload.get("data", {}).get("result", [])
                if results:
                    points = []
                    for raw_time, raw_value in results[0].get("values", []):
                        value = float(raw_value)
                        if math.isfinite(value):
                            points.append(
                                (datetime.fromtimestamp(float(raw_time), UTC), value)
                            )
                    if points:
                        series[label] = points
        except (RuntimeError, TypeError, ValueError):
            return None
        if not series:
            return None
        from matplotlib import pyplot as plt

        timezone = ZoneInfo(self.settings.display_timezone)
        figure, axes = plt.subplots(
            len(series), 1, figsize=(10, 2.6 * len(series)), squeeze=False
        )
        figure.suptitle(
            f"Agrivo ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ last {hours} hour(s) ({self.settings.display_timezone})"
        )
        for axis, (label, points) in zip(axes.flat, series.items(), strict=False):
            axis.plot(
                [point[0].astimezone(timezone) for point in points],
                [point[1] for point in points],
                color="#2e7d32",
                linewidth=2,
            )
            axis.set_ylabel(label)
            axis.grid(alpha=0.25)
        figure.tight_layout()
        output = io.BytesIO()
        figure.savefig(output, format="png", dpi=130)
        plt.close(figure)
        return output.getvalue()

    async def alerts(self) -> OperationResult:
        if not self.settings.alertmanager_url:
            return OperationResult(
                available=False, safe_error="ALERTMANAGER_URL is not configured."
            )
        try:
            payload = await self._json(
                urljoin(
                    self.settings.alertmanager_url.rstrip("/") + "/", "api/v2/alerts"
                ),
                params={"active": "true", "silenced": "false"},
            )
            items = [
                AlertInfo(
                    name=item.get("labels", {}).get("alertname", "Unnamed alert"),
                    severity=item.get("labels", {}).get("severity", "unknown"),
                    status=item.get("status", {}).get("state", "firing"),
                    description=item.get("annotations", {}).get(
                        "description",
                        item.get("annotations", {}).get("summary", "No description"),
                    ),
                    service=item.get("labels", {}).get("service"),
                    started_at=item.get("startsAt"),
                )
                for item in payload
            ]
            return OperationResult(items=items)
        except (RuntimeError, TypeError, ValueError):
            return OperationResult(
                available=False, safe_error="Alertmanager is unreachable."
            )

    async def _kubectl(self, resource: str) -> OperationResult:
        command = ["kubectl"]
        if self.settings.kubernetes_context:
            command.extend(["--context", self.settings.kubernetes_context])
        command.extend(
            ["get", resource, "-n", self.settings.active_namespace, "-o", "json"]
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(
                process.communicate(), timeout=self.settings.http_timeout_seconds
            )
            if process.returncode != 0:
                return OperationResult(
                    available=False,
                    safe_error=f"Kubernetes resource '{resource}' is unavailable.",
                )
            payload = json.loads(stdout.decode("utf-8"))
            return OperationResult(items=payload.get("items", []))
        except (FileNotFoundError, TimeoutError, json.JSONDecodeError):
            return OperationResult(
                available=False,
                safe_error="kubectl or Kubernetes context is unavailable.",
            )

    async def pods(self) -> OperationResult:
        raw = await self._kubectl("pods")
        if not raw.available:
            return raw
        items = []
        for pod in raw.items:
            statuses = pod.get("status", {}).get("containerStatuses", [])
            ready = sum(bool(item.get("ready")) for item in statuses)
            items.append(
                PodInfo(
                    name=pod["metadata"]["name"],
                    namespace=pod["metadata"]["namespace"],
                    phase=pod.get("status", {}).get("phase", "Unknown"),
                    ready=f"{ready}/{len(statuses)}",
                    restarts=sum(int(item.get("restartCount", 0)) for item in statuses),
                    node=pod.get("spec", {}).get("nodeName"),
                )
            )
        return OperationResult(items=items)

    async def deployments(self) -> OperationResult:
        raw = await self._kubectl("deployments")
        if not raw.available:
            return raw
        items = []
        for deployment in raw.items:
            spec, status = deployment.get("spec", {}), deployment.get("status", {})
            desired = int(spec.get("replicas", 0))
            containers = spec.get("template", {}).get("spec", {}).get("containers", [])
            image = containers[0].get("image") if containers else None
            items.append(
                DeploymentInfo(
                    name=deployment["metadata"]["name"],
                    namespace=deployment["metadata"]["namespace"],
                    ready=f"{status.get('readyReplicas', 0)}/{desired}",
                    available=int(status.get("availableReplicas", 0)),
                    desired=desired,
                    image=image,
                )
            )
        return OperationResult(items=items)

    async def hpas(self) -> OperationResult:
        raw = await self._kubectl("hpa")
        if not raw.available:
            return raw
        items = []
        for hpa in raw.items:
            spec, status = hpa.get("spec", {}), hpa.get("status", {})
            current = status.get("currentMetrics", [])
            metrics = (
                ", ".join(self._format_hpa_metric(metric) for metric in current)
                or "not reported"
            )
            reference = spec.get("scaleTargetRef", {})
            items.append(
                HpaInfo(
                    name=hpa["metadata"]["name"],
                    namespace=hpa["metadata"]["namespace"],
                    reference=f"{reference.get('kind', 'Deployment')}/{reference.get('name', '?')}",
                    current_replicas=int(status.get("currentReplicas", 0)),
                    min_replicas=int(spec.get("minReplicas", 1)),
                    max_replicas=int(spec.get("maxReplicas", 1)),
                    metrics=metrics,
                )
            )
        return OperationResult(items=items)

    @staticmethod
    def _format_hpa_metric(metric: dict[str, Any]) -> str:
        resource = metric.get("resource", {})
        current = resource.get("current", {})
        value = current.get("averageUtilization", current.get("averageValue", "?"))
        return f"{resource.get('name', metric.get('type', 'metric'))}: {value}"

    async def workflows(self) -> OperationResult:
        url = f"https://api.github.com/repos/{self.settings.github_owner}/{self.settings.github_repository}/actions/runs"
        headers = {"Accept": "application/vnd.github+json"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        try:
            payload = await self._json(url, headers=headers, params={"per_page": 10})
            items = [
                WorkflowInfo(
                    name=item.get("name", "Workflow"),
                    status=item.get("status", "unknown"),
                    conclusion=item.get("conclusion"),
                    branch=item.get("head_branch"),
                    sha=(item.get("head_sha") or "")[:7] or None,
                    url=item.get("html_url"),
                    created_at=item.get("created_at"),
                )
                for item in payload.get("workflow_runs", [])
            ]
            return OperationResult(items=items)
        except (RuntimeError, TypeError, ValueError):
            return OperationResult(
                available=False,
                safe_error="GitHub Actions is unreachable or unauthorized.",
            )

    async def argocd_apps(self) -> OperationResult:
        if not self.settings.argocd_url:
            return OperationResult(
                available=False, safe_error="ARGOCD_URL is not configured."
            )
        headers = (
            {"Authorization": f"Bearer {self.settings.argocd_token}"}
            if self.settings.argocd_token
            else {}
        )
        try:
            url = urljoin(
                self.settings.argocd_url.rstrip("/") + "/",
                "api/v1/applications",
            )
            if url.startswith("https://") and not self.settings.argocd_verify_tls:
                async with httpx.AsyncClient(
                    timeout=self.settings.http_timeout_seconds,
                    verify=False,  # noqa: S501 - explicit ARGOCD_VERIFY_TLS setting
                ) as argocd_client:
                    response = await argocd_client.get(url, headers=headers)
                    response.raise_for_status()
                    payload = response.json()
            else:
                payload = await self._json(url, headers=headers)
            items = [
                ArgoApplicationInfo(
                    name=item.get("metadata", {}).get("name", "unknown"),
                    sync=item.get("status", {})
                    .get("sync", {})
                    .get("status", "Unknown"),
                    health=item.get("status", {})
                    .get("health", {})
                    .get("status", "Unknown"),
                    revision=(
                        item.get("status", {}).get("sync", {}).get("revision") or ""
                    )[:7]
                    or None,
                )
                for item in payload.get("items", [])
            ]
            return OperationResult(items=items)
        except (httpx.HTTPError, RuntimeError, TypeError, ValueError):
            return OperationResult(
                available=False, safe_error="Argo CD is unreachable or unauthorized."
            )

    async def grafana_snapshot(self) -> bytes | None:
        dashboard = self.settings.grafana_dashboard_overview_url
        if not self.settings.grafana_render_enabled or not dashboard:
            return None
        render_url = dashboard.replace("/d/", "/render/d/", 1)
        headers = {}
        if self.settings.grafana_service_account_token:
            headers["Authorization"] = (
                f"Bearer {self.settings.grafana_service_account_token}"
            )
        try:
            response = await self.client.get(
                render_url,
                headers=headers,
                params={
                    "width": 1200,
                    "height": 700,
                    "tz": self.settings.display_timezone,
                },
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            return response.content if content_type.startswith("image/") else None
        except httpx.HTTPError:
            return None

    def grafana_links(self) -> list[tuple[str, str]]:
        configured = [
            ("Overview", self.settings.grafana_dashboard_overview_url),
            ("Backend", self.settings.grafana_dashboard_backend_url),
            ("Kubernetes", self.settings.grafana_dashboard_kubernetes_url),
            ("Incidents", self.settings.grafana_dashboard_incidents_url),
        ]
        return [(name, url) for name, url in configured if url]
