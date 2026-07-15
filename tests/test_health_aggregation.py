from app.models.health import OverallStatus
from app.services.health_service import HealthService
from app.services.mock_service import MockService


async def test_healthy_snapshot_is_operational(settings) -> None:  # type: ignore[no-untyped-def]
    snapshot = await MockService(
        settings.mock_data_dir, "healthy-system"
    ).get_snapshot()
    assert HealthService().overall_status(snapshot) == OverallStatus.OPERATIONAL


async def test_database_unavailable_is_critical(settings) -> None:  # type: ignore[no-untyped-def]
    snapshot = await MockService(
        settings.mock_data_dir, "database-unavailable"
    ).get_snapshot()
    assert HealthService().overall_status(snapshot) == OverallStatus.CRITICAL


async def test_resolved_alert_does_not_degrade_platform(settings) -> None:  # type: ignore[no-untyped-def]
    snapshot = await MockService(
        settings.mock_data_dir, "resolved-incident"
    ).get_snapshot()
    assert HealthService().overall_status(snapshot) == OverallStatus.OPERATIONAL
