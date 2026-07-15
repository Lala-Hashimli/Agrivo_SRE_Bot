from __future__ import annotations

import asyncio
import json
from pathlib import Path

from pydantic import ValidationError

from app.models.health import SystemSnapshot
from app.telemetry import MOCK_SCENARIO_INFO


class MockScenarioError(RuntimeError):
    pass


class MockService:
    def __init__(self, fixture_directory: Path, scenario: str) -> None:
        self.fixture_directory = fixture_directory
        self.scenario = scenario
        self._snapshot: SystemSnapshot | None = None

    async def get_snapshot(self, *, refresh: bool = False) -> SystemSnapshot:
        if self._snapshot is None or refresh:
            self._snapshot = await asyncio.to_thread(self._load_sync)
        return self._snapshot.model_copy(deep=True)

    def _load_sync(self) -> SystemSnapshot:
        fixture = (self.fixture_directory / f"{self.scenario}.json").resolve()
        root = self.fixture_directory.resolve()
        if root not in fixture.parents or not fixture.is_file():
            raise MockScenarioError(f"Mock scenario '{self.scenario}' is not available")
        try:
            payload = json.loads(fixture.read_text(encoding="utf-8"))
            snapshot = SystemSnapshot.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as error:
            raise MockScenarioError(
                f"Mock scenario '{self.scenario}' could not be loaded"
            ) from error
        MOCK_SCENARIO_INFO.labels(scenario=self.scenario).set(1)
        return snapshot
