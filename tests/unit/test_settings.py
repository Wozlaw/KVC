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

    assert "secret" not in repr(settings)
    assert "secret" not in str(settings)


def test_missing_database_url_does_not_break_app_import() -> None:
    from kvc_api import create_app

    assert create_app()


def test_creating_database_engine_without_url_raises_controlled_error() -> None:
    settings = AppSettings(database_url=None)

    with pytest.raises(DatabaseConfigurationError, match="KVC_DATABASE_URL"):
        create_async_engine_from_settings(settings)
