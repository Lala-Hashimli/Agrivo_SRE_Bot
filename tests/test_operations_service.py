from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.services.operations_service import OperationsService
from app.services.real_service import RealService
from app.services.service_factory import create_data_service


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, http_max_retries=0, **values)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_prometheus_metrics_preserve_missing_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["query"]
        result = [] if "histogram_quantile" in query else [{"value": [1, "12.5"]}]
        return httpx.Response(
            200, json={"status": "success", "data": {"result": result}}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = OperationsService(_settings(prometheus_url="http://prometheus"), client)
    metrics = await service.metrics()

    assert metrics.available is True
    assert metrics.request_rate == 12.5
    assert metrics.p95_latency_ms is None
    await client.aclose()


@pytest.mark.asyncio
async def test_alertmanager_and_delivery_adapters_normalize_payloads() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/v2/alerts"):
            return httpx.Response(
                200,
                json=[
                    {
                        "labels": {
                            "alertname": "BackendDown",
                            "severity": "critical",
                            "service": "backend",
                        },
                        "annotations": {"summary": "Backend is unavailable"},
                        "status": {"state": "active"},
                        "startsAt": "2026-07-15T08:00:00Z",
                    }
                ],
            )
        if request.url.host == "api.github.com":
            return httpx.Response(
                200,
                json={
                    "workflow_runs": [
                        {
                            "name": "Deploy",
                            "status": "completed",
                            "conclusion": "success",
                            "head_branch": "main",
                            "head_sha": "abcdef123456",
                            "html_url": "https://example/run/1",
                            "created_at": "2026-07-15T08:00:00Z",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "metadata": {"name": "agrivo-backend-dev"},
                        "status": {
                            "sync": {"status": "Synced", "revision": "123456789"},
                            "health": {"status": "Healthy"},
                        },
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = _settings(
        alertmanager_url="http://alertmanager", argocd_url="http://argocd"
    )
    service = OperationsService(settings, client)

    alerts = await service.alerts()
    workflows = await service.workflows()
    apps = await service.argocd_apps()

    assert alerts.items[0].name == "BackendDown"
    assert workflows.items[0].sha == "abcdef1"
    assert apps.items[0].sync == "Synced"
    await client.aclose()


@pytest.mark.asyncio
async def test_factory_selects_real_service() -> None:
    settings = _settings(bot_data_mode="real")
    operations = OperationsService(settings, httpx.AsyncClient())
    service = create_data_service(settings, operations)
    assert isinstance(service, RealService)
    await operations.close()
    await operations.client.aclose()
