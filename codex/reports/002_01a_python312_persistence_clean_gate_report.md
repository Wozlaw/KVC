# 002-01a - Python 3.12 persistence clean gate report

## Executive summary

Recovered the project runtime gate on CPython 3.12.9, corrected ORM timestamp insert semantics, and reran the persistence implementation clean gate through:

```text
.venv\Scripts\python.exe
```

Final status:

```text
ACCEPTED CLEAN GATE - READY FOR 002-02 LIVE POSTGRESQL ACCEPTANCE
```

No live PostgreSQL migration, downgrade, manual DDL, Kaiten call, MAX call, repository/service implementation, encryption implementation, or `.env` change was performed.

## Reason for corrective stage

`002-01` implemented the MVP persistence model, but the accepted runtime gate could not run because `.venv\Scripts\python.exe` pointed to:

```text
C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe
```

and that interpreter was not accessible in the normal workspace sandbox. The temporary Python 3.14 gate from `002-01` was diagnostic only and did not satisfy the project runtime contract `>=3.12,<3.13`.

`002-01a` also audited timestamp semantics because the ORM models had both application insert defaults and DB `server_default=now()` on `created_at` and `updated_at`.

## Baseline Git state

Initial baseline:

```text
git status --short
 M src/kvc_persistence/migrations/env.py
 M tests/unit/test_alembic_foundation.py
 M tests/unit/test_imports.py
 M tests/unit/test_persistence.py
?? codex/prompts/002_00_mvp_service_data_model_audit_prompt.md
?? codex/prompts/002_00a_mvp_service_data_model_final_specification_prompt.md
?? codex/prompts/002_00b_kaiten_deadline_notification_semantics_correction_prompt.md
?? codex/prompts/002_00c_live_kaiten_deadline_representation_acceptance_probe_prompt.md
?? codex/prompts/002_01_mvp_service_data_model_implementation_prompt.md
?? codex/prompts/002_01a_python312_persistence_clean_gate_prompt.md
?? codex/reports/002_00_mvp_service_data_model_audit_report.md
?? codex/reports/002_00a_mvp_service_data_model_final_specification.md
?? codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
?? codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
?? codex/reports/002_01_mvp_service_data_model_implementation_report.md
?? src/kvc_persistence/migrations/versions/00201_mvp_service_model.py
?? src/kvc_persistence/models.py
?? tests/unit/test_persistence_models.py

git log --oneline --decorate -5
0501ca3 (HEAD -> main) feat: add PostgreSQL persistence foundation
4e4d728 chore: bootstrap Kaiten Voice Control project

git diff --check
<no output, exit code 0>
```

The modified/untracked persistence files are the `002-01` implementation state that this corrective gate validates.

## Broken `.venv` diagnosis

Before recovery:

```text
py -0p
  *               D:\Prog\KVControl\.venv\Scripts\python.exe
 -V:3.14          C:\Python314\python.exe
 -V:3.10          C:\Python310\python.exe

where.exe python
D:\Prog\KVControl\.venv\Scripts\python.exe
C:\Python314\python.exe
C:\Python310\python.exe

where.exe py
C:\Windows\py.exe

py -3.12 --version
No suitable Python runtime found
```

The old `.venv\Scripts\python.exe` failed with:

```text
No Python at '"C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe'
```

An Inkscape-bundled Python 3.12.9 existed, but it used a Mingw extension suffix and created a POSIX-style `bin/` venv, so it was not suitable for the required Windows `.venv\Scripts\python.exe` clean gate.

## Available Python 3.12 interpreter

Downloaded the official CPython 3.12.9 NuGet package using Python 3.14 `urllib`, because `Invoke-WebRequest`, `curl.exe`, and Chocolatey network calls failed with TLS/connection errors.

Installed local runtime base:

```text
D:\Prog\KVControl\.python312\tools\python.exe
Python 3.12.9
```

`.python312/` is ignored by Git.

## `.venv` recovery method

The old `.venv` could not be fully removed at first because the stale launcher file denied deletion. It was renamed, and the venv was recreated over the directory using the local CPython 3.12.9 runtime:

```text
.\.python312\tools\python.exe -m venv .venv
.\.venv\Scripts\python.exe --version
Python 3.12.9
```

Recovered `.venv\pyvenv.cfg` points to:

```text
home = D:\Prog\KVControl\.python312\tools
version = 3.12.9
executable = D:\Prog\KVControl\.python312\tools\python.exe
```

`.venv/` is ignored by Git.

## Dependency installation method

Project dependency contract:

```text
pyproject.toml
requirements.lock.txt
```

Dependencies were installed from `requirements.lock.txt`. The lock file contains:

```text
-e d:\prog\kvcontrol
```

New pip parses the backslashes in that editable path as escapes, so a temporary requirements copy outside the repository replaced only that editable line with:

```text
-e .
```

All pinned package versions remained from `requirements.lock.txt`; no dependency upgrade was performed.

## Exact Python version in recovered `.venv`

```text
.venv\Scripts\python.exe --version
Python 3.12.9
```

## `pip check`

```text
.venv\Scripts\python.exe -m pip check
No broken requirements found.
```

## Timestamp semantic audit

Audited all seven ORM models in:

```text
src/kvc_persistence/models.py
```

Relevant timestamp columns:

```text
created_at
updated_at
last_verified_at
last_card_list_at
expires_at
ended_at
executed_at
sent_at
failed_at
notification_history.due_at
```

All instant columns remain `DateTime(timezone=True)`.

## Pre-correction timestamp behavior

Drift was found in ORM metadata:

```text
created_at: default=_utcnow + server_default=now()
updated_at: default=_utcnow + onupdate=_utcnow + server_default=now()
```

This could cause ORM INSERT to supply application-side values for `created_at`/`updated_at`, preventing the DB `server_default=now()` from producing initial values.

The physical Alembic migration already used DB `server_default=now()` and did not need schema changes.

## Exact correction performed

Changed ORM metadata only:

```text
created_at:
  default removed
  server_default=now() kept
  onupdate absent
  server_onupdate absent

updated_at:
  default removed
  server_default=now() kept
  onupdate=_utcnow kept
  server_onupdate absent
```

This preserves accepted semantics:

```text
initial insert -> DB server now()
subsequent ORM update -> application-side onupdate
```

No DB trigger was added.

## Physical DB schema contract

Confirmed unchanged:

```text
tables
columns
types
nullability
PK
FK
ON DELETE
CHECK
UNIQUE
partial UNIQUE
secondary indexes
JSONB contract
UUID contract
notification deadline contract
```

Application-only `onupdate` is not represented in DDL; this is expected.

## Migration change status

No `002-01a` migration change was required.

The existing initial revision remains:

```text
src/kvc_persistence/migrations/versions/00201_mvp_service_model.py
revision = 00201_mvp_service_model
down_revision = None
```

## Timestamp tests

Added metadata assertions to `tests/unit/test_persistence_models.py`:

```text
created_at.server_default exists
updated_at.server_default exists
created_at.default is None
updated_at.default is None
updated_at.onupdate exists
created_at.server_onupdate is None
updated_at.server_onupdate is None
DateTime(timezone=True)
```

Direct metadata probe after correction:

```text
('users', None, True, None, True, True, None, None)
('max_chats', None, True, None, True, True, None, None)
('kaiten_connections', None, True, None, True, True, None, None)
('dialog_sessions', None, True, None, True, True, None, None)
('pending_commands', None, True, None, True, True, None, None)
('notification_settings', None, True, None, True, True, None, None)
('notification_history', None, True, None, True, True, None, None)
```

Tuple meaning:

```text
table, created_at.default, created_at.server_default_exists,
updated_at.default, updated_at.server_default_exists,
updated_at.onupdate_exists, created_at.server_onupdate, updated_at.server_onupdate
```

## Targeted tests

```text
.venv\Scripts\python.exe -m pytest tests\unit\test_persistence_models.py tests\unit\test_alembic_foundation.py -q
18 passed
```

## Full pytest

```text
.venv\Scripts\python.exe -m pytest
41 passed
```

## `pytest -W error`

```text
.venv\Scripts\python.exe -m pytest -W error
41 passed
```

Ignored `.coverage` and `.pytest_cache` artifacts were cleaned before the Python 3.12 gate so old cache/coverage files could not affect `-W error`.

## Ruff format/check

```text
.venv\Scripts\python.exe -m ruff format --check .
54 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!
```

`codex/prompts/002_01a_python312_persistence_clean_gate_prompt.md` was formatted because Ruff checks markdown Python snippets.

## mypy

```text
.venv\Scripts\python.exe -m mypy src
Success: no issues found in 23 source files
```

## Alembic heads/history

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini heads
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini history
<base> -> 00201_mvp_service_model (head), add MVP service data model
```

## Offline SQL render

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head --sql
exit code 0
```

Rendered SQL contains:

```text
TIMESTAMP WITH TIME ZONE
JSONB
BYTEA
notification_history.due_at
notification_history.due_date_time_present
partial UNIQUE indexes
```

Rendered SQL does not contain:

```text
due_date DATE
CREATE TYPE ... ENUM
CREATE EXTENSION
unrelated DROP/ALTER
```

`CREATE TABLE` count is 8 in the raw offline render because Alembic also emits its service table:

```text
alembic_version
```

KVC business table inventory remains exactly 7.

## Seven-table inventory confirmation

```text
['dialog_sessions', 'kaiten_connections', 'max_chats', 'notification_history', 'notification_settings', 'pending_commands', 'users']
7
```

No Kaiten mirror tables were added.

## Deadline confirmation

Preserved:

```text
notification_history.due_at TIMESTAMPTZ NOT NULL
notification_history.due_date_time_present BOOLEAN NOT NULL
uq_notification_history_dedup:
  user_id, kaiten_card_id, due_at, due_date_time_present, notification_type
```

Confirmed absent:

```text
notification_history.due_date
due_date DATE
```

## No live DB migration

Not executed:

```text
alembic upgrade head
alembic downgrade
manual CREATE TABLE
manual DROP TABLE
manual DDL
```

Only offline SQL render with `--sql` was executed.

## Changed files

Production code:

```text
src/kvc_persistence/models.py
  removed application-side insert defaults from created_at/updated_at
```

Alembic:

```text
none for 002-01a
```

Existing untracked Alembic file from `002-01` remains present:

```text
src/kvc_persistence/migrations/versions/00201_mvp_service_model.py
```

Tests:

```text
tests/unit/test_persistence_models.py
  added timestamp default/onupdate semantic assertions
```

Existing test changes from `002-01` remain present:

```text
tests/unit/test_persistence.py
tests/unit/test_imports.py
tests/unit/test_alembic_foundation.py
```

Dependency/configuration:

```text
.gitignore
  added .python312/
```

Documentation:

```text
codex/prompts/002_01a_python312_persistence_clean_gate_prompt.md
  Ruff-formatted Python snippet
```

Reports:

```text
codex/reports/002_01a_python312_persistence_clean_gate_report.md
```

Environment-only:

```text
.python312/
.venv/
temporary requirements copy outside repository
```

Other:

```text
none
```

## Git checks

```text
git diff --check
<no output, exit code 0>

git status --short --ignored .venv .python312 .env
!! .env
!! .python312/
!! .venv/
```

Final tracked diff stat before this report:

```text
.gitignore                            |  2 +-
src/kvc_persistence/migrations/env.py | 18 ++++++++++++++++++
tests/unit/test_alembic_foundation.py | 29 ++++++++++++++++++++++++++---
tests/unit/test_imports.py            |  1 +
tests/unit/test_persistence.py        | 14 ++++++++++++--
5 files changed, 58 insertions(+), 6 deletions(-)
```

`git diff --stat` does not include untracked files from `002-01`/`002-01a`; see `git status --short` for the full worktree inventory.

## Deferred items for `002-02`

- Run live PostgreSQL upgrade/downgrade acceptance against the configured PostgreSQL instance.
- Inspect the physical schema in PostgreSQL.
- Verify Alembic `alembic_version` state after live migration.
- Do not use this stage as a substitute for live DB acceptance.

## Stage status

```text
ACCEPTED CLEAN GATE - READY FOR 002-02 LIVE POSTGRESQL ACCEPTANCE
```
