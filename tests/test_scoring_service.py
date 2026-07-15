from app.services.mock_service import MockService
from app.services.scoring_service import ScoringService


async def test_doctor_score_is_deterministic(settings) -> None:  # type: ignore[no-untyped-def]
    snapshot = await MockService(
        settings.mock_data_dir, "healthy-system"
    ).get_snapshot()
    first = ScoringService().calculate(snapshot)
    second = ScoringService().calculate(snapshot)
    assert first == second
    assert first.score == 100
    assert first.coverage_percent == 100


async def test_missing_data_reduces_coverage(settings) -> None:  # type: ignore[no-untyped-def]
    snapshot = await MockService(
        settings.mock_data_dir, "healthy-system"
    ).get_snapshot()
    snapshot.components["prometheus"].available = False
    snapshot.components["prometheus"].safe_error = "Data source unavailable."
    result = ScoringService().calculate(snapshot)
    assert result.score == 90
    assert result.coverage_percent == 90
    assert any("Prometheus data is unavailable" in item for item in result.deductions)
