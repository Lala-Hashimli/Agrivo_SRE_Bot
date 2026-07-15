from __future__ import annotations

from typing import Protocol

from app.config import Settings
from app.models.health import SystemSnapshot
from app.services.mock_service import MockService
from app.services.operations_service import OperationsService
from app.services.real_service import RealService


class DataService(Protocol):
    async def get_snapshot(self, *, refresh: bool = False) -> SystemSnapshot: ...


def create_data_service(
    settings: Settings, operations: OperationsService
) -> DataService:
    if settings.bot_data_mode == "real":
        return RealService(settings, operations)
    return MockService(settings.mock_data_dir, settings.mock_scenario)
