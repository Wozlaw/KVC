"""Settings tests."""

import pytest
from pydantic import SecretStr, ValidationError

from kvc_config import AppSettings
from kvc_persistence import DatabaseConfigurationError, create_async_engine_from_settings


def test_settings_load_without_real_secrets() -> None:
    settings = AppSettings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.database_url is None
    assert settings.database_echo is False
    assert settings.max_bot_token is None
    assert settings.max_api_base_url == "https://platform-api2.max.ru"
    assert settings.max_webhook_secret is None
    assert settings.max_webhook_path == "/max/webhook"
    assert settings.max_inbound_mode == "webhook"
    assert settings.max_allowed_update_types == (
        "message_created",
        "message_callback",
        "bot_started",
    )
    assert settings.max_polling_timeout_seconds == 60
    assert settings.max_polling_limit == 100
    assert settings.max_webhook_public_url is None
    assert settings.max_mini_app_public_url is None
    assert settings.max_mini_app_context_secret is None


def test_settings_load_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KVC_APP_ENV", "test")
    monkeypatch.setenv("KVC_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv(
        "KVC_DATABASE_URL",
        "postgresql+asyncpg://user:password@127.0.0.1:5432/kvc_test",
    )
    monkeypatch.setenv("KVC_DATABASE_ECHO", "true")

    settings = AppSettings()

    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.database_url is not None
    assert settings.database_url.get_secret_value().startswith("postgresql+asyncpg://")
    assert settings.database_echo is True


@pytest.mark.parametrize("app_env", ["development", "test", "production"])
def test_settings_allow_known_environment_values(
    app_env: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KVC_APP_ENV", app_env)

    assert AppSettings().app_env == app_env


def test_settings_reject_invalid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KVC_APP_ENV", "staging")

    with pytest.raises(ValidationError):
        AppSettings()


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
    ],
)
def test_database_echo_parses_boolean(
    raw_value: str,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KVC_DATABASE_ECHO", raw_value)

    assert AppSettings().database_echo is expected


def test_database_url_is_redacted_in_settings_repr() -> None:
    settings = AppSettings(
        database_url=SecretStr("postgresql+asyncpg://user:secret@127.0.0.1:5432/kvc_test")
    )

    assert "user:secret" not in repr(settings)
    assert "user:secret" not in str(settings)


def test_missing_database_url_does_not_break_app_import() -> None:
    from kvc_api import create_app

    assert create_app()


def test_creating_database_engine_without_url_raises_controlled_error() -> None:
    settings = AppSettings(database_url=None)

    with pytest.raises(DatabaseConfigurationError, match="KVC_DATABASE_URL"):
        create_async_engine_from_settings(settings)


def test_max_settings_load_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KVC_MAX_API_BASE_URL", "https://max.example.test")
    monkeypatch.setenv("KVC_MAX_WEBHOOK_PATH", "/custom/webhook")
    monkeypatch.setenv("KVC_MAX_INBOUND_MODE", "long_polling")
    monkeypatch.setenv("KVC_MAX_ALLOWED_UPDATE_TYPES", "message_created, bot_started")
    monkeypatch.setenv("KVC_MAX_POLLING_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("KVC_MAX_POLLING_LIMIT", "1000")
    monkeypatch.setenv("KVC_MAX_WEBHOOK_PUBLIC_URL", "https://kvc.example.test/max/webhook")
    monkeypatch.setenv("KVC_MAX_MINI_APP_PUBLIC_URL", "https://kvc.example.test/max/app")

    settings = AppSettings()

    assert settings.max_api_base_url == "https://max.example.test"
    assert settings.max_webhook_path == "/custom/webhook"
    assert settings.max_inbound_mode == "long_polling"
    assert settings.max_allowed_update_types == ("message_created", "bot_started")
    assert settings.max_polling_timeout_seconds == 90
    assert settings.max_polling_limit == 1000
    assert settings.max_webhook_public_url == "https://kvc.example.test/max/webhook"
    assert settings.max_mini_app_public_url == "https://kvc.example.test/max/app"


@pytest.mark.parametrize("inbound_mode", ["webhook", "long_polling"])
def test_max_inbound_mode_allows_known_values(
    inbound_mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KVC_MAX_INBOUND_MODE", inbound_mode)

    assert AppSettings().max_inbound_mode == inbound_mode


def test_max_inbound_mode_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KVC_MAX_INBOUND_MODE", "polling")

    with pytest.raises(ValidationError):
        AppSettings()


@pytest.mark.parametrize("timeout_seconds", [0, 90])
def test_max_polling_timeout_allows_bounds(
    timeout_seconds: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KVC_MAX_POLLING_TIMEOUT_SECONDS", str(timeout_seconds))

    assert AppSettings().max_polling_timeout_seconds == timeout_seconds


@pytest.mark.parametrize("timeout_seconds", [-1, 91])
def test_max_polling_timeout_rejects_out_of_range(
    timeout_seconds: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KVC_MAX_POLLING_TIMEOUT_SECONDS", str(timeout_seconds))

    with pytest.raises(ValidationError):
        AppSettings()


@pytest.mark.parametrize("limit", [1, 1000])
def test_max_polling_limit_allows_bounds(
    limit: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KVC_MAX_POLLING_LIMIT", str(limit))

    assert AppSettings().max_polling_limit == limit


@pytest.mark.parametrize("limit", [0, 1001])
def test_max_polling_limit_rejects_out_of_range(
    limit: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KVC_MAX_POLLING_LIMIT", str(limit))

    with pytest.raises(ValidationError):
        AppSettings()


def test_max_blank_secret_values_normalize_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KVC_MAX_BOT_TOKEN", "")
    monkeypatch.setenv("KVC_MAX_WEBHOOK_SECRET", "")
    monkeypatch.setenv("KVC_MAX_MINI_APP_CONTEXT_SECRET", "")
    monkeypatch.setenv("KVC_MAX_WEBHOOK_PUBLIC_URL", "")
    monkeypatch.setenv("KVC_MAX_MINI_APP_PUBLIC_URL", "")

    settings = AppSettings()

    assert settings.max_bot_token is None
    assert settings.max_webhook_secret is None
    assert settings.max_mini_app_context_secret is None
    assert settings.max_webhook_public_url is None
    assert settings.max_mini_app_public_url is None


def test_max_configured_secrets_are_secret_str_and_redacted() -> None:
    settings = AppSettings(
        max_bot_token=SecretStr("synthetic-max-bot-token"),
        max_webhook_secret=SecretStr("synthetic-webhook-secret"),
        max_mini_app_context_secret=SecretStr("synthetic-context-secret"),
    )

    assert settings.max_bot_token is not None
    assert settings.max_webhook_secret is not None
    assert settings.max_mini_app_context_secret is not None
    assert "synthetic-max-bot-token" not in repr(settings)
    assert "synthetic-webhook-secret" not in repr(settings)
    assert "synthetic-context-secret" not in repr(settings)


def test_max_allowed_update_types_reject_empty_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KVC_MAX_ALLOWED_UPDATE_TYPES", " , ")

    with pytest.raises(ValidationError):
        AppSettings()
