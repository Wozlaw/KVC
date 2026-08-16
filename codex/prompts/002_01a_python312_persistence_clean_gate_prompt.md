# 002-01a — Python 3.12 environment recovery and persistence implementation clean gate

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Текущая ветка:

```text
002 — MVP service data model
```

Предыдущие этапы:

```text
002-00   MVP service data model audit
002-00a  Final MVP service data model specification
002-00b  Kaiten deadline semantics and notification dedup correction
002-00c  Live Kaiten deadline representation acceptance probe
002-01   MVP service data model implementation
```

Основной входной отчёт:

```text
codex/reports/002_01_mvp_service_data_model_implementation_report.md
```

`002-01` реализовал SQLAlchemy-модели и первую Alembic migration, но обязательный project quality gate не был выполнен в принятом runtime Python 3.12 из-за сломанной `.venv`.

Проверка на временном Python 3.14.3 полезна как диагностика, но **не заменяет accepted runtime Python 3.12**.

Дополнительно необходимо проверить потенциальный semantic drift timestamp mappings: initial `created_at`/`updated_at` должны реально получать значение через DB `server_default = now()`, а не незаметно подменяться application-side insert default.

Этот этап — **узкий corrective clean gate перед `002-02`**.

---

# 1. Главная цель

Выполнить три задачи:

1. восстановить/пересоздать проектную `.venv` на **CPython 3.12**;
2. проверить и при необходимости точечно исправить timestamp default semantics;
3. повторить полный quality gate и Alembic offline verification именно на Python 3.12.

После этого этапа реализация `002-01` должна быть доказанно готова к:

```text
002-02 — live PostgreSQL acceptance
```

---

# 2. Нормативная база

Изучи:

```text
codex/reports/002_00a_mvp_service_data_model_final_specification.md
codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
codex/reports/002_01_mvp_service_data_model_implementation_report.md
```

Также изучи текущие:

```text
pyproject.toml
src/kvc_persistence/base.py
src/kvc_persistence/models.py
src/kvc_persistence/engine.py
src/kvc_persistence/session.py
src/kvc_persistence/migrations/env.py
src/kvc_persistence/migrations/versions/00201_mvp_service_model.py
tests/
```

Не проектируй модель заново.

Приоритет frozen contract:

```text
002-00c
002-00b
002-00a
```

---

# 3. Baseline

Сначала зафиксируй:

```powershell
git status --short
git log --oneline --decorate -5
git diff --check
```

Проверь доступные Python interpreters:

```powershell
py -0p
where.exe python
where.exe py
py -3.12 --version
```

Не удаляй `.venv`, пока не подтвержден доступный Python 3.12 interpreter.

---

# 4. Восстановление `.venv`

В `002-01` `.venv\Scripts\python.exe` указывал на отсутствующий interpreter:

```text
C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe
```

Это необходимо исправить.

## Требование к версии

Использовать:

```text
Python 3.12.x
```

Предпочтительно ранее принятую проектом версию:

```text
Python 3.12.9
```

если она доступна.

Не переводить проект на Python 3.14.

Не менять `requires-python` или runtime contract ради обхода проблемы.

## Если Python 3.12 установлен

Предпочтительная последовательность:

1. удалить только сломанную `.venv`;
2. создать новую `.venv` через реальный Python 3.12;
3. установить зависимости штатным mechanism проекта;
4. проверить версию и dependency integrity.

Пример:

```powershell
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.venv\Scripts\python.exe --version
```

Фактическую команду установки dependencies определить по repository contract:

```text
pyproject.toml
lock file
requirements files
editable install
dev/test extras
```

Не делать массовый dependency upgrade.

## Если Python 3.12 отсутствует

Не использовать другую minor/major версию как substitute.

Финальный статус:

```text
BLOCKED - PYTHON 3.12 RUNTIME REQUIRED
```

---

# 5. Dependency reconstruction

После пересоздания `.venv` установить ровно project-defined dependencies.

Проверь:

```text
pyproject.toml
lock/requirements mechanism
dev/test dependencies
```

После установки:

```powershell
.venv\Scripts\python.exe -m pip check
```

должен проходить.

Не менять версии зависимостей без необходимости.

---

# 6. Timestamp semantic audit

Проверь фактические mappings в:

```text
src/kvc_persistence/models.py
```

и любые mixins/helpers, если они используются.

В `002-01` report указано:

```text
created_at and updated_at have server default now()
ORM models also use timezone-aware Python defaults
updated_at has application-side onupdate
```

Нужно подтвердить, не подменяет ли application-side `default` серверный default при ORM INSERT.

## Frozen semantics

Initial insert:

```text
created_at  -> server_default = now()
updated_at  -> server_default = now()
```

Subsequent update:

```text
updated_at -> application/ORM-side onupdate
```

DB trigger не нужен.

---

# 7. Что проверить для timestamp columns

Для каждого relevant field проверь:

```text
default
server_default
onupdate
server_onupdate
nullable
DateTime(timezone=True)
```

Особенно:

```text
created_at
updated_at
```

Нежелательная комбинация:

```python
default = utc_now
server_default = func.now()
```

на initial insert, если accepted contract требует реального DB `now()`.

---

# 8. Целевая timestamp semantics

Если найден drift, исправить минимально.

## `created_at`

Ожидается:

```text
server_default = now()
no application-side insert default
```

## `updated_at`

Ожидается:

```text
server_default = now()
no application-side insert default
application-side onupdate present
```

Допустим технически эквивалентный SQLAlchemy 2.x вариант, сохраняющий эти semantics.

Не добавлять:

```text
DB trigger
server-side update trigger
```

---

# 9. Scope correction

Проверить все семь models.

Если helper/mixin используется только этими моделями и исправление очевидно — допускается точечная общая правка.

Не делать крупный refactoring.

Цель:

```text
minimal semantic correction
```

---

# 10. Tests для timestamp semantics

Добавить/скорректировать tests, подтверждающие:

```text
created_at.server_default exists
updated_at.server_default exists
created_at has no application insert default
updated_at has no application insert default
updated_at has application-side onupdate
DateTime(timezone=True)
```

Проверять SQLAlchemy metadata semantics, а не нестабильный textual repr.

---

# 11. Frozen persistence contract не менять

Запрещено изменять:

```text
table inventory
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

Сохраняем:

```text
notification_history.due_at TIMESTAMPTZ NOT NULL
notification_history.due_date_time_present BOOLEAN NOT NULL
```

Сохраняем отсутствие:

```text
notification_history.due_date
```

Не возвращать PostgreSQL `DATE`.

---

# 12. Migration менять только при реальном schema drift

Проверь:

```text
src/kvc_persistence/migrations/versions/00201_mvp_service_model.py
```

Если migration уже содержит корректные DB `server_default=now()` и physical schema не меняется, timestamp correction может затрагивать только ORM/tests.

Не переписывать migration из-за application-only `default/onupdate`.

Migration менять только если обнаружено фактическое расхождение frozen physical schema.

---

# 13. Model/migration parity

После любых изменений подтвердить physical parity:

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
partial indexes
secondary indexes
server defaults
```

Application-only `onupdate` может отсутствовать в DDL — это нормально.

Явно отметить это в report.

---

# 14. Targeted Python 3.12 gate

После восстановления `.venv` выполнить:

```powershell
.venv\Scripts\python.exe --version

.venv\Scripts\python.exe -m pytest `
  tests\unit\test_persistence_models.py `
  tests\unit\test_alembic_foundation.py -q
```

Ожидается:

```text
Python 3.12.x
all targeted tests pass
```

Никакого fallback Python 3.14 для acceptance result.

---

# 15. Full Python 3.12 quality gate

Обязательно выполнить:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip check

.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error

.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src
```

Все команды должны выполняться через:

```text
.venv\Scripts\python.exe
```

Не использовать Python 3.14 как substitute.

---

# 16. Alembic clean gate на Python 3.12

В той же `.venv` выполнить:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini heads
.venv\Scripts\python.exe -m alembic -c alembic.ini history
```

Ожидается:

```text
00201_mvp_service_model (head)
```

и одна initial chain:

```text
<base> -> 00201_mvp_service_model
```

---

# 17. Offline SQL render

Выполнить:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head --sql
```

Проверить наличие:

```text
7 CREATE TABLE
TIMESTAMP WITH TIME ZONE
JSONB
BYTEA
partial UNIQUE indexes
notification_history.due_at
notification_history.due_date_time_present
```

И отсутствие:

```text
due_date DATE
CREATE TYPE ... ENUM
CREATE EXTENSION
unrelated DROP/ALTER
```

Не записывать connection secrets в report.

---

# 18. Не выполнять live migration

На `002-01a` запрещено:

```powershell
alembic upgrade head
alembic downgrade
```

без `--sql`.

Не выполнять:

```text
CREATE TABLE
DROP TABLE
manual DDL
manual schema repair
```

Live acceptance — `002-02`.

---

# 19. Не использовать live Kaiten/MAX

Не выполнять:

- Kaiten API mutation;
- deadline probe;
- MAX calls;
- notification worker;
- encryption;
- repository/service logic.

`.env` не изменять.

---

# 20. Environment hygiene

После пересоздания `.venv` убедиться:

```text
.venv не отслеживается Git
.env не отслеживается Git
```

Проверить:

```powershell
git status --short
```

Если `.gitignore` уже корректен, не менять его.

---

# 21. Git review

После correction:

```powershell
git diff --check
git diff --stat
git status --short
```

Не допускать:

- unrelated formatting churn;
- dependency lock churn без причины;
- `.env` diff;
- `.venv` tracking.

---

# 22. Итоговый report

Создай:

```text
codex/reports/002_01a_python312_persistence_clean_gate_report.md
```

Он должен содержать минимум:

1. Executive summary.
2. Reason for corrective stage.
3. Baseline Git state.
4. Broken `.venv` diagnosis.
5. Available Python 3.12 interpreter.
6. `.venv` recovery method.
7. Dependency installation method.
8. Exact Python version in recovered `.venv`.
9. `pip check`.
10. Timestamp semantic audit.
11. Pre-correction timestamp behavior, если drift найден.
12. Exact correction performed.
13. Confirmation physical DB schema contract unchanged.
14. Migration change status.
15. Timestamp tests.
16. Targeted tests.
17. Full pytest.
18. `pytest -W error`.
19. Ruff format/check.
20. mypy.
21. Alembic heads/history.
22. Offline SQL render.
23. Seven-table inventory confirmation.
24. `due_at + due_date_time_present` confirmation.
25. `due_date DATE` absence.
26. Confirmation no live DB migration.
27. Changed files.
28. Git checks.
29. Deferred items for `002-02`.
30. Final status.

---

# 23. Changed-files classification

В report:

```text
Production code:
Alembic:
Tests:
Dependency/configuration:
Documentation:
Reports:
Environment-only:
Other:
```

`.venv` recreation:

```text
Environment-only
```

Если migration не менялась:

```text
Alembic:
none
```

Если model correction не понадобилась:

```text
Production code:
none
```

Не создавать искусственный diff.

---

# 24. Acceptance criteria

`002-01a` успешен только если:

- `.venv` использует CPython 3.12.x;
- `.venv\Scripts\python.exe --version` проходит;
- dependencies восстановлены штатным mechanism проекта;
- `pip check` проходит;
- timestamp semantics проверены;
- drift, если найден, минимально исправлен;
- `created_at` initial value остаётся DB server default;
- `updated_at` initial value остаётся DB server default;
- `updated_at` имеет application-side update behavior;
- frozen seven-table physical contract не изменён;
- `due_at + due_date_time_present` сохранены;
- `due_date DATE` отсутствует;
- targeted tests проходят;
- full pytest проходит;
- `pytest -W error` проходит;
- Ruff проходит;
- mypy проходит;
- Alembic heads/history проходят на Python 3.12;
- offline SQL render проходит;
- live PostgreSQL schema не изменена;
- `.env` не изменён;
- `.venv` не попала в Git;
- report создан.

---

# 25. Final status

Если всё успешно:

```text
ACCEPTED CLEAN GATE - READY FOR 002-02 LIVE POSTGRESQL ACCEPTANCE
```

Если Python 3.12 отсутствует:

```text
BLOCKED - PYTHON 3.12 RUNTIME REQUIRED
```

Если найден persistence drift, требующий архитектурного решения:

```text
BLOCKED - PERSISTENCE CONTRACT DECISION REQUIRED
```

Проблема live PostgreSQL access не является blocker для `002-01a`, поскольку live acceptance относится к `002-02`.

---

## Главное правило

`002-01a` не расширяет persistence model и не является новой feature.

Он должен:

```text
восстановить accepted Python 3.12 runtime
+
проверить timestamp default semantics
+
получить чистый project quality gate
```

После этого `002-01` можно окончательно считать принятым и переходить к `002-02`.
