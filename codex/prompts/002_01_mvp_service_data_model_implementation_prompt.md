# 002-01 — MVP service data model implementation: SQLAlchemy models and initial Alembic migration

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Текущая ветка разработки:

```text
002 — MVP service data model
```

Предыдущие этапы завершены и приняты:

```text
002-00   MVP service data model audit
002-00a  Final MVP service data model specification
002-00b  Kaiten deadline semantics and notification dedup correction
002-00c  Live Kaiten deadline representation acceptance probe
```

На этом этапе необходимо **реализовать замороженный persistence contract MVP**:

1. SQLAlchemy 2.x ORM models;
2. первую реальную Alembic revision;
3. автоматические structural/metadata/migration tests;
4. интеграцию моделей с существующим persistence/Alembic foundation;
5. implementation report.

Это **реализационный этап**, но **не live PostgreSQL acceptance**.

Фактическое применение migration к PostgreSQL, downgrade/upgrade, инспекция физической схемы и ручная приемка относятся к следующему этапу:

```text
002-02 — live PostgreSQL persistence acceptance
```

---

# 1. Нормативные документы и приоритет

Перед изменением кода обязательно изучи:

```text
codex/reports/002_00_mvp_service_data_model_audit_report.md
codex/reports/002_00a_mvp_service_data_model_final_specification.md
codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
```

Также изучи:

- текущую структуру `src/`;
- существующий SQLAlchemy `Base`;
- существующий `MetaData`;
- naming convention;
- engine/session foundation;
- `alembic.ini`;
- `alembic/env.py`;
- существующие migrations;
- tests;
- `pyproject.toml`;
- conventions проекта.

## Приоритет контрактов

При любых расхождениях использовать:

```text
002-00c  — highest priority for deadline representation/semantics
002-00b  — notification deadline/dedup corrections
002-00a  — основной frozen seven-table schema
002-00   — audit/background rationale
```

В частности запрещено реализовывать устаревший контракт:

```text
notification_history.due_date DATE
```

Окончательный live-verified contract:

```text
notification_history.due_at TIMESTAMPTZ NOT NULL
notification_history.due_date_time_present BOOLEAN NOT NULL
```

Если файл `002-00c` в репозитории не содержит финального статуса:

```text
ACCEPTED LIVE CONTRACT - READY FOR 002-01
```

не начинай реализацию и зафиксируй blocker.

---

# 2. Главная цель

После `002-01` репозиторий должен содержать одну согласованную persistence-модель из **ровно семи KVC-owned business tables**:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

и одну первую Alembic revision, создающую именно эту модель.

Нельзя:

- добавлять локальный cache Kaiten;
- добавлять будущие business tables;
- проектировать модель заново;
- внедрять repositories/services раньше `002-03`;
- реализовывать Kaiten/MAX integrations;
- выполнять live migration acceptance вместо `002-02`.

---

# 3. Сначала проанализируй persistence foundation

Перед реализацией зафиксируй:

```text
current SQLAlchemy Base location
current MetaData location
metadata naming convention
engine/session modules
Alembic target_metadata wiring
existing Alembic revisions
current heads/history
```

Убедись, что не создаётся второй независимый:

```text
DeclarativeBase
MetaData
```

Новые модели должны использовать **существующий Base/metadata**.

Если naming convention уже существует, не заменяй её.

Особенно проверь, чтобы итоговые имена constraint/index не получили двойные префиксы вроде:

```text
ck_users_ck_users_status
```

Если существующая naming convention требует semantic constraint name, используй её корректно.

---

# 4. SQLAlchemy implementation style

Использовать текущий SQLAlchemy 2.x typed declarative style.

Предпочтительно:

```python
Mapped[...]
mapped_column(...)
```

если это соответствует foundation проекта.

Не вводить legacy API без необходимости.

## PostgreSQL physical types

Первая migration использует:

```text
UUID
TEXT
BOOLEAN
SMALLINT
INTEGER
BYTEA
TIMESTAMPTZ
JSONB
```

`DATE` не используется.

Mappings должны компилироваться в соответствующие PostgreSQL types.

Ориентиры:

```text
UUID        -> UUID(as_uuid=True)
TEXT        -> Text
BOOLEAN     -> Boolean
SMALLINT    -> SmallInteger
INTEGER     -> Integer
BYTEA       -> LargeBinary / PostgreSQL BYTEA-compatible
TIMESTAMPTZ -> DateTime(timezone=True)
JSONB       -> PostgreSQL JSONB
```

Не использовать PostgreSQL ENUM.

Finite states:

```text
TEXT + CHECK
```

Python enums/constants допустимы только если физический DB type остаётся `TEXT`.

---

# 5. UUID contract

Internal PK используют:

```text
UUID
```

UUID генерируется приложением:

```python
default = uuid.uuid4
```

Не использовать:

```text
gen_random_uuid()
uuid-ossp
server-side UUID generation
BIGINT identity
```

Migration не должна создавать PostgreSQL extension.

---

# 6. Timestamp contract

Все instants:

```text
TIMESTAMPTZ
```

Включая:

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

Для:

```text
created_at
updated_at
```

использовать server default:

```text
now()
```

`updated_at` дополнительно должен обновляться application-side/ORM при изменении строки.

Не добавлять DB trigger.

Python datetimes должны быть timezone-aware.

---

# 7. `users`

Реализовать:

```text
id          UUID        NOT NULL PK, application uuid4
status      TEXT        NOT NULL DEFAULT 'ACTIVE'
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(), application-updated
```

CHECK:

```text
ck_users_status
status IN ('ACTIVE', 'DISABLED')
```

Secondary indexes:

```text
none
```

Не добавлять поля вне frozen contract.

---

# 8. `max_chats`

Поля:

```text
id            UUID        NOT NULL PK, application uuid4
user_id       UUID        NOT NULL FK -> users.id
max_user_id   TEXT        NOT NULL
max_chat_id   TEXT        NOT NULL
chat_type     TEXT        NOT NULL DEFAULT 'PRIVATE'
is_primary    BOOLEAN     NOT NULL DEFAULT true
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(), application-updated
```

FK:

```text
fk_max_chats_user_id_users
user_id -> users.id ON DELETE RESTRICT
```

UNIQUE:

```text
uq_max_chats_max_chat_id
UNIQUE (max_chat_id)
```

Partial UNIQUE:

```text
uq_max_chats_max_user_id_private
UNIQUE (max_user_id)
WHERE chat_type = 'PRIVATE'
```

```text
uq_max_chats_user_primary
UNIQUE (user_id)
WHERE is_primary
```

CHECK:

```text
ck_max_chats_chat_type
chat_type IN ('PRIVATE')
```

Не создавать дублирующие indexes поверх UNIQUE.

---

# 9. `kaiten_connections`

Поля:

```text
id                        UUID        NOT NULL PK, application uuid4
user_id                   UUID        NOT NULL FK -> users.id, UNIQUE
api_base_url              TEXT        NOT NULL
kaiten_user_id            TEXT        NULL
workspace_id              TEXT        NULL
encrypted_api_token       BYTEA       NOT NULL
token_encryption_version  SMALLINT    NOT NULL DEFAULT 1
status                    TEXT        NOT NULL DEFAULT 'ACTIVE'
last_verified_at          TIMESTAMPTZ NULL
created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(), application-updated
```

FK:

```text
fk_kaiten_connections_user_id_users
user_id -> users.id ON DELETE RESTRICT
```

UNIQUE:

```text
uq_kaiten_connections_user_id
UNIQUE (user_id)
```

CHECK:

```text
ck_kaiten_connections_status
status IN ('ACTIVE', 'DISABLED', 'NEEDS_REAUTH')
```

```text
ck_kaiten_connections_token_encryption_version_positive
token_encryption_version > 0
```

Secondary indexes:

```text
none
```

## Secret boundary

На этом этапе не реализовывать encryption.

Запрещено:

- хранить plaintext Kaiten token;
- логировать token;
- использовать реальный token в tests;
- включать `.env` values в report;
- включать secret payload в migration.

---

# 10. `dialog_sessions`

Поля:

```text
id                    UUID        NOT NULL PK, application uuid4
user_id               UUID        NOT NULL FK -> users.id
max_chat_binding_id   UUID        NULL FK -> max_chats.id
current_board_id      TEXT        NULL
current_board_name    TEXT        NULL
current_card_id       TEXT        NULL
current_card_title    TEXT        NULL
previous_user_message TEXT        NULL
previous_bot_message  TEXT        NULL
last_card_list        JSONB       NULL
last_card_list_at     TIMESTAMPTZ NULL
expires_at            TIMESTAMPTZ NULL
ended_at              TIMESTAMPTZ NULL
created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(), application-updated
```

Важно:

```text
max_chat_binding_id
```

— внутренний FK на `max_chats.id`.

Имя:

```text
max_chat_id
```

зарезервировано за внешним MAX ID.

FK:

```text
fk_dialog_sessions_user_id_users
user_id -> users.id ON DELETE RESTRICT
```

```text
fk_dialog_sessions_max_chat_binding_id_max_chats
max_chat_binding_id -> max_chats.id ON DELETE SET NULL
```

Partial UNIQUE:

```text
uq_dialog_sessions_one_active_per_user
UNIQUE (user_id)
WHERE ended_at IS NULL
```

Secondary index:

```text
ix_dialog_sessions_max_chat_binding_id
(max_chat_binding_id)
```

No JSONB GIN index.

---

# 11. `pending_commands`

Поля:

```text
id                      UUID        NOT NULL PK, application uuid4
user_id                 UUID        NOT NULL FK -> users.id
dialog_session_id       UUID        NOT NULL FK -> dialog_sessions.id
intent                  TEXT        NOT NULL
original_message        TEXT        NOT NULL
arguments               JSONB       NOT NULL DEFAULT {"version":1,"payload":{}}
unresolved_entity       JSONB       NULL
candidates              JSONB       NULL
state                   TEXT        NOT NULL DEFAULT 'RECEIVED'
failure_reason          TEXT        NULL
clarification_attempts  INTEGER     NOT NULL DEFAULT 0
expires_at              TIMESTAMPTZ NULL
executed_at              TIMESTAMPTZ NULL
created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(), application-updated
```

`arguments` server default должен быть реальным JSONB default.

FK:

```text
fk_pending_commands_user_id_users
user_id -> users.id ON DELETE RESTRICT
```

```text
fk_pending_commands_dialog_session_id_dialog_sessions
dialog_session_id -> dialog_sessions.id ON DELETE CASCADE
```

CHECK:

```text
ck_pending_commands_state
state IN (
  'RECEIVED',
  'PARSED',
  'RESOLVING',
  'NEEDS_CLARIFICATION',
  'READY',
  'EXECUTED',
  'FAILED',
  'CANCELLED',
  'EXPIRED'
)
```

```text
ck_pending_commands_clarification_attempts_non_negative
clarification_attempts >= 0
```

Partial UNIQUE:

```text
uq_pending_commands_one_active_per_session
UNIQUE (dialog_session_id)
WHERE state IN (
  'RECEIVED',
  'PARSED',
  'RESOLVING',
  'NEEDS_CLARIFICATION',
  'READY'
)
```

Secondary indexes:

```text
ix_pending_commands_user_state
(user_id, state)
```

```text
ix_pending_commands_expires_at_active
(expires_at)
WHERE state IN (
  'RECEIVED',
  'PARSED',
  'RESOLVING',
  'NEEDS_CLARIFICATION',
  'READY'
)
AND expires_at IS NOT NULL
```

No JSONB GIN indexes.

---

# 12. PendingCommand ownership invariant

Frozen invariant:

```text
pending_commands.user_id == dialog_sessions.user_id
where pending_commands.dialog_session_id = dialog_sessions.id
```

Не добавлять ради него:

```text
composite FK
DB trigger
global before_flush hook
```

В `002-01`:

- сохранить оба обычных FK;
- документировать invariant;
- не создавать repository layer;
- runtime enforcement отложить до `002-03`.

В report явно указать:

```text
ownership invariant schema representation: implemented
runtime cross-row enforcement: deferred to 002-03
```

Это не blocker для migration.

---

# 13. `notification_settings`

Поля:

```text
user_id       UUID        NOT NULL PK, FK -> users.id
enabled       BOOLEAN     NOT NULL DEFAULT false
due_soon_days INTEGER     NOT NULL DEFAULT 1
timezone      TEXT        NOT NULL DEFAULT 'UTC'
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(), application-updated
```

FK:

```text
fk_notification_settings_user_id_users
user_id -> users.id ON DELETE RESTRICT
```

CHECK:

```text
ck_notification_settings_due_soon_days_range
due_soon_days BETWEEN 0 AND 30
```

Secondary index:

```text
ix_notification_settings_enabled_user
(enabled, user_id)
```

IANA timezone validation — application-level, не DB-level на этом этапе.

---

# 14. `notification_history` — final live-verified contract

Поля:

```text
id                     UUID        NOT NULL PK, application uuid4
user_id                UUID        NOT NULL FK -> users.id
kaiten_card_id         TEXT        NOT NULL
due_at                 TIMESTAMPTZ NOT NULL
due_date_time_present  BOOLEAN     NOT NULL
notification_type      TEXT        NOT NULL
delivery_status        TEXT        NOT NULL DEFAULT 'RESERVED'
sent_at                TIMESTAMPTZ NULL
failed_at              TIMESTAMPTZ NULL
error_type             TEXT        NULL
created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(), application-updated
```

Запрещено создавать:

```text
due_date DATE
```

FK:

```text
fk_notification_history_user_id_users
user_id -> users.id ON DELETE RESTRICT
```

UNIQUE:

```text
uq_notification_history_dedup
UNIQUE (
  user_id,
  kaiten_card_id,
  due_at,
  due_date_time_present,
  notification_type
)
```

CHECK:

```text
ck_notification_history_type
notification_type IN ('DUE_SOON', 'DUE_TODAY', 'OVERDUE')
```

```text
ck_notification_history_delivery_status
delivery_status IN ('RESERVED', 'SENT', 'FAILED')
```

Secondary indexes:

```text
none
```

---

# 15. Live-verified deadline rules

`002-00c` доказал следующий Kaiten behavior.

## Date-only

Input:

```text
2026-09-20
due_date_time_present = false
```

Read-back:

```text
2026-09-20T00:00:00.000Z
due_date_time_present = false
```

Rule:

```text
if due_date_time_present is false:
    selected_due_date = UTC calendar date component of due_at
```

Запрещено timezone-convert `due_at` через user timezone для восстановления date-only даты.

`notification_settings.timezone` используется только для определения:

```text
today_for_user
```

## Date-time

Если:

```text
due_date_time_present = true
```

`due_at` — точный instant.

Live probe также выявил Kaiten normalization:

```text
12:00:00.000Z -> 12:00:59.999Z
18:00:00.000Z -> 18:00:59.999Z
```

Будущий Kaiten adapter должен использовать read-back Kaiten value для dedup identity.

В `002-01` adapter и notification classification не реализовывать.

Но schema/tests/documentation не должны противоречить этим правилам.

---

# 16. JSONB boundary

Физические JSONB columns:

```text
dialog_sessions.last_card_list
pending_commands.arguments
pending_commands.unresolved_entity
pending_commands.candidates
```

Они остаются transient/versioned application payload.

Не создавать:

- дополнительные normalized tables;
- JSON schema infrastructure;
- JSONB GIN indexes.

`pending_commands.arguments` default:

```json
{
  "version": 1,
  "payload": {}
}
```

---

# 17. ORM relationships

Relationships добавлять только там, где они действительно упрощают mapping.

Если добавляются:

- typed relationships;
- `back_populates`;
- не допускать ORM cascade, противоречащий DB `ON DELETE`;
- учитывать `passive_deletes` только если это согласуется с foundation проекта;
- не помещать бизнес-логику в relationship config.

DB constraints остаются источником истины для referential actions.

---

# 18. Alembic integration

Убедись, что `alembic/env.py` использует metadata, в которой зарегистрированы все семь моделей.

Не создавать новый Alembic environment.

Не ломать async foundation ветки `001`.

Если нужен aggregation module/import registry — реализовать минимально.

После import:

```text
Base.metadata.tables
```

должен содержать семь KVC business tables.

`alembic_version` не входит в ORM business metadata.

---

# 19. Первая Alembic revision

Перед созданием выполнить:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini heads
.venv\Scripts\python.exe -m alembic -c alembic.ini history
```

Ожидаемый baseline:

```text
no existing revisions
```

Если revision уже есть — не создавать второй root, сначала исследовать.

Предпочтительный revision id:

```text
00201_mvp_service_model
```

если это совместимо с текущими Alembic/project conventions.

Message:

```text
add MVP service data model
```

---

# 20. Autogenerate discipline

Допускается:

```text
alembic revision --autogenerate
```

но migration обязательно проверить вручную.

Не допускать:

- drop unrelated objects;
- alter unrelated infrastructure;
- extension creation;
- seed data;
- ручные изменения `alembic_version`;
- неожиданные schema operations.

Autogenerate — инструмент, не источник контракта.

---

# 21. Upgrade order

Создание:

```text
1. users
2. max_chats
3. kaiten_connections
4. dialog_sessions
5. pending_commands
6. notification_settings
7. notification_history
8. partial UNIQUE / secondary indexes
```

---

# 22. Downgrade order

Удаление:

```text
1. notification_history
2. notification_settings
3. pending_commands
4. dialog_sessions
5. kaiten_connections
6. max_chats
7. users
```

Не затрагивать:

```text
alembic_version
unrelated infrastructure
.env
```

---

# 23. Partial UNIQUE/index predicates

Реализовать PostgreSQL-native partial indexes.

## MAX private identity

```text
uq_max_chats_max_user_id_private
UNIQUE (max_user_id)
WHERE chat_type = 'PRIVATE'
```

## MAX primary chat

```text
uq_max_chats_user_primary
UNIQUE (user_id)
WHERE is_primary
```

## Active dialog

```text
uq_dialog_sessions_one_active_per_user
UNIQUE (user_id)
WHERE ended_at IS NULL
```

## Active pending command

```text
uq_pending_commands_one_active_per_session
UNIQUE (dialog_session_id)
WHERE state IN (
  'RECEIVED',
  'PARSED',
  'RESOLVING',
  'NEEDS_CLARIFICATION',
  'READY'
)
```

## Active expiration scan

```text
ix_pending_commands_expires_at_active
(expires_at)
WHERE state IN (
  'RECEIVED',
  'PARSED',
  'RESOLVING',
  'NEEDS_CLARIFICATION',
  'READY'
)
AND expires_at IS NOT NULL
```

Использовать корректный SQLAlchemy PostgreSQL dialect mechanism:

```text
Index(..., unique=True, postgresql_where=...)
```

или эквивалент.

---

# 24. Server defaults

Реализовать только accepted defaults.

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
arguments = '{"version":1,"payload":{}}'::jsonb
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

UUID PK не имеют server default.

---

# 25. Constraint/index inventory

Физическая схема должна содержать:

## CHECK

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

## UNIQUE / partial UNIQUE

```text
uq_max_chats_max_chat_id
uq_max_chats_max_user_id_private
uq_max_chats_user_primary
uq_kaiten_connections_user_id
uq_dialog_sessions_one_active_per_user
uq_pending_commands_one_active_per_session
uq_notification_history_dedup
```

## Secondary indexes

```text
ix_dialog_sessions_max_chat_binding_id
ix_pending_commands_user_state
ix_pending_commands_expires_at_active
ix_notification_settings_enabled_user
```

Не создавать duplicate indexes.

---

# 26. Tests — обязательный минимум

Добавить автоматические tests, не требующие live Kaiten и по возможности не мутирующие configured PostgreSQL.

## 26.1 Metadata inventory

Проверить:

```text
все семь models импортируются
все семь tables зарегистрированы в Base.metadata
нет восьмой неожиданной KVC business table
```

## 26.2 Columns

Для каждой таблицы проверить:

- columns;
- nullability;
- PK;
- FK targets;
- `ondelete`;
- types;
- server defaults.

## 26.3 Constraints

Проверить наличие и exact names:

```text
CHECK
UNIQUE
partial UNIQUE
```

## 26.4 Partial predicates

Через PostgreSQL dialect compilation проверить semantics partial indexes.

Особенно:

```text
one active dialog per user
one active pending command per session
one primary MAX chat per user
private MAX user uniqueness
active pending expiration scan
```

## 26.5 No duplicate indexes

Добавить targeted assertions для known accepted index inventory.

## 26.6 Notification deadline

Обязательно проверить:

```text
notification_history has due_at
notification_history has due_date_time_present
notification_history does NOT have due_date
due_at is timezone-aware datetime mapping
dedup key includes due_at + due_date_time_present
```

## 26.7 JSONB

Проверить:

```text
last_card_list -> JSONB
arguments -> JSONB
unresolved_entity -> JSONB
candidates -> JSONB
```

Проверить server default `arguments`.

## 26.8 UUID

Проверить application-generated UUID default callable.

## 26.9 Migration structure

Проверить:

- одна head revision;
- корректный `down_revision`;
- семь `create_table`;
- нет `DATE`;
- нет PostgreSQL ENUM;
- нет extension creation;
- downgrade удаляет семь business tables.

---

# 27. Offline Alembic verification

Live DB schema в `002-01` не менять.

Разрешены:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini heads
.venv\Scripts\python.exe -m alembic -c alembic.ini history
```

После revision:

```text
one head
history contains initial MVP revision
```

По возможности выполнить:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head --sql
```

Если async env не поддерживает offline render, не переписывай его только ради этого — зафиксируй limitation.

---

# 28. Что НЕ выполнять

На configured/live PostgreSQL не выполнять:

```text
alembic upgrade head
alembic downgrade
manual CREATE TABLE
manual DROP TABLE
manual schema patch
```

Не выполнять:

- live Kaiten mutations;
- MAX calls;
- token encryption implementation;
- repositories;
- business services;
- PendingCommand state machine runtime;
- notification classification;
- worker/retries;
- outbox;
- seed data;
- API/CLI admin commands для новых business tables;
- `.env` changes.

---

# 29. Existing `alembic_version`

Если в PostgreSQL уже существует пустая:

```text
public.alembic_version
```

это service table Alembic.

Не добавлять её в ORM.

Не удалять/пересоздавать вручную.

Фактическая миграция будет проверена в `002-02`.

---

# 30. Source-of-truth boundary

После implementation не должно появиться таблиц:

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

Допустимы только:

- external IDs;
- encrypted Kaiten token;
- transient JSON context;
- notification deadline dedup marker.

Добавить regression test/table inventory assertion.

---

# 31. Model/migration parity

Проверить, что ORM metadata и revision совпадают по:

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

Не оставлять autogenerate drift сразу после создания migration.

---

# 32. Кодовая организация

Следовать существующей структуре проекта.

Не навязывать новую hierarchy без необходимости.

Предпочтительно:

- coherent models package;
- existing Base отдельно;
- aggregation import только при необходимости Alembic;
- no circular imports;
- no wildcard side effects.

Не смешивать ORM models с:

```text
Kaiten HTTP DTO
MAX DTO
LLM schemas
business handlers
```

---

# 33. Quality

Новый код должен проходить:

```text
pytest
pytest -W error
ruff format
ruff check
mypy
```

Не маскировать проблемы массовыми:

```text
# type: ignore
# noqa
```

---

# 34. Full quality gate

После реализации выполнить:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip check

.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error

.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src

.venv\Scripts\python.exe -m alembic -c alembic.ini heads
.venv\Scripts\python.exe -m alembic -c alembic.ini history

git diff --check
git status --short
git diff --stat
```

Дополнительно отдельно показать targeted tests нового persistence layer.

---

# 35. Git discipline

Не делать commit автоматически.

Перед работой:

```powershell
git status --short
git log --oneline --decorate -5
git diff --check
```

Не удалять untracked prompts/reports предыдущих этапов.

`.env` не изменять и не добавлять в Git.

---

# 36. Implementation report

Создай:

```text
codex/reports/002_01_mvp_service_data_model_implementation_report.md
```

Отчёт должен содержать минимум:

1. Executive summary.
2. Contract precedence (`002-00a/00b/00c`).
3. Baseline repository state.
4. Existing persistence/Alembic foundation.
5. Model package/files.
6. Final seven-table inventory.
7. Column/type/nullability/default inventory.
8. PK/FK/ON DELETE inventory.
9. CHECK inventory.
10. UNIQUE/partial UNIQUE inventory.
11. Secondary index inventory.
12. No-duplicate-index review.
13. JSONB mapping review.
14. Secret field handling.
15. UUID generation.
16. Timestamp/TIMESTAMPTZ contract.
17. Final notification deadline implementation.
18. Confirmation `DATE` absent.
19. Confirmation `due_at + due_date_time_present` present.
20. PendingCommand ownership invariant scope.
21. Alembic revision id/message/down_revision.
22. Upgrade inventory.
23. Downgrade inventory.
24. Model/migration parity review.
25. Alembic heads/history.
26. Offline migration verification.
27. Tests added/updated.
28. Full quality gate.
29. Changed files.
30. Explicit out-of-scope.
31. Risks/deferred items for `002-02`/`002-03`.
32. Final status.

---

# 37. Changed-files classification

В report отдельно:

```text
Production code:
Alembic:
Tests:
Configuration:
Documentation:
Reports:
Other:
```

Любое изменение `alembic/env.py` перечислить в `Configuration`.

`.env`:

```text
must remain unchanged
```

---

# 38. Acceptance criteria

`002-01` успешен только если:

- реализованы ровно семь frozen business models;
- используется существующий Base/metadata;
- UUID генерируются приложением;
- physical PostgreSQL types соответствуют contract;
- `TEXT + CHECK`, без PostgreSQL ENUM;
- FK имеют правильный `ON DELETE`;
- exact named constraints/indexes присутствуют;
- partial indexes PostgreSQL-compatible;
- duplicate indexes отсутствуют;
- JSONB mappings корректны;
- `pending_commands.arguments` имеет JSONB default;
- `notification_history.due_at` — `TIMESTAMPTZ`;
- `notification_history.due_date_time_present` — `BOOLEAN`;
- `notification_history.due_date` отсутствует;
- dedup UNIQUE использует final tuple;
- migration создаёт ровно семь business tables;
- downgrade симметричен;
- Kaiten mirror tables отсутствуют;
- encryption/repositories/services/workers не реализованы;
- live PostgreSQL schema в этом этапе не мутировала;
- tests проходят;
- `pytest -W error` проходит;
- Ruff проходит;
- mypy проходит;
- Alembic имеет одну ожидаемую head revision;
- report создан.

---

# 39. Final status

Если implementation и offline checks успешны:

```text
IMPLEMENTED - READY FOR 002-02 LIVE POSTGRESQL ACCEPTANCE
```

Если обнаружено расхождение frozen contract, которое требует нового архитектурного решения:

```text
BLOCKED - ARCHITECTURAL DECISION REQUIRED
```

Проблемы live PostgreSQL access не должны блокировать code-level completion `002-01`, поскольку live acceptance относится к `002-02`.

---

## Главное правило

`002-01` **не проектирует модель заново**.

Он буквально переводит:

```text
002-00a
+ corrections 002-00b
+ live-verified final contract 002-00c
```

в SQLAlchemy metadata и одну initial Alembic migration.

Любое изменение fields, types, constraints, indexes, delete semantics или ownership boundary запрещено без отдельного архитектурного решения.
