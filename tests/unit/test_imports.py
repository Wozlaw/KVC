"""Import smoke tests for top-level project packages."""

from importlib import import_module


def test_top_level_packages_import() -> None:
    packages = [
        "kvc_api",
        "kvc_worker",
        "kvc_domain",
        "kvc_application",
        "kvc_application.services",
        "kvc_persistence",
        "kvc_notifications",
        "kvc_config",
        "kvc_integrations",
        "kvc_integrations.security",
        "kvc_integrations.system",
        "kvc_integrations.kaiten",
        "kvc_integrations.max",
        "kvc_integrations.gigachat",
        "kvc_integrations.stt",
        "kvc_integrations.stt.salutespeech",
        "kvc_persistence.models",
        "kvc_persistence.repositories",
    ]

    for package_name in packages:
        assert import_module(package_name)
