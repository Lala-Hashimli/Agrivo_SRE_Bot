from __future__ import annotations

import asyncio
from dataclasses import dataclass

import structlog
from google import genai
from google.genai import types

from app.config import Settings
from app.telemetry import (
    AI_FAILURES_TOTAL,
    AI_REQUEST_DURATION_SECONDS,
    AI_REQUESTS_TOTAL,
)
from app.utils.sanitization import sanitize_text

LOGGER = structlog.get_logger(__name__)

SYSTEM_INSTRUCTION = """You are Agrivo SRE Assistant.

You help a junior DevOps team understand Azure, Kubernetes, Docker, GitHub
Actions, Argo CD, Prometheus, Grafana, Alertmanager, PostgreSQL, Node.js, and
incident response.

Clearly distinguish confirmed facts from general guidance.
Do not invent live system information.
If live data was not supplied, explicitly say that the response is general guidance.
Prefer safe diagnostic actions.
Do not recommend destructive actions without a warning.
Do not request or expose secrets.
"""


@dataclass(frozen=True)
class AIAnswer:
    available: bool
    text: str | None = None
    error_category: str | None = None


class AIService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = (
            genai.Client(api_key=settings.gemini_api_key)
            if settings.ai_configured
            else None
        )

    @property
    def configured(self) -> bool:
        return self._client is not None

    async def ask(self, question: str) -> AIAnswer:
        if not self.configured:
            return AIAnswer(available=False, error_category="not_configured")
        if not question.strip() or len(question) > self.settings.ai_max_question_length:
            return AIAnswer(available=False, error_category="invalid_input")

        sanitized = sanitize_text(
            question, max_length=self.settings.ai_max_question_length
        )
        AI_REQUESTS_TOTAL.inc()
        client = self._client
        if client is None:
            return AIAnswer(available=False, error_category="not_configured")
        try:
            with AI_REQUEST_DURATION_SECONDS.time():
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=self.settings.gemini_model,
                        contents=sanitized,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            temperature=0.2,
                            max_output_tokens=700,
                        ),
                    ),
                    timeout=self.settings.http_timeout_seconds,
                )
            text = sanitize_text(response.text or "", max_length=3500)
            if not text:
                raise ValueError("Gemini returned an empty response")
            return AIAnswer(available=True, text=text)
        except TimeoutError:
            AI_FAILURES_TOTAL.labels(category="timeout").inc()
            LOGGER.warning("ai_request_failed", error_category="timeout")
            return AIAnswer(available=False, error_category="timeout")
        except Exception:
            AI_FAILURES_TOTAL.labels(category="provider_error").inc()
            LOGGER.exception("ai_request_failed", error_category="provider_error")
            return AIAnswer(available=False, error_category="provider_error")
