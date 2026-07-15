from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from telegram.ext import Application

from app.api.routes import router
from app.bot.application import build_telegram_application
from app.config import Settings, get_settings
from app.dependencies import create_runtime
from app.logging_config import configure_logging

LOGGER = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    selected_settings = settings or get_settings()
    configure_logging(selected_settings.log_level)
    runtime = create_runtime(selected_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        telegram_application: Application[Any, Any, Any, Any, Any, Any] | None = None
        try:
            await runtime.state_repository.initialize()
            runtime.storage_ready = await runtime.state_repository.ping()
        except Exception:
            runtime.startup_errors.append("state_storage_unavailable")
            LOGGER.exception("state_storage_initialization_failed")

        try:
            await runtime.data_service.get_snapshot(refresh=True)
            runtime.data_ready = True
        except Exception:
            runtime.startup_errors.append("data_source_unavailable")
            LOGGER.exception("data_source_initialization_failed")

        if selected_settings.telegram_configured:
            try:
                telegram_application = build_telegram_application(runtime)
                await telegram_application.initialize()
                await telegram_application.start()
                if telegram_application.updater is None:
                    raise RuntimeError("Telegram updater is unavailable")
                await telegram_application.updater.start_polling(
                    drop_pending_updates=False
                )
                runtime.telegram_initialized = True
                LOGGER.info("telegram_polling_started")
            except Exception:
                runtime.startup_errors.append("telegram_initialization_failed")
                LOGGER.exception(
                    "telegram_initialization_failed", error_category="provider_error"
                )
        else:
            LOGGER.warning(
                "telegram_not_configured",
                detail="FastAPI remains available; Telegram polling is disabled",
            )

        if (
            not selected_settings.telegram_allowed_user_ids
            and not selected_settings.telegram_allowed_chat_ids
        ):
            LOGGER.warning(
                "telegram_allowlist_empty",
                detail="All Telegram users are allowed outside production",
            )
        yield

        await runtime.operations_service.close()

        if telegram_application is not None:
            try:
                if (
                    telegram_application.updater
                    and telegram_application.updater.running
                ):
                    await telegram_application.updater.stop()
                if telegram_application.running:
                    await telegram_application.stop()
                await telegram_application.shutdown()
            except Exception:
                LOGGER.exception("telegram_shutdown_failed")

    application = FastAPI(
        title="Agrivo SRE Assistant",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.runtime = runtime
    application.include_router(router)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104 - container service must accept external traffic
        port=8085,
        reload=False,
    )
