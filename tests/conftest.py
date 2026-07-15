from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def settings(tmp_path: Path, project_root: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        bot_data_mode="mock",
        mock_scenario="healthy-system",
        mock_data_dir=project_root / "mock-data",
        database_path=tmp_path / "state.db",
        telegram_bot_token=None,
        telegram_allowed_user_ids=[],
        telegram_allowed_chat_ids=[],
        gemini_api_key=None,
    )
