from __future__ import annotations

from typing import Any

from telegram.ext import Application, ApplicationBuilder

from app.bot.commands import register_handlers
from app.dependencies import RuntimeDependencies


def build_telegram_application(
    runtime: RuntimeDependencies,
) -> Application[Any, Any, Any, Any, Any, Any]:
    token = runtime.settings.telegram_bot_token
    if not token:
        raise ValueError("Telegram token is not configured")
    application = ApplicationBuilder().token(token).build()
    application.bot_data["runtime"] = runtime
    register_handlers(application)
    return application
