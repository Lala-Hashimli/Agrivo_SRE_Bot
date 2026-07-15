from app.services.ai_service import AIService
from app.utils.sanitization import REDACTED, sanitize_text


async def test_gemini_disabled_returns_fallback_state(settings) -> None:  # type: ignore[no-untyped-def]
    answer = await AIService(settings).ask("Why is the backend slow?")
    assert not answer.available
    assert answer.error_category == "not_configured"


def test_sensitive_information_is_redacted() -> None:
    raw = (
        "Authorization: Bearer secret-token-123 password=hunter2 "
        "postgresql://admin:secret@database:5432/agrivo "
        "buyer@example.com +994501234567"
    )
    sanitized = sanitize_text(raw)
    assert sanitized.count(REDACTED) >= 5
    assert "hunter2" not in sanitized
    assert "admin:secret" not in sanitized
    assert "buyer@example.com" not in sanitized
    assert "+994501234567" not in sanitized
