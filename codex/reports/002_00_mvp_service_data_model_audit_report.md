# 002-00 — MVP service data model audit report

## Executive summary

Baseline branch `001` is ready as infrastructure for branch `002`: PostgreSQL, async SQLAlchemy, asyncpg, Alembic, settings, tests, lint, and type checks are in place. The repository starts this audit from commit `0501ca3 feat: add PostgreSQL persistence foundation`; the only uncommitted item at audit start was the prompt file `codex/prompts/002_00_mvp_service_data_model_audit_prompt.md`.

The MVP needs seven service-owned tables:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

No table should store a permanent copy of Kaiten boards, cards, comments, due dates, attachments, columns, or card state. KVC stores only internal identity, user configuration, encrypted Kaiten access, transient dialog context, pending command state, and notification dedup/audit state.

Final audit status: `READY WITH DECISIONS REQUIRED`. Implementation should wait for explicit confirmation of the decisions listed near the end of this report.

## Source requirements

Requirements that directly affect KVC-owned data:

- Kaiten is the only source of truth for spaces, boards, columns, cards, comments, due dates, attachments, and card position/state.
- KVC is multi-user from the start.
- Each user connects their own Kaiten account.
- MAX identity/chat must be bound to a concrete KVC user.
- Dialog context is mandatory and must include current board, current card, previous user message, previous bot message, last card list, and pending command.
- A pending command must preserve the original user command while entity resolution or clarification is in progress.
- Pending command lifecycle from the specification: `RECEIVED -> PARSED -> RESOLVING -> NEEDS_CLARIFICATION -> READY -> EXECUTED`, with repeated `RESOLVING <-> NEEDS_CLARIFICATION`.
- Notification settings must support `/notify on`, `/notify off`, `/notify status`, and a configurable due-soon threshold.
- Notification history must prevent duplicate notifications by `user_id`, `card_id`, `due_date`, and `notification_type`.
- Kaiten API tokens must be encrypted at rest.
- Global application secrets must not be stored in the service database.
- Background worker may read Kaiten and send MAX notifications, but must not mutate Kaiten.

No newer specification or architecture document was found that overrides the MVP specification.

## Current persistence baseline

Git baseline:

```text
git status --short
?? codex/prompts/002_00_mvp_service_data_model_audit_prompt.md

git log --oneline --decorate -5
0501ca3 (HEAD -> main) feat: add PostgreSQL persistence foundation
4e4d728 chore: bootstrap Kaiten Voice Control project

git diff --check
<no output, exit code 0>
```

Branch-001 implementation is committed in `0501ca3`. The audit prompt is untracked and is not an architecture implementation change.

PostgreSQL/Alembic baseline:

```text
python -m alembic -c alembic.ini heads
<no output, exit code 0>

python -m alembic -c alembic.ini history
<no output, exit code 0>

python -m alembic -c alembic.ini current
<no output, exit code 0>
```

Current user tables:

```text
public.alembic_version
```

`public.alembic_version` is an empty Alembic service table created during `001-02a` online diagnostics. There are no KVC business tables and no Alembic revisions.

## Data ownership

| Data | Source of truth | Stored in KVC DB | Storage format | Reason |
|---|---|---:|---|---|
| Kaiten board | Kaiten | Partial/transient only | `current_board_id` as `TEXT`, optional display snapshot in dialog context | Resolve later commands like "this board"; not a board cache |
| Kaiten card | Kaiten | Partial/transient only | `current_card_id`, candidate refs, notification `kaiten_card_id` as `TEXT` | Context, pending resolution, notification dedup |
| Kaiten comments | Kaiten | No | Not stored | Summary reads live Kaiten comments |
| Kaiten due date | Kaiten | Only notification dedup marker | `DATE` in `notification_history.due_date` | A due-date change must create a new notification event key |
| Kaiten attachments | Kaiten | No | Not stored | Photos are read/attached through Kaiten APIs |
| Kaiten columns | Kaiten | Transient candidates only | JSONB candidate references | Resolver context; not a local column registry |
| Current board | Dialog context | Yes | External ID plus optional name snapshot | Needed after `/use` and for implicit commands |
| Current card | Dialog context | Yes | External ID plus optional title snapshot | Needed for pronouns and commands like "add comment there" |
| MAX identity | MAX | Yes | `TEXT` external IDs in `max_chats` | Route incoming messages and send replies |
| Kaiten token | User secret | Yes | Encrypted bytes/text, never plaintext | Needed for per-user Kaiten access |
| Dialog context | KVC | Yes | Scalar refs plus bounded JSONB snapshots | Must survive restart, but expire |
| PendingCommand | KVC | Yes | Row plus JSONB arguments/candidates | Multi-step clarification and safe execution |
| Notification settings | KVC | Yes | Boolean/threshold/timezone | User preferences |
| Notification history | KVC | Yes | Dedup key plus delivery status | Prevent duplicate polling notifications |
| GigaChat credentials | Environment/secret storage | No | Not stored | Global provider secret |
| MAX bot token | Environment/secret storage | No | Not stored | Global bot secret |
| DB password | Environment/secret storage | No | Not stored | Infrastructure secret |
| Token encryption key | Environment/secret storage | No | Not stored | Must not be in PostgreSQL |

## Candidate schema

### `users`

Responsibility: stable internal KVC user identity and account-level service status.

Recommended PK: `UUID`. It avoids exposing a sequential user count if IDs later cross API or logs. It also keeps internal identity separate from MAX and Kaiten external IDs. Application-generated UUIDs are preferable initially to avoid requiring a PostgreSQL extension just for ID generation.

| Field | PostgreSQL type | NULL | Default | Constraint | Purpose |
|---|---|---:|---|---|---|
| `id` | `UUID` | No | application `uuid4` | PK | Internal KVC user identity |
| `status` | `TEXT` | No | `'ACTIVE'` | CHECK `ck_users_status` in `ACTIVE`, `DISABLED` | Disable service access without physical delete |
| `created_at` | `TIMESTAMPTZ` | No | application/server UTC now |  | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | No | application/server UTC now |  | Last account metadata change |

PK: `users.id`.

UNIQUE: none.

CHECK:

```text
ck_users_status: status IN ('ACTIVE', 'DISABLED')
```

Indexes:

- no initial secondary index; most lookups enter through `max_chats`.

Delete policy:

- Prefer no physical user delete in MVP. Use `DISABLED`.
- If physical delete is later required, it must be a separate explicit operation because it touches encrypted tokens, dialog context, and audit/dedup rows.

Data classes:

- `id`, `status`: persistent identity/configuration.
- timestamps: persistent audit metadata.

### `max_chats`

Responsibility: bind MAX user/chat identity to a KVC user.

External ID policy: use `TEXT` until MAX integration verifies exact ID type and range. Do not lock the first migration to `INTEGER`.

MVP recommendation: private one-to-one chat only. Group chat support should be rejected at the application boundary until explicitly designed.

| Field | PostgreSQL type | NULL | Default | Constraint | Purpose |
|---|---|---:|---|---|---|
| `id` | `UUID` | No | application `uuid4` | PK | Internal chat binding ID |
| `user_id` | `UUID` | No |  | FK to `users.id` | Owner KVC user |
| `max_user_id` | `TEXT` | No |  |  | MAX user external ID |
| `max_chat_id` | `TEXT` | No |  |  | MAX chat external ID |
| `chat_type` | `TEXT` | No | `'PRIVATE'` | CHECK `ck_max_chats_chat_type` | Private chat for MVP |
| `is_primary` | `BOOLEAN` | No | `true` |  | Main chat for notifications/replies |
| `created_at` | `TIMESTAMPTZ` | No | UTC now |  | Binding creation |
| `updated_at` | `TIMESTAMPTZ` | No | UTC now |  | Binding update |

PK: `max_chats.id`.

FK:

```text
max_chats.user_id -> users.id ON DELETE RESTRICT
```

UNIQUE:

```text
uq_max_chats_max_chat_id: max_chat_id
uq_max_chats_max_user_id_private: max_user_id WHERE chat_type = 'PRIVATE'
uq_max_chats_user_primary: user_id WHERE is_primary
```

CHECK:

```text
ck_max_chats_chat_type: chat_type IN ('PRIVATE')
```

Indexes:

- `ix_max_chats_max_chat_id` for incoming message routing.
- `ix_max_chats_max_user_id` for binding lookup/debug.
- `ix_max_chats_user_id` only if SQLAlchemy/Alembic does not already create a usable unique/partial index for user lookup.

Delete policy:

- `RESTRICT` on user delete until account deletion is explicitly designed.

Data classes:

- MAX IDs: external references.
- `is_primary`: persistent configuration.
- timestamps: persistent audit metadata.

### `kaiten_connections`

Responsibility: per-user Kaiten access configuration.

External ID policy: all Kaiten account/workspace/space IDs should be `TEXT` until Kaiten API contracts are audited.

| Field | PostgreSQL type | NULL | Default | Constraint | Purpose |
|---|---|---:|---|---|---|
| `id` | `UUID` | No | application `uuid4` | PK | Internal connection ID |
| `user_id` | `UUID` | No |  | FK to `users.id` | Owner KVC user |
| `api_base_url` | `TEXT` | No |  |  | Kaiten endpoint, if deployments differ |
| `kaiten_user_id` | `TEXT` | Yes |  |  | Optional verified Kaiten account ID |
| `workspace_id` | `TEXT` | Yes |  |  | Optional external workspace/account scope |
| `encrypted_api_token` | `BYTEA` or `TEXT` | No |  |  | Encrypted token payload |
| `token_encryption_version` | `SMALLINT` | No | `1` | CHECK positive | Key/algorithm version marker |
| `status` | `TEXT` | No | `'ACTIVE'` | CHECK `ck_kaiten_connections_status` | Connection usability |
| `last_verified_at` | `TIMESTAMPTZ` | Yes |  |  | Last successful credential check |
| `created_at` | `TIMESTAMPTZ` | No | UTC now |  | Connection creation |
| `updated_at` | `TIMESTAMPTZ` | No | UTC now |  | Connection update |

PK: `kaiten_connections.id`.

FK:

```text
kaiten_connections.user_id -> users.id ON DELETE RESTRICT
```

UNIQUE:

```text
uq_kaiten_connections_user_id: user_id
```

The unique user constraint encodes one Kaiten connection per user for MVP. Multiple connections/spaces can be added later after a separate architecture decision.

CHECK:

```text
ck_kaiten_connections_status: status IN ('ACTIVE', 'DISABLED', 'NEEDS_REAUTH')
ck_kaiten_connections_token_encryption_version_positive: token_encryption_version > 0
```

Indexes:

- `ix_kaiten_connections_user_id` is covered by the unique constraint.
- Optional `ix_kaiten_connections_status` only if worker/admin queries by status become common; not required for first migration.

Delete policy:

- `RESTRICT` by default. Disable a connection via `status`, do not delete token-bearing rows casually.

Data classes:

- token: secret.
- user/base URL/status: persistent configuration.
- Kaiten IDs: external references.

### `dialog_sessions`

Responsibility: bounded conversation context that survives process restart.

MVP recommendation: one active dialog session per user. Keep historical sessions only until TTL/cleanup, not as a permanent message log.

| Field | PostgreSQL type | NULL | Default | Constraint | Purpose |
|---|---|---:|---|---|---|
| `id` | `UUID` | No | application `uuid4` | PK | Internal session ID |
| `user_id` | `UUID` | No |  | FK to `users.id` | Session owner |
| `max_chat_id` | `UUID` | Yes |  | FK to `max_chats.id` | Chat context source |
| `current_board_id` | `TEXT` | Yes |  |  | Kaiten board external ID |
| `current_board_name` | `TEXT` | Yes |  |  | Display snapshot only |
| `current_card_id` | `TEXT` | Yes |  |  | Kaiten card external ID |
| `current_card_title` | `TEXT` | Yes |  |  | Display snapshot only |
| `previous_user_message` | `TEXT` | Yes |  |  | Previous user text for clarification |
| `previous_bot_message` | `TEXT` | Yes |  |  | Previous bot text for clarification |
| `last_card_list` | `JSONB` | Yes |  | CHECK object/array by app contract | Bounded candidate/list snapshot |
| `last_card_list_at` | `TIMESTAMPTZ` | Yes |  |  | Freshness marker for ordinal references |
| `expires_at` | `TIMESTAMPTZ` | Yes |  |  | Session context TTL |
| `ended_at` | `TIMESTAMPTZ` | Yes |  |  | Marks inactive session |
| `created_at` | `TIMESTAMPTZ` | No | UTC now |  | Session creation |
| `updated_at` | `TIMESTAMPTZ` | No | UTC now |  | Last context update |

PK: `dialog_sessions.id`.

FK:

```text
dialog_sessions.user_id -> users.id ON DELETE RESTRICT
dialog_sessions.max_chat_id -> max_chats.id ON DELETE SET NULL
```

UNIQUE / partial unique:

```text
uq_dialog_sessions_one_active_per_user: user_id WHERE ended_at IS NULL
```

Indexes:

- partial unique active-session index above for `user -> active dialog session`.
- `ix_dialog_sessions_max_chat_id` if sessions are retrieved through chat binding.
- no JSONB GIN index initially.

Delete policy:

- User delete `RESTRICT`.
- MAX chat delete `SET NULL` preserves session history/context until cleanup.
- Expired/ended sessions may be hard-deleted by a future cleanup job after TTL.

Data classes:

- current board/card: external reference plus transient display snapshot.
- previous messages and last card list: transient dialog context.
- timestamps/TTL: lifecycle metadata.

`last_card_list` JSONB contract:

```json
{
  "version": 1,
  "source": "cards.list | cards.list_by_column | resolver.candidates",
  "generated_at": "UTC timestamp",
  "items": [
    {
      "ordinal": 1,
      "kaiten_card_id": "external text id",
      "display_code": "008-08",
      "title": "short title snapshot",
      "column_name": "optional snapshot",
      "due_date": "YYYY-MM-DD or null"
    }
  ]
}
```

This is a temporary response snapshot for commands like "the second one". It is not a local Kaiten card cache and should be overwritten by the next list/candidate response.

### `pending_commands`

Responsibility: preserve unresolved or multi-step command execution state.

MVP recommendation: at most one active pending command per active dialog session.

| Field | PostgreSQL type | NULL | Default | Constraint | Purpose |
|---|---|---:|---|---|---|
| `id` | `UUID` | No | application `uuid4` | PK | Internal command ID |
| `user_id` | `UUID` | No |  | FK to `users.id` | Command owner |
| `dialog_session_id` | `UUID` | No |  | FK to `dialog_sessions.id` | Conversation context |
| `intent` | `TEXT` | No |  |  | Internal command intent, e.g. `comment.add` |
| `original_message` | `TEXT` | No |  |  | Original user command |
| `arguments` | `JSONB` | No | `'{}'` | app JSON contract | Parsed command arguments |
| `unresolved_entity` | `JSONB` | Yes |  | app JSON contract | Current unresolved entity |
| `candidates` | `JSONB` | Yes |  | app JSON contract | Current candidate list |
| `state` | `TEXT` | No | `'RECEIVED'` | CHECK `ck_pending_commands_state` | Lifecycle state |
| `failure_reason` | `TEXT` | Yes |  |  | Safe failure/cancel reason |
| `clarification_attempts` | `INTEGER` | No | `0` | CHECK non-negative | Bound clarification loops |
| `expires_at` | `TIMESTAMPTZ` | Yes |  |  | Pending command TTL |
| `executed_at` | `TIMESTAMPTZ` | Yes |  |  | Execution timestamp |
| `created_at` | `TIMESTAMPTZ` | No | UTC now |  | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | No | UTC now |  | Last state change |

PK: `pending_commands.id`.

FK:

```text
pending_commands.user_id -> users.id ON DELETE RESTRICT
pending_commands.dialog_session_id -> dialog_sessions.id ON DELETE CASCADE
```

UNIQUE / partial unique:

```text
uq_pending_commands_one_active_per_session:
  dialog_session_id
  WHERE state IN ('RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY')
```

CHECK:

```text
ck_pending_commands_state:
  state IN ('RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY', 'EXECUTED', 'FAILED', 'CANCELLED', 'EXPIRED')

ck_pending_commands_clarification_attempts_non_negative:
  clarification_attempts >= 0
```

Indexes:

- partial unique active command index above.
- `ix_pending_commands_user_state` on `(user_id, state)` for user-level recovery/debug.
- `ix_pending_commands_expires_at_active` partial on `expires_at` for active states, if cleanup is implemented in the same branch.

Delete policy:

- Pending command rows may be deleted when their dialog session is deleted.
- Executed/failed/cancelled/expired commands are no longer active and can be cleaned by TTL.

Data classes:

- original message: transient command context with short retention.
- intent/state/timestamps: persistent workflow state.
- JSON payloads: transient resolver/interpreter payloads.

JSONB contracts:

`arguments`:

```json
{
  "version": 1,
  "payload": {
    "card_id": "optional external text id",
    "comment": "optional text",
    "due_date": "optional YYYY-MM-DD"
  }
}
```

`unresolved_entity`:

```json
{
  "version": 1,
  "type": "card | board | column",
  "query": "original user phrase",
  "required_for": "argument name"
}
```

`candidates`:

```json
{
  "version": 1,
  "items": [
    {
      "ordinal": 1,
      "entity_type": "card",
      "external_id": "Kaiten external id",
      "display": "008-03 API audit",
      "metadata": {
        "column_name": "optional snapshot"
      }
    }
  ]
}
```

No GIN index is recommended initially because MVP query patterns address pending commands by user/session/state, not by nested JSON fields.

### `notification_settings`

Responsibility: per-user notification preference for due-date polling.

| Field | PostgreSQL type | NULL | Default | Constraint | Purpose |
|---|---|---:|---|---|---|
| `user_id` | `UUID` | No |  | PK, FK to `users.id` | Owner user |
| `enabled` | `BOOLEAN` | No | `false` |  | `/notify on/off` state |
| `due_soon_days` | `INTEGER` | No | `1` | CHECK range | Days before due date for DUE_SOON |
| `timezone` | `TEXT` | No | `'UTC'` |  | User date interpretation timezone |
| `created_at` | `TIMESTAMPTZ` | No | UTC now |  | Settings creation |
| `updated_at` | `TIMESTAMPTZ` | No | UTC now |  | Last settings update |

PK: `notification_settings.user_id`.

FK:

```text
notification_settings.user_id -> users.id ON DELETE RESTRICT
```

CHECK:

```text
ck_notification_settings_due_soon_days_range:
  due_soon_days BETWEEN 0 AND 30
```

Indexes:

- `ix_notification_settings_enabled` on `(enabled)` only if the worker scans enabled settings directly. For small MVP data it can be skipped; for worker query clarity, include `(enabled, user_id)`.

Delete policy:

- `RESTRICT` with user physical deletion deferred.

Data classes:

- enabled/threshold/timezone: persistent user configuration.

Timezone note:

- Store an explicit IANA timezone string. Default can be `UTC` or a product default chosen by the user.
- Do not infer notification date semantics from the server timezone.

### `notification_history`

Responsibility: notification deduplication and minimal delivery audit for polling worker.

| Field | PostgreSQL type | NULL | Default | Constraint | Purpose |
|---|---|---:|---|---|---|
| `id` | `UUID` | No | application `uuid4` | PK | Internal event ID |
| `user_id` | `UUID` | No |  | FK to `users.id` | Notification recipient |
| `kaiten_card_id` | `TEXT` | No |  |  | Kaiten card external ID |
| `due_date` | `DATE` | No |  |  | Kaiten due-date marker |
| `notification_type` | `TEXT` | No |  | CHECK `ck_notification_history_type` | `DUE_SOON`, `DUE_TODAY`, `OVERDUE` |
| `delivery_status` | `TEXT` | No | `'RESERVED'` | CHECK `ck_notification_history_delivery_status` | Minimal concurrency/delivery state |
| `sent_at` | `TIMESTAMPTZ` | Yes |  |  | Successful MAX send timestamp |
| `failed_at` | `TIMESTAMPTZ` | Yes |  |  | Failed MAX send timestamp |
| `error_type` | `TEXT` | Yes |  |  | Safe error class/code, no secrets |
| `created_at` | `TIMESTAMPTZ` | No | UTC now |  | Reservation/audit creation |
| `updated_at` | `TIMESTAMPTZ` | No | UTC now |  | Last delivery status update |

PK: `notification_history.id`.

FK:

```text
notification_history.user_id -> users.id ON DELETE RESTRICT
```

UNIQUE:

```text
uq_notification_history_dedup:
  (user_id, kaiten_card_id, due_date, notification_type)
```

CHECK:

```text
ck_notification_history_type:
  notification_type IN ('DUE_SOON', 'DUE_TODAY', 'OVERDUE')

ck_notification_history_delivery_status:
  delivery_status IN ('RESERVED', 'SENT', 'FAILED')
```

Indexes:

- unique dedup index above handles duplicate prevention.
- `ix_notification_history_user_card` on `(user_id, kaiten_card_id)` only if audit display/debug by card is needed; skip in first migration unless a query requires it.

Delete policy:

- `RESTRICT` on user delete to avoid losing dedup/audit state without an explicit account deletion decision.
- Old history may be pruned by retention policy later; no soft delete required.

Delivery risk:

- If KVC records "sent" before MAX delivery, a failed send can be incorrectly deduped.
- Minimal safer MVP workflow: reserve row with `RESERVED`, send MAX, then update to `SENT` or `FAILED`. A later retry policy can retry `FAILED` rows explicitly. This is not a full outbox, but it gives a concrete concurrency guard.

## Relationships

| Parent | Child | Cardinality | FK | ON DELETE | Rationale |
|---|---|---|---|---|---|
| `users` | `max_chats` | 1 -> 1 for MVP, 1 -> many later | `max_chats.user_id` | `RESTRICT` | User binding should not vanish accidentally |
| `users` | `kaiten_connections` | 1 -> 1 for MVP | `kaiten_connections.user_id` | `RESTRICT` | Token-bearing configuration needs explicit lifecycle |
| `users` | `dialog_sessions` | 1 -> many historical, 1 active | `dialog_sessions.user_id` | `RESTRICT` | Preserve context until cleanup/account decision |
| `max_chats` | `dialog_sessions` | 1 -> many historical | `dialog_sessions.max_chat_id` | `SET NULL` | Chat rebinding should not destroy session history |
| `dialog_sessions` | `pending_commands` | 1 -> many historical, 1 active | `pending_commands.dialog_session_id` | `CASCADE` | Pending commands are session-scoped transient state |
| `users` | `pending_commands` | 1 -> many | `pending_commands.user_id` | `RESTRICT` | User ownership supports direct queries and isolation |
| `users` | `notification_settings` | 1 -> 1 | `notification_settings.user_id` | `RESTRICT` | User preference lifecycle follows account lifecycle |
| `users` | `notification_history` | 1 -> many | `notification_history.user_id` | `RESTRICT` | Dedup/audit state must not be casually deleted |

## PendingCommand design

The specification states the core lifecycle:

| From | To | Condition | Terminal |
|---|---|---|---:|
| `RECEIVED` | `PARSED` | Parser/LLM produced intent and initial arguments | No |
| `PARSED` | `RESOLVING` | Resolver starts resolving external references | No |
| `RESOLVING` | `NEEDS_CLARIFICATION` | Resolver found no match or ambiguous candidates | No |
| `NEEDS_CLARIFICATION` | `RESOLVING` | User answered a clarification question | No |
| `RESOLVING` | `READY` | All required entities/arguments resolved | No |
| `READY` | `EXECUTED` | Command handler completed the explicit user operation | Yes |

Additional proposed technical states:

| From | To | Condition | Terminal |
|---|---|---|---:|
| Any active state | `CANCELLED` | User sends cancel command or starts incompatible new command | Yes |
| Any active state | `EXPIRED` | `expires_at` passes before resolution/execution | Yes |
| `READY` or active processing state | `FAILED` | Kaiten/MAX/application failure prevents completion | Yes |

These additional states are not already accepted product requirements. They are recommended because without them a command that fails, expires, or is cancelled remains indistinguishable from an active command and can violate the "one active pending command" invariant.

One active pending command per dialog session should be enforced by both application logic and a PostgreSQL partial unique index:

```text
UNIQUE (dialog_session_id)
WHERE state IN ('RECEIVED', 'PARSED', 'RESOLVING', 'NEEDS_CLARIFICATION', 'READY')
```

JSONB is preferred for `arguments`, `unresolved_entity`, and `candidates` in MVP because these payloads are transient interpreter/resolver state and will differ by command intent. Normalizing them now would create tables for unstable AI payload without useful query patterns. The stable columns remain normalized: user, session, intent, state, timestamps, TTL.

Transaction boundary:

- create pending command and update dialog context in one transaction;
- state transition and candidate/context update in one transaction;
- final execution status update after the external Kaiten operation result is known.

Concurrency:

- Use the partial unique index to reject two active pending commands for one session.
- Use row-level lock on the active `dialog_sessions` row or active `pending_commands` row while processing a user message.
- Duplicate clarification replies should re-read the command state in the same transaction before applying a transition.

## Dialog context design

The dialog context must survive server restart, but must not become a conversation transcript. The recommended design stores one active session per user and overwrites transient fields as interaction advances.

Context retention:

- `current_board_id` survives until user selects another board or the session expires.
- `current_card_id` survives until another card is opened/resolved or the session expires.
- `previous_user_message` and `previous_bot_message` are short-lived and may be overwritten on every bot exchange.
- `last_card_list` is overwritten on every list/candidate response.
- `expires_at` defines when context is stale.

`last_card_list` should be JSONB, not a separate table, because:

- it is temporary response context;
- it is bounded by page size/candidate limit;
- it is never a durable local card catalog;
- query patterns do not search inside it.

No JSONB GIN index is needed for dialog context in the first migration.

Transaction boundary:

- incoming message handling should lock the active session, read active pending command if present, update context, and commit together.

## Notification data design

`notification_settings` stores the user's notification preference:

- enabled/disabled;
- due-soon threshold in whole days;
- explicit timezone.

Timezone is needed in MVP because Kaiten due dates may be calendar dates without time, and production server timezone must not determine "today" for a user.

`notification_history` stores deduplication events:

```text
user_id
kaiten_card_id
due_date
notification_type
```

The unique constraint must include `due_date`. This ensures a notification sent for an old due date does not block notifications after the card due date changes.

Recommended event semantics:

- `DUE_SOON`: due date is within `due_soon_days`, but not today.
- `DUE_TODAY`: due date equals user's local date.
- `OVERDUE`: due date is before user's local date.

Minimal worker transaction:

1. Read enabled settings and Kaiten connection.
2. Read due cards from Kaiten.
3. For each event, attempt insert into `notification_history` with `RESERVED`.
4. If insert conflicts, skip duplicate.
5. Send MAX notification.
6. Update row to `SENT` with `sent_at`, or `FAILED` with safe `error_type`.

This avoids duplicate polling sends without introducing a full message queue/outbox.

## Secret storage contract

Secrets that must not be stored in KVC DB:

- PostgreSQL password.
- MAX bot token.
- MAX webhook secret.
- GigaChat credentials.
- SaluteSpeech credentials.
- token encryption key.
- `.env` contents.

Secret that must be stored in KVC DB:

- user Kaiten API token, only encrypted at rest.

Kaiten token contract:

- plaintext token is accepted only at the application/integration boundary long enough to encrypt or call Kaiten;
- plaintext token is never persisted;
- `encrypted_api_token` stores ciphertext;
- encryption key comes from environment or external secret storage;
- encryption key is never stored in PostgreSQL;
- `token_encryption_version` identifies the key/algorithm version needed for future rotation;
- logs, repr, reports, migrations, and test fixtures must not include real tokens.

The first migration should create storage columns only. It should not implement encryption.

## Timestamp/timezone contract

Use `TIMESTAMPTZ` for all instants:

```text
created_at
updated_at
last_verified_at
expires_at
ended_at
executed_at
sent_at
failed_at
```

Store instants in UTC. Application code should use timezone-aware datetimes.

Use `DATE` for Kaiten due dates when Kaiten represents deadlines as calendar dates without explicit time. Notification classification should interpret this date in the user's configured timezone.

Table timestamp needs:

| Table | Required timestamps | Rationale |
|---|---|---|
| `users` | `created_at`, `updated_at` | Account lifecycle |
| `max_chats` | `created_at`, `updated_at` | Binding lifecycle |
| `kaiten_connections` | `created_at`, `updated_at`, `last_verified_at` | Token/config lifecycle and verification |
| `dialog_sessions` | `created_at`, `updated_at`, `last_card_list_at`, `expires_at`, `ended_at` | Context freshness and cleanup |
| `pending_commands` | `created_at`, `updated_at`, `expires_at`, `executed_at` | Workflow lifecycle |
| `notification_settings` | `created_at`, `updated_at` | Preference lifecycle |
| `notification_history` | `created_at`, `updated_at`, `sent_at`, `failed_at` | Dedup reservation and delivery audit |

Do not add `deleted_at` in first migration; no soft-delete use case is accepted yet.

## Index/query matrix

| Scenario | Table | Lookup condition | Proposed index | Rationale |
|---|---|---|---|---|
| MAX incoming message routes to user | `max_chats` | `max_chat_id = ?` | `uq_max_chats_max_chat_id` | Fast webhook lookup and uniqueness |
| MAX private user binding | `max_chats` | `max_user_id = ? AND chat_type = 'PRIVATE'` | partial unique `uq_max_chats_max_user_id_private` | Prevent duplicate private identity |
| Send notification to primary chat | `max_chats` | `user_id = ? AND is_primary` | partial unique `uq_max_chats_user_primary` | One primary chat per user |
| User Kaiten access | `kaiten_connections` | `user_id = ?` | `uq_kaiten_connections_user_id` | One MVP connection per user |
| Active dialog session | `dialog_sessions` | `user_id = ? AND ended_at IS NULL` | partial unique `uq_dialog_sessions_one_active_per_user` | Fast context retrieval and invariant |
| Current active pending command | `pending_commands` | `dialog_session_id = ? AND state IN active states` | partial unique `uq_pending_commands_one_active_per_session` | Prevent ambiguous clarification state |
| User command recovery/debug | `pending_commands` | `user_id = ? AND state = ?` | `ix_pending_commands_user_state` | Operational lookup |
| Expire stale pending commands | `pending_commands` | `expires_at < now AND state IN active states` | partial `ix_pending_commands_expires_at_active` | Cleanup job, if implemented |
| Notification worker scans enabled users | `notification_settings` | `enabled = true` | `ix_notification_settings_enabled_user` | Worker polling input |
| Notification dedup | `notification_history` | `user_id/card/due/type` | `uq_notification_history_dedup` | Prevent duplicate sends across polling cycles |

Do not add JSONB GIN indexes in the first migration; no MVP query requires searching inside JSON payloads.

## Constraints and enum policy

Prefer `TEXT + CHECK` for MVP finite states:

- simpler Alembic changes than PostgreSQL ENUM alteration;
- values remain constrained by the database;
- application enums can mirror the database checks;
- no lookup/reference tables needed for small fixed sets.

Finite value inventory:

| Concept | Storage | Values | Reason |
|---|---|---|---|
| User status | `TEXT + CHECK` | `ACTIVE`, `DISABLED` | More expressive than boolean, easy extension |
| MAX chat type | `TEXT + CHECK` | `PRIVATE` initially | Do not imply group support |
| Kaiten connection status | `TEXT + CHECK` | `ACTIVE`, `DISABLED`, `NEEDS_REAUTH` | Token can fail without deleting config |
| Pending command state | `TEXT + CHECK` | Spec states plus proposed terminal states | Workflow invariant |
| Notification type | `TEXT + CHECK` | `DUE_SOON`, `DUE_TODAY`, `OVERDUE` | Direct spec values |
| Notification delivery status | `TEXT + CHECK` | `RESERVED`, `SENT`, `FAILED` | Minimal concurrency/delivery tracking |

CHECK constraints should use explicit semantic names because current naming convention is:

```text
ck_%(table_name)s_%(constraint_name)s
```

Examples:

```text
ck_pending_commands_state
ck_notification_history_type
ck_notification_settings_due_soon_days_range
```

## Concurrency and transactions

Minimum concurrency invariants:

- Two webhook requests from one user must not create two active dialog sessions.
- Two messages from one user must not create two active pending commands in the same session.
- A clarification reply must not be applied to an already executed/cancelled/expired command.
- Two notification polling cycles must not send the same notification event twice.
- Incoming message handling and notification worker can operate for the same user without sharing mutable command state.

Recommended enforcement:

- partial unique indexes for one active session and one active pending command;
- transaction around message routing, session update, pending command transition;
- row-level lock on active session/pending command during message processing;
- unique insert/reservation for notification history before MAX send;
- idempotent handling of conflict on notification dedup insert.

No distributed lock infrastructure is required for MVP.

Transaction boundaries:

| Operation | Atomic KVC DB changes |
|---|---|
| Bind MAX user/chat | create/find `users`, insert/update `max_chats`, create default `notification_settings` if needed |
| Bind Kaiten token | encrypt token outside DB, insert/update `kaiten_connections`, update verification timestamp/status |
| Start/update dialog session | create or lock active `dialog_sessions`, update context fields |
| Create pending command | insert `pending_commands`, update dialog context in same transaction |
| Resolve clarification | lock pending command, update candidates/unresolved entity/state, update context |
| Execute command | after explicit user command and Kaiten result, update pending state/timestamps/context |
| Notification send | reserve dedup row, send MAX, update delivery status |

## First migration proposal

Purpose: introduce the first real KVC service data model without copying Kaiten content.

Tables:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

Constraints:

- all PKs;
- all FKs with explicit delete behavior;
- unique MAX chat/user bindings;
- unique one Kaiten connection per user;
- partial unique one active dialog session per user;
- partial unique one active pending command per session;
- notification dedup unique key;
- named CHECK constraints for finite states and numeric ranges.

Indexes:

- routing/dedup indexes listed in the query matrix;
- no JSONB GIN indexes initially.

Upgrade order:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
indexes / partial unique indexes / checks as part of table creation where possible
```

Downgrade order:

```text
drop notification_history
drop notification_settings
drop pending_commands
drop dialog_sessions
drop kaiten_connections
drop max_chats
drop users
```

Do not assign a revision ID in this audit. Do not create a migration until user decisions are confirmed.

## Decisions requiring user approval

### 1. Internal primary key type

Option A: `UUID` internal IDs.

Option B: `BIGINT GENERATED BY DEFAULT AS IDENTITY`.

Recommendation: Option A, application-generated UUIDs.

Consequence: UUID avoids sequential account enumeration and keeps future external API exposure safer. BIGINT is simpler to inspect manually but exposes ordering and cardinality if leaked.

### 2. MAX chat scope in MVP

Option A: Support only private one-to-one MAX chats in MVP.

Option B: Design group chat support now.

Recommendation: Option A.

Consequence: Option A keeps user identity and notification routing deterministic. Option B requires group permissions, user disambiguation inside chat, and more complex context partitioning.

### 3. Kaiten connections per user

Option A: One active Kaiten connection per user in MVP.

Option B: Multiple Kaiten connections/workspaces per user from first migration.

Recommendation: Option A.

Consequence: Option A matches MVP and simplifies command routing. Option B supports future commercial/workspace scenarios but requires connection selection UX and more constraints now.

### 4. Pending command terminal states

Option A: Add `FAILED`, `CANCELLED`, `EXPIRED` in the first schema.

Option B: Store only specification states for now.

Recommendation: Option A.

Consequence: Option A makes cleanup, cancellation, and external failure explicit. Option B is closer to the current spec text but leaves failed/stale commands ambiguous.

### 5. Notification delivery status

Option A: Include `RESERVED`, `SENT`, `FAILED` delivery status in `notification_history`.

Option B: Store only successful notifications with `sent_at`.

Recommendation: Option A.

Consequence: Option A reduces duplicate send races and records safe failures. Option B is simpler but can double-send under concurrent polling unless additional locking is introduced elsewhere.

### 6. User timezone default

Option A: Store `timezone` now with default `UTC`.

Option B: Store `timezone` now with product default `Europe/Kaliningrad`.

Recommendation: Option A unless the product is explicitly single-timezone.

Consequence: Option A is deployment-neutral. Option B may better match current local testing but bakes a regional assumption into all new users.

### 7. Physical user deletion

Option A: No physical user delete in MVP; use `users.status = DISABLED`.

Option B: Implement physical deletion semantics in first data model.

Recommendation: Option A.

Consequence: Option A avoids unresolved retention/security decisions. Option B needs a clear policy for encrypted tokens, dialog context, and notification history.

## Recommended branch plan

```text
002-00  Audit of MVP service data model
002-00a Final data model specification after user decisions
002-01  SQLAlchemy models and first Alembic migration
002-02  Migration/application persistence acceptance on live PostgreSQL
002-03  Minimal repository/query contracts for user bindings, dialog context, pending commands, and notifications
```

Do not start `002-01` until `002-00a` resolves the user-approval decisions above.

## Quality gate

Final audit quality gate:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
25 passed in 2.08s

.venv\Scripts\python.exe -m pytest -W error
25 passed in 2.06s

.venv\Scripts\python.exe -m ruff format --check .
42 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 21 source files

git diff --check
<no output, exit code 0>
```

## Changed files

Production code changes:

```text
none
```

Tests:

```text
none
```

Documentation:

```text
none
```

Report:

```text
codex/reports/002_00_mvp_service_data_model_audit_report.md
```

## Final status

READY WITH DECISIONS REQUIRED

The service-owned data, persistence boundaries, table relationships, transient context, secret protection, notification deduplication, and first migration content are defined as a candidate design. Implementation should wait for explicit user confirmation of the listed decisions.
