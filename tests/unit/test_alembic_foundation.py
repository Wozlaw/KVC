"""Alembic foundation tests."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_config_points_to_persistence_migrations() -> None:
    config = Config("alembic.ini")

    assert config.get_main_option("script_location") == "src/kvc_persistence/migrations"


def test_alembic_script_directory_has_no_revisions() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == []
    assert list(script.walk_revisions()) == []
    assert Path("src/kvc_persistence/migrations/versions/.gitkeep").exists()
