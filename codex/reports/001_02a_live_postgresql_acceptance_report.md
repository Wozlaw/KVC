# 001-02a — Live PostgreSQL acceptance report

## Baseline

- Baseline commit: `4e4d728 chore: bootstrap Kaiten Voice Control project`.
- Branch: `main`.
- Initial Git status before this stage:

```text
 M .env.example
 M README.md
 M docs/architecture/technology_stack.md
 M src/kvc_config/__init__.py
 M src/kvc_config/settings.py
 M src/kvc_persistence/__init__.py
 M tests/unit/test_settings.py
?? alembic.ini
?? codex/prompts/001_02_configuration_postgresql_persistence_alembic_foundation_prompt.md
?? codex/prompts/001_02a_live_postgresql_acceptance_prompt.md
?? codex/reports/001_02_configuration_postgresql_persistence_alembic_foundation_report.md
?? docs/operations/postgresql_local_development.md
?? src/kvc_persistence/base.py
?? src/kvc_persistence/engine.py
?? src/kvc_persistence/health.py
?? src/kvc_persistence/migrations/
?? src/kvc_persistence/session.py
?? tests/unit/test_alembic_foundation.py
?? tests/unit/test_persistence.py
```

- `git diff --check` before live acceptance: no output, exit code 0.
- `git log --oneline --decorate -5`:

```text
4e4d728 (HEAD -> main) chore: bootstrap Kaiten Voice Control project
```

Environment and tooling:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip --version
pip 26.2.1 from D:\Prog\KVControl\.venv\Lib\site-packages\pip (python 3.12)

psql --version
psql (PostgreSQL) 18.6

where.exe psql
C:\Program Files\PostgreSQL\18\bin\psql.exe

pg_isready -h 127.0.0.1 -p 5432
127.0.0.1:5432 - accepting connections

Get-Service *postgres*
Running  postgresql-x64-18  postgresql-x64-18 - PostgreSQL Server 18
```

Instrumental note: direct sandboxed execution of `.venv\Scripts\python.exe` could not access the base interpreter path. The same project `.venv` commands were run with approved elevated execution and returned Python 3.12.9.

## Preliminary audit

Audited before changes:

```text
src/kvc_config/
src/kvc_persistence/
alembic.ini
src/kvc_persistence/migrations/env.py
tests/
.env.example
docs/operations/postgresql_local_development.md
docs/architecture/technology_stack.md
codex/reports/001_02_configuration_postgresql_persistence_alembic_foundation_report.md
```

Findings:

- `AppSettings` loads `KVC_` variables from `.env`.
- `KVC_DATABASE_URL` is stored as `SecretStr | None`.
- engine creation uses project `create_async_engine_from_settings()`.
- database driver validation requires `postgresql+asyncpg`.
- health probe executes read-only `SELECT 1`.
- session factory returns `async_sessionmaker[AsyncSession]`.
- Alembic `env.py` uses project settings and shared `Base.metadata`.
- `Base.metadata.tables` is empty.
- `src/kvc_persistence/migrations/versions/` contains no revisions, only `.gitkeep`.

## Safe configuration summary

Loaded through the existing project settings API from local `.env`:

```text
env_exists: PASS
app_env: development
database scheme: postgresql+asyncpg
host: 127.0.0.1
port: 5432
database: kvc_dev
database user: kvc_user
database echo: False
credentials_present: true
password: REDACTED / not reported
rendered URL: postgresql+asyncpg://kvc_user:***@127.0.0.1:5432/kvc_dev
```

The full `KVC_DATABASE_URL` was not printed.

## Application connection

Executed through existing project APIs:

```text
Settings load: PASS
database URL validation: PASS
Base.metadata table count: 0
AsyncEngine creation: PASS
engine object is AsyncEngine: true
engine driver: postgresql+asyncpg
connection open: PASS
SELECT 1: 1
current_user: kvc_user
current_database: kvc_dev
connection close: PASS
engine dispose: PASS
```

The import smoke:

```text
.venv\Scripts\python.exe -c "import kvc_config, kvc_persistence, kvc_api; print('config, persistence and api imports ok')"
config, persistence and api imports ok
```

No database connection is created by importing `kvc_api`; live connection happened only after explicit engine use.

## Health probe

Executed with the existing `check_database_connection()` project health probe:

```text
health_ok=True
health_error_type=None
```

The probe performs read-only `SELECT 1`, creates no tables, mutates no data, and returns no credentials.

## AsyncSession

Executed with the existing project `create_async_sessionmaker()`:

```text
session_is_async=True
SELECT 1 via AsyncSession: 1
session close: PASS
engine dispose: PASS
```

No `CREATE`, `INSERT`, `UPDATE`, or `DELETE` was executed by the session acceptance.

## Schema state

Before Alembic online diagnostics:

```text
user tables: <none>
```

After Alembic online diagnostics:

```text
user tables: public.alembic_version
alembic_version row count: 0
alembic_version columns: version_num: character varying
```

There are no Kaiten Voice Control business tables. No Alembic revision file was created.

Deviation: `python -m alembic -c alembic.ini check` created the empty Alembic version table. Alembic 1.19.1 `current` uses `dont_mutate=True`; `check` runs the migration environment without `dont_mutate`, and `MigrationContext.run_migrations()` ensures the version table when no current heads exist. The table was not removed automatically.

## Alembic online diagnostics

Commands and results:

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini heads
<no output, exit code 0>

.venv\Scripts\python.exe -m alembic -c alembic.ini history
<no output, exit code 0>

.venv\Scripts\python.exe -m alembic -c alembic.ini current
<no output, exit code 0>

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

Acceptance facts:

- real PostgreSQL connection was used by online Alembic commands.
- `KVC_DATABASE_URL` came from project settings and local `.env`.
- `alembic.ini` was not edited with real credentials.
- shared `Base.metadata` was used.
- no fake revision was created.
- `alembic upgrade head` was not executed.

## Test isolation correction

Observed failure:

```text
.venv\Scripts\python.exe -m pytest
FAILED tests/unit/test_settings.py::test_settings_load_without_real_secrets
AssertionError: assert SecretStr('**********') is None
```

Root cause:

- The local `.env` now exists, so plain `AppSettings()` in a unit test loaded live `KVC_DATABASE_URL`.
- This violated the policy that regular `pytest` must stay independent from live PostgreSQL configuration.

Minimal correction:

- `tests/unit/test_settings.py::test_settings_load_without_real_secrets` now uses `AppSettings(_env_file=None)`.
- Production code was not changed.
- No integration test was added just for quantity.

Verification:

```text
.venv\Scripts\python.exe -m pytest
25 passed in 2.11s

.venv\Scripts\python.exe -m pytest -W error
25 passed in 2.07s
```

Both runs reported no warnings.

## Automated quality gate

Final quality gate results:

```text
.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
25 passed in 2.11s

.venv\Scripts\python.exe -m pytest -W error
25 passed in 2.07s

.venv\Scripts\python.exe -m ruff format --check .
39 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 21 source files

.venv\Scripts\python.exe -c "import kvc_config, kvc_persistence, kvc_api; print('config, persistence and api imports ok')"
config, persistence and api imports ok

.venv\Scripts\python.exe -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); tomllib.load(open('.codex/config.toml','rb')); print('toml ok')"
toml ok

git diff --check
<no output, exit code 0>
```

## Security

Ignore checks:

```text
git check-ignore -v -- .env .venv
.gitignore:2:.env    .env
.gitignore:1:.venv/  .venv
```

Credential checks:

```text
high_confidence_secret_scan=PASS
checked_files=50
```

The high-confidence scan checked tracked and unignored working tree files for the full live database URL and for the live password appearing inside a DSN credential segment. No matches were found. The real password and full live `KVC_DATABASE_URL` are not included in this report.

## Changed files

Production code changes:

```text
none
```

Tests:

```text
tests/unit/test_settings.py
```

Documentation:

```text
none
```

Report:

```text
codex/reports/001_02a_live_postgresql_acceptance_report.md
```

Existing uncommitted files from `001-02` remained in the working tree and were not reverted.

## Deviations

- `alembic check` created an empty `public.alembic_version` table. This was an Alembic online diagnostic side effect, not a project business table and not a fake revision.
- The table was not deleted automatically because the prompt explicitly required reporting unexpected schema changes instead of hiding them.
- A unit test needed a minimal isolation correction because local `.env` now exists.
- Sandboxed `.venv` execution could not access the base Python path; approved elevated execution of the same project `.venv` was used for checks.

## Final status

PASS WITH NOTES

The live PostgreSQL application path is proven:

```text
.env
  -> AppSettings
  -> KVC_DATABASE_URL
  -> SQLAlchemy AsyncEngine
  -> asyncpg
  -> PostgreSQL 18.6 / kvc_dev / kvc_user
  -> SELECT 1
  -> AsyncSession
  -> health probe
  -> Alembic online diagnostics
  -> dispose
```

Remaining note preventing clean `PASS`: the live Alembic diagnostic created the empty `public.alembic_version` table.
