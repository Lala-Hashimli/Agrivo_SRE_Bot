from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import Settings
from app.repositories.state_repository import StateRepository
from app.services.ai_service import AIService
from app.services.health_service import HealthService
from app.services.operations_service import OperationsService
from app.services.scoring_service import ScoringService
from app.services.service_factory import DataService, create_data_service


class Localizer:
    def __init__(self, locale_directory: Path | None = None) -> None:
        directory = locale_directory or Path(__file__).resolve().parent / "locales"
        self._messages: dict[str, dict[str, Any]] = {}
        for language in ("en", "az"):
            with (directory / f"{language}.json").open(encoding="utf-8") as stream:
                self._messages[language] = json.load(stream)

    def text(self, language: str, key: str, **values: object) -> str:
        selected = self._messages.get(language, self._messages["en"])
        value: Any = selected
        for part in key.split("."):
            value = value[part]
        return str(value).format(**values)


@dataclass
class RuntimeDependencies:
    settings: Settings
    state_repository: StateRepository
    data_service: DataService
    operations_service: OperationsService
    health_service: HealthService
    scoring_service: ScoringService
    ai_service: AIService
    localizer: Localizer
    storage_ready: bool = False
    data_ready: bool = False
    telegram_initialized: bool = False
    startup_errors: list[str] = field(default_factory=list)


def create_runtime(settings: Settings) -> RuntimeDependencies:
    operations = OperationsService(settings)
    return RuntimeDependencies(
        settings=settings,
        state_repository=StateRepository(settings.database_path),
        data_service=create_data_service(settings, operations),
        operations_service=operations,
        health_service=HealthService(),
        scoring_service=ScoringService(),
        ai_service=AIService(settings),
        localizer=Localizer(),
    )
