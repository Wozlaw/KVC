"""Settings tests."""

from kvc_config import AppSettings


def test_settings_load_without_real_secrets() -> None:
    settings = AppSettings()

    assert settings.env == "development"
    assert settings.log_level == "INFO"
    assert settings.gigachat_model == "GigaChat-Pro"
    assert settings.max_bot_token is None
    assert settings.kaiten_api_token is None
