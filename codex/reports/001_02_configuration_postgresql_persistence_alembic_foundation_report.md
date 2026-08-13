# 001-02 — Configuration, PostgreSQL persistence and Alembic foundation report

## 24.1. Baseline

- Baseline commit: `4e4d728 chore: bootstrap Kaiten Voice Control project`.
- Initial Git status before implementation:

```text
?? codex/prompts/001_02_configuration_postgresql_persistence_alembic_foundation_prompt.md
```

- `git diff --check` before implementation: no output, exit code 0.
- Product specification present:
  - `docs/specifications/Kaiten Voice Control — спецификация MVP v0.1.md`.

Baseline environment and package versions:

```text
Python 3.12.9
pip 26.2.1
fastapi==0.141.1
pydantic==2.13.4
pydantic-settings==2.15.0
sqlalchemy==2.0.52
alembic==1.19.1
asyncpg==0.31.0
pytest==9.1.1
ruff==0.16.2
mypy==2.3.0
```

Baseline quality gate before implementation:

```text
pip check: No broken requirements found.
pytest: 4 passed, 0 warnings
ruff check .: All checks passed!
mypy src: Success: no issues found in 16 source files
```

PostgreSQL tooling inventory:

```text
psql --version
psql: command not found / not recognized by PowerShell
```

```text
where.exe psql
INFO: Could not find files for the given pattern(s).
```

```text
Get-Service *postgres*
```

Result: no PostgreSQL service entries returned.

Local database configuration:

```text
.env: absent
KVC_APP_ENV=<not set>
KVC_DATABASE_URL=<not set>
KVC_DATABASE_ECHO=<not set>
KVC_LOG_LEVEL=<not set>
```

No database URL or credentials were available for live PostgreSQL smoke.

## 24.2. Configuration contract

Implemented in `src/kvc_config/settings.py`.

```text
KVC_APP_ENV
  type: Literal["development", "test", "production"]
  default: development
  required: no
  invalid values: rejected by pydantic validation

KVC_LOG_LEVEL
  type: str
  default: INFO
  required: no

KVC_DATABASE_URL
  type: SecretStr | None
  default: None
  required: no for imports and /health
  required: yes for database engine creation and Alembic online/offline environment
  validation: must be a valid SQLAlchemy URL with driver postgresql+asyncpg before engine creation
  repr/logging: redacted by SecretStr; full value is read only inside database URL factory

KVC_DATABASE_ECHO
  type: bool
  default: false
  required: no
```

`.env.example` now documents `KVC_APP_ENV`, `KVC_LOG_LEVEL`, `KVC_DATABASE_URL`, and `KVC_DATABASE_ECHO`, plus existing future integration placeholders. Values are placeholders only.

## 24.3. Persistence structure

```text
src/kvc_persistence/
├── __init__.py
├── base.py
├── engine.py
├── health.py
├── session.py
└── migrations/
    ├── env.py
    ├── script.py.mako
    └── versions/
        └── .gitkeep
```

File responsibilities:

- `base.py` — shared SQLAlchemy `DeclarativeBase` and naming convention.
- `engine.py` — database URL validation, `AsyncEngine` factory, dispose lifecycle.
- `session.py` — `async_sessionmaker[AsyncSession]` contract.
- `health.py` — read-only `SELECT 1` health probe with safe result object.
- `migrations/env.py` — Alembic async PostgreSQL environment using shared metadata.
- `migrations/script.py.mako` — future revision template.
- `migrations/versions/.gitkeep` — keeps versions directory without fake migrations.

## 24.4. SQLAlchemy contract

- `Base`: `sqlalchemy.orm.DeclarativeBase`.
- Metadata: single shared `Base.metadata`.
- Naming convention:

```text
ix: ix_%(column_0_label)s
uq: uq_%(table_name)s_%(column_0_name)s
ck: ck_%(table_name)s_%(constraint_name)s
fk: fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s
pk: pk_%(table_name)s
```

- Runtime driver contract: `postgresql+asyncpg`.
- Engine factory: `create_async_engine_from_settings(settings=None)`.
- Engine options: `pool_pre_ping=True`, `echo=KVC_DATABASE_ECHO`.
- Engine creation does not connect at import time.
- Session factory: `async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)`.
- Disposal lifecycle: `dispose_async_engine(engine)` awaits `engine.dispose()`.
- No repository layer, Unit of Work, API dependency, business table, or migration revision was added.

## 24.5. Alembic

- Config file: `alembic.ini`.
- Migration directory: `src/kvc_persistence/migrations`.
- Versions directory: `src/kvc_persistence/migrations/versions`.
- URL source: `KVC_DATABASE_URL` through `AppSettings` and `get_database_url()`.
- `alembic.ini` contains only a non-credential placeholder:

```text
sqlalchemy.url = postgresql+asyncpg://localhost/placeholder_database
```

- Target metadata:

```text
target_metadata = Base.metadata
```

Diagnostics:

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini heads
```

Result: no output, exit code 0.

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini history
```

Result: no output, exit code 0.

```text
$env:KVC_DATABASE_URL='<test postgresql+asyncpg URL, redacted>'
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head --sql
BEGIN;
COMMIT;
```

This loaded Alembic `env.py` and shared metadata in offline SQL mode without connecting to PostgreSQL and without creating revisions.

Fake empty migration status:

```text
src/kvc_persistence/migrations/versions/
└── .gitkeep
```

No Alembic revision files exist.

## 24.6. PostgreSQL live smoke

Status: `NOT RUN`.

Reason:

- `psql` is not available in PATH.
- `Get-Service *postgres*` returned no PostgreSQL services.
- `.env` is absent.
- `KVC_DATABASE_URL` is not set in the current shell.

No SQLite fallback was introduced. No PostgreSQL installation, service creation, user/database creation, PATH changes, Docker setup, or system configuration changes were attempted.

## 24.7. Tests

Final quality gate:

```text
.venv\Scripts\python.exe --version
Python 3.12.9
```

```text
.venv\Scripts\python.exe -m pip --version
pip 26.2.1 from D:\Prog\KVControl\.venv\Lib\site-packages\pip (python 3.12)
```

```text
.venv\Scripts\python.exe -m pip check
No broken requirements found.
```

```text
.venv\Scripts\python.exe -m pytest
collected 25 items
tests\smoke\test_health.py .. [  8%]
tests\unit\test_alembic_foundation.py .. [ 16%]
tests\unit\test_imports.py . [ 20%]
tests\unit\test_persistence.py ....... [ 48%]
tests\unit\test_settings.py ............. [100%]
25 passed in 2.02s
coverage TOTAL: 91%
```

`pytest`: 25 passed, 0 warnings.

```text
.venv\Scripts\python.exe -m pytest -W error
25 passed in 2.04s
coverage TOTAL: 91%
```

`pytest -W error`: PASS.

```text
.venv\Scripts\python.exe -m ruff format --check .
37 files already formatted
```

```text
.venv\Scripts\python.exe -m ruff check .
All checks passed!
```

```text
.venv\Scripts\python.exe -m mypy src
Success: no issues found in 21 source files
```

```text
.venv\Scripts\python.exe -c "import kvc_config, kvc_persistence; print('config and persistence imports ok')"
config and persistence imports ok
```

```text
.venv\Scripts\python.exe -c "import kvc_api; print('kvc_api import ok without database connection')"
kvc_api import ok without database connection
```

```text
.venv\Scripts\python.exe -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); tomllib.load(open('.codex/config.toml','rb')); print('toml ok')"
toml ok
```

```text
git diff --check
```

Result: no output, exit code 0.

## 24.8. Security

- Real database credentials were not added.
- `.env` remains ignored.
- `.venv/` remains ignored.
- Database URL is represented as `SecretStr | None` in settings.
- Database URL validation returns clear controlled `DatabaseConfigurationError` without printing credentials.
- Database health result returns only `ok` and `error_type`.
- Alembic config does not contain real credentials.
- Search for credential-like strings found only placeholders, tests, documentation references, and secret-handling code.

Ignore check:

```text
git check-ignore -v -- .env .venv AGENTS.md .codex/config.toml requirements.lock.txt docs/specifications docs/operations
.gitignore:2:.env    .env
.gitignore:1:.venv/  .venv
```

`AGENTS.md`, `.codex/config.toml`, `requirements.lock.txt`, `docs/specifications/`, and `docs/operations/` are not ignored.

## 24.9. Changed files

Created:

```text
alembic.ini
docs/operations/postgresql_local_development.md
src/kvc_persistence/base.py
src/kvc_persistence/engine.py
src/kvc_persistence/health.py
src/kvc_persistence/session.py
src/kvc_persistence/migrations/env.py
src/kvc_persistence/migrations/script.py.mako
src/kvc_persistence/migrations/versions/.gitkeep
tests/unit/test_alembic_foundation.py
tests/unit/test_persistence.py
codex/reports/001_02_configuration_postgresql_persistence_alembic_foundation_report.md
```

Modified:

```text
.env.example
README.md
docs/architecture/technology_stack.md
src/kvc_config/__init__.py
src/kvc_config/settings.py
src/kvc_persistence/__init__.py
tests/unit/test_settings.py
```

Present but not part of architecture implementation:

```text
codex/prompts/001_02_configuration_postgresql_persistence_alembic_foundation_prompt.md
```

## 24.10. Deviations

- PostgreSQL live smoke was not executed because local PostgreSQL tooling/service and `KVC_DATABASE_URL` were unavailable.
- No dependencies were added; existing `sqlalchemy`, `alembic`, `asyncpg`, `pydantic`, and `pydantic-settings` were sufficient. Therefore `requirements.lock.txt` was not regenerated to avoid meaningless lock snapshot churn.
- `alembic check` and `alembic current` were not run against a database because they require live database configuration. Offline Alembic environment loading was verified with `upgrade head --sql`.

## 24.11. Final status

PASS WITH NOTES
