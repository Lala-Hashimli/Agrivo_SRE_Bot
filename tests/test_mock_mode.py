import pytest

from app.services.mock_service import MockScenarioError, MockService


async def test_healthy_mock_scenario_parses(settings) -> None:  # type: ignore[no-untyped-def]
    snapshot = await MockService(
        settings.mock_data_dir, "healthy-system"
    ).get_snapshot()
    assert snapshot.scenario == "healthy-system"
    assert snapshot.components["backend"].available
    assert snapshot.components["kubernetes"].running_pods == 6


async def test_invalid_mock_scenario_is_safe(settings) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(MockScenarioError, match="is not available"):
        await MockService(settings.mock_data_dir, "../../secret").get_snapshot()
