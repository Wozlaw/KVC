# 002-02 — Live PostgreSQL persistence acceptance

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
002-01a  Python 3.12 persistence clean gate
```

Основной входной отчёт:

```text
codex/reports/002_01a_python312_persistence_clean_gate_report.md
```

`002-01a` завершён со статусом:

```text
ACCEPTED CLEAN GATE - READY FOR 002-02 LIVE POSTGRESQL ACCEPTANCE
```

На этом этапе необходимо **реально применить initial Alembic migration к configured PostgreSQL**, проверить физическую схему, выполнить downgrade/upgrade round-trip и доказать соответствие frozen persistence contract.

Это **live database acceptance stage**.

---

# 1. Главная цель

Подтвердить на реальном PostgreSQL, что revision:

```text
00201_mvp_service_model
```

корректно:

1. применяется к baseline database;
2. создаёт ровно семь KVC business tables;
3. создаёт правильные PK/FK/CHECK/UNIQUE/partial UNIQUE/indexes/defaults;
4. сохраняет финальный deadline contract;
5. корректно записывает Alembic revision state;
6. полностью откатывается;
7. повторно применяется после downgrade;
8. не создаёт schema drift;
9. не затрагивает unrelated database objects.

После `002-02` persistence schema ветки `002` должна считаться физически принятой на PostgreSQL.

---

# 2. Нормативные документы

Перед выполнением обязательно изучи:

```text
codex/reports/002_00a_mvp_service_data_model_final_specification.md
codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
codex/reports/002_01_mvp_service_data_model_implementation_report.md
codex/reports/002_01a_python312_persistence_clean_gate_report.md
```

Также проверь:

```text
src/kvc_persistence/models.py
src/kvc_persistence/migrations/env.py
src/kvc_persistence/migrations/versions/00201_mvp_service_model.py
alembic.ini
pyproject.toml
```

Приоритет frozen contract:

```text
002-00c
002-00b
002-00a
```

Не проектируй модель заново.

---

# 3. Runtime contract

Все команды выполнять через восстановленную project environment:

```text
.venv\Scripts\python.exe
```

Перед live DB действиями обязательно подтвердить:

```powershell
.venv\Scripts\python.exe --version
```

Ожидается:

```text
Python 3.12.x
```

Предпочтительно:

```text
Python 3.12.9
```

Не использовать Python 3.14 fallback для acceptance.

---

# 4. Безопасность live database acceptance

Этот этап разрешает DDL только в configured KVC development database.

Перед migration необходимо доказать, что target database:

- является development/test database проекта;
- не является production;
- содержит только ожидаемый baseline;
- доступна через configured `KVC_DATABASE_URL`;
- не содержит ценных пользовательских данных, которые могут быть потеряны при downgrade.

Не печатай password/secret connection string.

В report допустимо показать безопасно:

```text
database host
port
database name
current_user
PostgreSQL version
```

но не пароль.

Если существует риск, что configured DB содержит реальные рабочие данные:

```text
BLOCKED - SAFE DEVELOPMENT DATABASE REQUIRED
```

и не выполнять downgrade.

---

# 5. Baseline Git state

Перед DB actions зафиксировать:

```powershell
git status --short
git log --oneline --decorate -5
git diff --check
```

Live DB acceptance не должна автоматически создавать commit.

Не удалять untracked prompts/reports.

`.env`, `.venv`, `.python312` не должны попадать в Git.

---

# 6. Database connectivity baseline

Проверить PostgreSQL connectivity через application environment.

Дополнительно допустимо использовать `psql`, если он доступен.

Минимально зафиксировать:

```sql
SELECT version();
SELECT current_database();
SELECT current_user;
SELECT current_schema();
SELECT 1;
SHOW timezone;
```

Server timezone не должен использоваться как KVC user timezone contract.

---

# 7. Pre-migration database inventory

До `alembic upgrade head` получить baseline physical inventory.

Проверить:

```text
schemas
tables in public
alembic_version existence/content
existing constraints/indexes where relevant
```

Ожидаемый baseline:

```text
public.alembic_version may already exist
KVC business tables do not yet exist
```

Если `alembic_version` существует, зафиксировать:

```sql
SELECT * FROM alembic_version;
```

Не менять её вручную.

Если любая из семи business tables уже существует неожиданно:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

не выполнять migration автоматически.

Сначала определить происхождение. Если безопасное восстановление baseline не очевидно:

```text
BLOCKED - DATABASE BASELINE NOT CLEAN
```

---

# 8. Alembic baseline

До live migration выполнить:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini heads
.venv\Scripts\python.exe -m alembic -c alembic.ini history
.venv\Scripts\python.exe -m alembic -c alembic.ini current
```

Ожидается:

```text
head: 00201_mvp_service_model
history: <base> -> 00201_mvp_service_model
current: base / empty revision state
```

Если `current` уже показывает `00201_mvp_service_model`, не продолжать вслепую — сначала проверить физическую схему.

---

# 9. First live upgrade

Выполнить:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

Ожидается:

```text
exit code 0
```

После этого:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini current
```

должен показать:

```text
00201_mvp_service_model
```

---

# 10. `alembic_version` acceptance

После upgrade проверить:

```sql
SELECT version_num FROM alembic_version;
```

Ожидается:

```text
00201_mvp_service_model
```

Не insert/update/delete `alembic_version` вручную.

---

# 11. Business table inventory

После upgrade физически подтвердить наличие ровно семи KVC business tables:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

`alembic_version` — служебная таблица Alembic, не business table.

Не должны появиться Kaiten mirror tables:

```text
boards
spaces
columns
cards
comments
attachments
card_states
kaiten_due_dates
```

---

# 12. Column/type/nullability inspection

Для каждой из семи таблиц проверить через PostgreSQL catalog / information_schema:

```text
column name
data type
nullable
default
```

Особенно:

```text
UUID
TEXT
BOOLEAN
SMALLINT
INTEGER
BYTEA
TIMESTAMP WITH TIME ZONE
JSONB
```

`DATE` не должен присутствовать в `notification_history`.

---

# 13. Final notification deadline physical acceptance

Обязательно подтвердить:

```text
notification_history.due_at
  TIMESTAMP WITH TIME ZONE
  NOT NULL
```

```text
notification_history.due_date_time_present
  BOOLEAN
  NOT NULL
```

И отсутствие:

```text
notification_history.due_date
```

Dedup key:

```text
user_id
kaiten_card_id
due_at
due_date_time_present
notification_type
```

Имя:

```text
uq_notification_history_dedup
```

Не должно быть standalone `due_at` index.

---

# 14. Server defaults inspection

Физически подтвердить accepted defaults.

## users

```text
status = 'ACTIVE'
```

## max_chats

```text
chat_type = 'PRIVATE'
is_primary = true
```

## kaiten_connections

```text
token_encryption_version = 1
status = 'ACTIVE'
```

## pending_commands

```text
arguments = versioned JSONB object
state = 'RECEIVED'
clarification_attempts = 0
```

## notification_settings

```text
enabled = false
due_soon_days = 1
timezone = 'UTC'
```

## notification_history

```text
delivery_status = 'RESERVED'
```

## timestamps

```text
created_at = now()
updated_at = now()
```

Не требуй ORM `onupdate` от PostgreSQL catalog — это application behavior.

---

# 15. PK acceptance

Проверить:

```text
pk_users
pk_max_chats
pk_kaiten_connections
pk_dialog_sessions
pk_pending_commands
pk_notification_settings
pk_notification_history
```

UUID surrogate PK не должны иметь DB UUID-generation default.

---

# 16. FK / ON DELETE acceptance

Проверить:

```text
fk_max_chats_user_id_users
  max_chats.user_id -> users.id
  ON DELETE RESTRICT

fk_kaiten_connections_user_id_users
  kaiten_connections.user_id -> users.id
  ON DELETE RESTRICT

fk_dialog_sessions_user_id_users
  dialog_sessions.user_id -> users.id
  ON DELETE RESTRICT

fk_dialog_sessions_max_chat_binding_id_max_chats
  dialog_sessions.max_chat_binding_id -> max_chats.id
  ON DELETE SET NULL

fk_pending_commands_user_id_users
  pending_commands.user_id -> users.id
  ON DELETE RESTRICT

fk_pending_commands_dialog_session_id_dialog_sessions
  pending_commands.dialog_session_id -> dialog_sessions.id
  ON DELETE CASCADE

fk_notification_settings_user_id_users
  notification_settings.user_id -> users.id
  ON DELETE RESTRICT

fk_notification_history_user_id_users
  notification_history.user_id -> users.id
  ON DELETE RESTRICT
```

---

# 17. CHECK constraint acceptance

Проверить existence/names/semantics:

```text
ck_users_status
ck_max_chats_chat_type
ck_kaiten_connections_status
ck_kaiten_connections_token_encryption_version_positive
ck_pending_commands_state
ck_pending_commands_clarification_attempts_non_negative
ck_notification_settings_due_soon_days_range
ck_notification_history_type
ck_notification_history_delivery_status
```

---

# 18. UNIQUE / partial UNIQUE acceptance

Проверить ordinary UNIQUE:

```text
uq_max_chats_max_chat_id
uq_kaiten_connections_user_id
uq_notification_history_dedup
```

Проверить partial UNIQUE:

```text
uq_max_chats_max_user_id_private
WHERE chat_type = 'PRIVATE'
```

```text
uq_max_chats_user_primary
WHERE is_primary
```

```text
uq_dialog_sessions_one_active_per_user
WHERE ended_at IS NULL
```

```text
uq_pending_commands_one_active_per_session
WHERE state IN (
  'RECEIVED',
  'PARSED',
  'RESOLVING',
  'NEEDS_CLARIFICATION',
  'READY'
)
```

Проверить именно `UNIQUE` + predicate.

---

# 19. Secondary index acceptance

Проверить ровно accepted indexes:

```text
ix_dialog_sessions_max_chat_binding_id
ix_pending_commands_user_state
ix_pending_commands_expires_at_active
ix_notification_settings_enabled_user
```

`ix_pending_commands_expires_at_active` должен иметь predicate:

```text
state IN active states
AND expires_at IS NOT NULL
```

Не должно быть duplicate indexes на accepted UNIQUE keys.

---

# 20. No ENUM / extension acceptance

Проверить, что revision не создала:

```text
custom PostgreSQL ENUM
uuid-ossp
pgcrypto
```

если они не существовали baseline.

Не удалять unrelated extensions.

---

# 21. Minimal DML acceptance

После structural inspection выполнить безопасный DML smoke-test только на synthetic rows.

Цель:

- defaults;
- FK;
- CHECK;
- partial UNIQUE;
- JSONB default;
- notification dedup.

Не использовать реальные Kaiten/MAX IDs/token.

---

# 22. DML smoke — user/defaults

Создать synthetic user, передав только UUID PK.

Проверить DB defaults:

```text
status = ACTIVE
created_at IS NOT NULL
updated_at IS NOT NULL
```

Не передавать timestamps вручную.

---

# 23. DML smoke — notification settings defaults

Создать row только с `user_id`.

Проверить:

```text
enabled = false
due_soon_days = 1
timezone = UTC
created_at IS NOT NULL
updated_at IS NOT NULL
```

---

# 24. DML smoke — pending command JSONB default

Создать минимальную цепочку:

```text
user
dialog_session
pending_command
```

не передавая:

```text
arguments
state
clarification_attempts
```

Проверить:

```json
{
  "version": 1,
  "payload": {}
}
```

и:

```text
state = RECEIVED
clarification_attempts = 0
```

---

# 25. DML smoke — CHECK constraints

Через controlled transaction/savepoint проверить rejection:

```text
users.status = INVALID
kaiten_connections.token_encryption_version = 0
pending_commands.clarification_attempts = -1
notification_settings.due_soon_days = 31
notification_history.notification_type = INVALID
```

Ожидать PostgreSQL constraint violation.

---

# 26. DML smoke — active dialog partial UNIQUE

Для одного synthetic user:

1. создать active dialog;
2. попытаться создать второй active dialog;
3. получить unique violation;
4. завершить первый (`ended_at != NULL`);
5. убедиться, что новый active dialog разрешён.

---

# 27. DML smoke — active pending command partial UNIQUE

Для одного dialog session:

1. создать active pending command;
2. попытаться создать второй;
3. получить unique violation;
4. перевести первый в terminal state, например `CANCELLED`;
5. убедиться, что новый active command разрешён.

Это DB acceptance, не runtime state-machine implementation.

---

# 28. DML smoke — MAX uniqueness

Synthetic rows:

- duplicate `max_chat_id` должен отклоняться;
- duplicate private `max_user_id` должен отклоняться;
- два `is_primary = true` для одного user должны отклоняться.

Не использовать реальные MAX IDs.

---

# 29. DML smoke — notification dedup

Создать synthetic `notification_history` row с:

```text
user_id
kaiten_card_id
due_at
due_date_time_present
notification_type
```

Не передавать `delivery_status`.

Проверить:

```text
delivery_status = RESERVED
```

Повторить точно тот же dedup tuple:

```text
expect unique violation
```

Изменить только:

```text
due_at
```

и убедиться, что row разрешена.

---

# 30. DML smoke — FK referential actions

Проверить:

## SET NULL

```text
max_chat
dialog_session.max_chat_binding_id -> max_chat
delete max_chat
dialog_session.max_chat_binding_id IS NULL
```

## CASCADE

```text
dialog_session
pending_command
delete dialog_session
pending_command deleted
```

## RESTRICT

Попытаться удалить user с дочерней row.

Ожидать FK violation.

---

# 31. Cleanup before downgrade

До downgrade удалить synthetic rows и подтвердить, что business tables пусты, если это практически удобно.

В report описать cleanup strategy.

Не оставлять искусственные acceptance data после финального upgrade.

---

# 32. Live downgrade

После успешного first-cycle acceptance выполнить:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini downgrade base
```

После этого:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini current
```

должен показывать base/no revision.

---

# 33. Post-downgrade inspection

Подтвердить отсутствие семи business tables.

Проверить `alembic_version` с учётом реального поведения Alembic.

Service table может оставаться; не удалять её вручную.

Unrelated PostgreSQL objects должны сохраниться.

---

# 34. Second live upgrade

Выполнить:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

После этого:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini current
```

ожидается:

```text
00201_mvp_service_model
```

---

# 35. Final schema reinspection

После второго upgrade повторно проверить минимум:

```text
7 business tables
alembic_version
notification_history deadline fields
all expected indexes
all expected constraints
```

Полный DML smoke второй раз повторять не обязательно, если schema fingerprint совпадает.

---

# 36. Schema fingerprint / drift check

Сформировать deterministic fingerprint после первого и второго upgrade.

Включить:

```text
tables
columns
types
nullability
defaults
PK
FK
CHECK
UNIQUE
indexes + predicates
```

Сравнить first/second fingerprint.

Они должны совпадать.

Если нет:

```text
BLOCKED - MIGRATION ROUNDTRIP DRIFT DETECTED
```

---

# 37. ORM / migration / live DB parity

Сравнить:

```text
SQLAlchemy metadata
Alembic revision
live PostgreSQL schema
```

по:

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
server defaults
```

Application-only `updated_at.onupdate` не обязан присутствовать в DDL.

---

# 38. Alembic drift detection

Если безопасно:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

После final upgrade ожидается отсутствие новых upgrade operations.

Если команда технически недоступна, зафиксировать limitation без redesign env.

---

# 39. Final project quality gate

После live migration cycle повторить:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src
```

---

# 40. Допустимые исправления

Если live PostgreSQL выявляет технический implementation defect, который однозначно нарушает frozen contract, допускается минимально исправить:

```text
ORM metadata
initial Alembic revision
tests
```

Примеры:

- wrong constraint name;
- wrong type/default;
- wrong partial predicate;
- wrong `ON DELETE`;
- migration/model drift.

После correction:

1. вернуть DB к clean baseline;
2. повторить полный upgrade/downgrade/upgrade acceptance;
3. описать correction.

Если требуется новое архитектурное решение:

```text
BLOCKED - ARCHITECTURAL DECISION REQUIRED
```

---

# 41. Архитектуру не менять

Не менять самостоятельно:

```text
seven-table inventory
UUID strategy
TEXT + CHECK
MAX private-only
one Kaiten connection per user
PendingCommand states
notification types
due_at + due_date_time_present
notification dedup tuple
ON DELETE policy
physical user deletion policy
```

---

# 42. Не выполнять

Запрещено:

- repositories;
- business services;
- token encryption implementation;
- real Kaiten token in DB test rows;
- Kaiten API calls;
- MAX API calls;
- notification worker;
- PendingCommand runtime;
- outbox;
- seed data;
- API/CLI endpoints;
- `.env` changes.

---

# 43. Git discipline

Не делать commit автоматически.

В конце:

```powershell
git status --short
git diff --check
git diff --stat
```

Не добавлять DB dumps.

---

# 44. Итоговый report

Создай:

```text
codex/reports/002_02_live_postgresql_persistence_acceptance_report.md
```

Report должен содержать минимум:

1. Executive summary.
2. Safety/development DB confirmation.
3. Runtime/Python version.
4. PostgreSQL connection summary без secrets.
5. PostgreSQL version/current DB/current user.
6. Baseline schema inventory.
7. Baseline Alembic state.
8. First `upgrade head` result.
9. `alembic_version` after first upgrade.
10. Seven-table inventory.
11. Column/type/nullability inspection.
12. Server-default inspection.
13. PK inventory.
14. FK/ON DELETE inventory.
15. CHECK inventory.
16. UNIQUE/partial UNIQUE inventory.
17. Secondary index inventory.
18. No-duplicate-index review.
19. Notification deadline physical acceptance.
20. No ENUM/extension review.
21. DML defaults smoke.
22. DML CHECK rejection smoke.
23. Active-dialog partial UNIQUE smoke.
24. Active-pending partial UNIQUE smoke.
25. MAX uniqueness smoke.
26. Notification dedup smoke.
27. FK SET NULL/CASCADE/RESTRICT smoke.
28. Synthetic data cleanup.
29. Live downgrade result.
30. Post-downgrade inventory.
31. Second live upgrade result.
32. Final `alembic_version`.
33. First/second schema fingerprint comparison.
34. ORM/migration/live DB parity.
35. `alembic check` result, если доступен.
36. Full quality gate.
37. Any corrections performed.
38. Changed files.
39. Deferred items for `002-03`.
40. Final status.

---

# 45. Changed-files classification

В report:

```text
Production code:
Alembic:
Tests:
Configuration:
Documentation:
Reports:
Database state:
Other:
```

Если correction не понадобилась:

```text
Production code:
none for 002-02

Alembic:
none for 002-02

Tests:
none for 002-02
```

Database state:

```text
final state: upgraded to 00201_mvp_service_model
```

---

# 46. Финальное состояние БД

После успешного round-trip acceptance оставить development database на:

```text
00201_mvp_service_model
```

Итоговая последовательность:

```text
upgrade
inspect/test
downgrade
inspect
upgrade
final inspect
```

Не оставлять DB в `base`.

---

# 47. Acceptance criteria

`002-02` успешен только если:

- target DB безопасна для development acceptance;
- Python 3.12 environment работает;
- PostgreSQL connection успешна;
- baseline понятен;
- first upgrade проходит;
- `alembic_version = 00201_mvp_service_model`;
- созданы ровно семь business tables;
- columns/types/nullability соответствуют contract;
- defaults соответствуют contract;
- PK/FK/ON DELETE соответствуют contract;
- CHECK соответствуют contract;
- UNIQUE/partial UNIQUE соответствуют contract;
- secondary indexes соответствуют contract;
- duplicate indexes отсутствуют;
- `due_at TIMESTAMPTZ` присутствует;
- `due_date_time_present BOOLEAN` присутствует;
- `due_date DATE` отсутствует;
- migration не добавляет ENUM/extensions;
- DB defaults реально работают;
- CHECK реально отклоняют invalid values;
- partial UNIQUE invariants реально работают;
- notification dedup реально работает;
- FK actions реально работают;
- downgrade проходит;
- после downgrade business tables отсутствуют;
- second upgrade проходит;
- first/second schema fingerprints совпадают;
- ORM/migration/live PostgreSQL parity подтверждена;
- final database state = head;
- full quality gate проходит;
- report создан.

---

# 48. Final status

Если всё прошло:

```text
ACCEPTED LIVE POSTGRESQL PERSISTENCE - READY FOR 002-03
```

Если safe development DB отсутствует:

```text
BLOCKED - SAFE DEVELOPMENT DATABASE REQUIRED
```

Если baseline загрязнён:

```text
BLOCKED - DATABASE BASELINE NOT CLEAN
```

Если round-trip даёт drift:

```text
BLOCKED - MIGRATION ROUNDTRIP DRIFT DETECTED
```

Если требуется архитектурное решение:

```text
BLOCKED - ARCHITECTURAL DECISION REQUIRED
```

---

## Главное правило

`002-02` должен доказать не то, что migration **выглядит правильной**, а то, что она **фактически корректно работает на PostgreSQL**.

Итог:

```text
upgrade
+
physical inspection
+
constraint/default smoke tests
+
downgrade
+
second upgrade
+
schema parity/drift check
```

после чего persistence layer ветки `002` можно считать физически принятым и переходить к `002-03`.
