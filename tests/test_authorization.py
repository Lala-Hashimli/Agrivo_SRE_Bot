from pydantic import ValidationError

from app.bot.permissions import is_authorized
from app.config import Settings


def test_development_empty_allowlist_allows_users() -> None:
    settings = Settings(
        _env_file=None,
        app_env="development",
        telegram_allowed_user_ids=[],
        telegram_allowed_chat_ids=[],
    )
    assert is_authorized(settings, 123, 456)


def test_production_empty_allowlist_is_rejected() -> None:
    try:
        Settings(
            _env_file=None,
            app_env="production",
            telegram_allowed_user_ids=[],
            telegram_allowed_chat_ids=[],
        )
    except ValidationError as error:
        assert "Production requires" in str(error)
    else:
        raise AssertionError("Production settings accepted an empty allowlist")


def test_unauthorized_user_is_rejected() -> None:
    settings = Settings(
        _env_file=None,
        app_env="development",
        telegram_allowed_user_ids=[100],
        telegram_allowed_chat_ids=[200],
    )
    assert not is_authorized(settings, 101, 201)
    assert is_authorized(settings, 100, 999)
    assert is_authorized(settings, 999, 200)


def test_comma_separated_allowlists_are_parsed() -> None:
    settings = Settings(
        _env_file=None,
        telegram_allowed_user_ids="100, 200",
        telegram_allowed_chat_ids="-300",
        telegram_incident_chat_id="",
    )
    assert settings.telegram_allowed_user_ids == [100, 200]
    assert settings.telegram_allowed_chat_ids == [-300]
    assert settings.telegram_incident_chat_id is None


def test_env_example_is_valid(project_root) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(_env_file=project_root / ".env.example")
    assert settings.bot_data_mode == "mock"
    assert settings.telegram_allowed_user_ids == []
    assert settings.telegram_incident_chat_id is None
