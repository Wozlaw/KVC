"""Alembic foundation tests."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

REVISION_ID = "00201_mvp_service_model"
REVISION_PATH = Path("src/kvc_persistence/migrations/versions/00201_mvp_service_model.py")


def test_alembic_config_points_to_persistence_migrations() -> None:
    config = Config("alembic.ini")

    assert config.get_main_option("script_location") == "src/kvc_persistence/migrations"


def test_alembic_script_directory_has_initial_mvp_revision() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    revisions = list(script.walk_revisions())
    assert script.get_heads() == [REVISION_ID]
    assert len(revisions) == 1
    assert revisions[0].revision == REVISION_ID
    assert revisions[0].down_revision is None
    assert Path("src/kvc_persistence/migrations/versions/.gitkeep").exists()


def test_initial_migration_structure_matches_contract() -> None:
    migration = REVISION_PATH.read_text(encoding="utf-8")

    assert migration.count("op.create_table(") == 7
    assert migration.count("op.drop_table(") == 7
    assert "00201_mvp_service_model" in migration
    assert "down_revision: str | None = None" in migration
    assert "postgresql.ENUM" not in migration
    assert "sa.Enum" not in migration
    assert "sa.Date()" not in migration
    assert "postgresql.DATE" not in migration
    assert "CREATE EXTENSION" not in migration.upper()
    assert "due_at" in migration
    assert "due_date_time_present" in migration
    assert "due_date" not in migration.replace("due_date_time_present", "")
