from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_liveness_and_readiness_work_without_telegram(settings) -> None:  # type: ignore[no-untyped-def]
    with TestClient(create_app(settings)) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")
        health = client.get("/health")
        assert live.status_code == 200
        assert ready.status_code == 200
        assert health.status_code == 200
        assert health.json()["telegram_configured"] is False
        assert health.json()["status"] == "healthy"


def test_metrics_are_exposed(settings) -> None:  # type: ignore[no-untyped-def]
    with TestClient(create_app(settings)) as client:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "agrivo_sre_bot_commands_total" in response.text
        assert "agrivo_sre_bot_health_score" in response.text


def test_invalid_mock_scenario_fails_readiness_safely(
    tmp_path: Path, project_root: Path
) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        bot_data_mode="mock",
        mock_scenario="does-not-exist",
        mock_data_dir=project_root / "mock-data",
        database_path=tmp_path / "invalid.db",
        telegram_bot_token=None,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        payload = response.json()
        assert payload["status"] == "not_ready"
        assert payload["checks"]["data_source"] is False
        assert "does-not-exist" not in response.text
