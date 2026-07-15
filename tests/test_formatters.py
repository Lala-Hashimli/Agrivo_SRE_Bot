from app.bot.formatters import format_status
from app.dependencies import Localizer
from app.models.health import OverallStatus
from app.services.mock_service import MockService
from app.utils.telegram_text import escape_html, split_message


def test_long_telegram_message_is_split_safely() -> None:
    value = ("Agrivo backend status is healthy.\n" * 300).strip()
    chunks = split_message(value)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 4096 for chunk in chunks)
    assert "".join(chunks).replace("\n", "") == value.replace("\n", "")


def test_html_is_escaped() -> None:
    assert escape_html("<b>Agrivo & SRE</b>") == "&lt;b&gt;Agrivo &amp; SRE&lt;/b&gt;"


async def test_status_uses_azerbaijan_time_and_marks_mock_data(settings) -> None:  # type: ignore[no-untyped-def]
    snapshot = await MockService(
        settings.mock_data_dir, "healthy-system"
    ).get_snapshot()
    message = format_status(snapshot, OverallStatus.OPERATIONAL, Localizer(), "en")
    assert "14 July 2026, 16:00 AZT" in message
    assert "Mock data: no live Agrivo" in message
