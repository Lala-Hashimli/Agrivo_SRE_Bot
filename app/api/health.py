from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.dependencies import RuntimeDependencies

router = APIRouter()


def _runtime(request: Request) -> RuntimeDependencies:
    return cast(RuntimeDependencies, request.app.state.runtime)


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    runtime = _runtime(request)
    ready = runtime.storage_ready and runtime.data_ready
    if runtime.settings.telegram_configured:
        ready = ready and runtime.telegram_initialized
    return {
        "application": "Agrivo SRE Assistant",
        "environment": runtime.settings.app_env,
        "data_mode": runtime.settings.bot_data_mode,
        "telegram_configured": runtime.settings.telegram_configured,
        "ai_configured": runtime.settings.ai_configured,
        "status": "healthy" if ready else "degraded",
    }


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive", "service": "agrivo-sre-bot"}


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    runtime = _runtime(request)
    storage_ready = await runtime.state_repository.ping()
    telegram_ready = (
        runtime.telegram_initialized if runtime.settings.telegram_configured else True
    )
    is_ready = storage_ready and runtime.data_ready and telegram_ready
    payload = {
        "status": "ready" if is_ready else "not_ready",
        "service": "agrivo-sre-bot",
        "checks": {
            "configuration": True,
            "sqlite": storage_ready,
            "data_source": runtime.data_ready,
            "telegram": telegram_ready,
        },
    }
    return JSONResponse(
        payload,
        status_code=(
            status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
    )
