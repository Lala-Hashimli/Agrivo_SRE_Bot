from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from app.config import Settings
from app.dependencies import RuntimeDependencies
from app.telemetry import UNAUTHORIZED_REQUESTS_TOTAL

LOGGER = structlog.get_logger(__name__)


def is_authorized(settings: Settings, user_id: int | None, chat_id: int | None) -> bool:
    if (
        not settings.telegram_allowed_user_ids
        and not settings.telegram_allowed_chat_ids
    ):
        return settings.app_env != "production"
    user_allowed = user_id is not None and user_id in settings.telegram_allowed_user_ids
    chat_allowed = chat_id is not None and chat_id in settings.telegram_allowed_chat_ids
    return user_allowed or chat_allowed


Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]


def authorized(handler: Handler) -> Handler:
    @wraps(handler)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any
    ) -> None:
        runtime: RuntimeDependencies = context.application.bot_data["runtime"]
        user_id = update.effective_user.id if update.effective_user else None
        chat_id = update.effective_chat.id if update.effective_chat else None
        if not is_authorized(runtime.settings, user_id, chat_id):
            UNAUTHORIZED_REQUESTS_TOTAL.inc()
            LOGGER.warning("telegram_access_denied", user_id=user_id, chat_id=chat_id)
            language = (
                await runtime.state_repository.get_language(user_id)
                if user_id is not None
                else "en"
            )
            if update.effective_message:
                await update.effective_message.reply_text(
                    runtime.localizer.text(language, "access_denied")
                )
            return
        if user_id is not None:
            await runtime.state_repository.touch_user(user_id)
        await handler(update, context, *args, **kwargs)

    return wrapper
