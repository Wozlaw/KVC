# 002-00b - Kaiten deadline semantics and notification dedup correction

## Executive summary

The official Kaiten REST API confirms that card deadlines are not just calendar dates. Card create/update accepts `due_date` as an ISO 8601 string or `null`, and uses `due_date_time_present` to mark whether the deadline is specified up to hours and minutes. Card retrieve/list responses expose the same semantic pair.

This corrects the affected part of `002-00a`: `notification_history.due_date DATE` is replaced by:

```text
due_at TIMESTAMPTZ NOT NULL
due_date_time_present BOOLEAN NOT NULL
```

The notification dedup key becomes:

```text
(
  user_id,
  kaiten_card_id,
  due_at,
  due_date_time_present,
  notification_type
)
```

This report is a corrective addendum. It does not change production code, tests, SQLAlchemy models, Alembic revisions, database schema, or business logic.

## Verified official Kaiten deadline contract

Official REST Card API findings:

- Create card accepts `due_date` as a string with description `Deadline. ISO 8601 format`, or `null` for an empty due date.
- Create card accepts `due_date_time_present` as a boolean flag indicating that the deadline is specified up to hours and minutes.
- Update card has the same `due_date` and `due_date_time_present` request fields.
- Retrieve card/list response schemas expose `due_date` as `null | string` and `due_date_time_present` as boolean.
- Official response examples include a timestamp value such as `2022-10-20T21:00:00.000Z` with `due_date_time_present: true`.
- Import API documents the related `CardDateObject` with `value: string` and `time_present: boolean | null`, where the boolean defines whether the value contains only date or also time.

Interpretation for KVC:

- `due_date` is an external Kaiten deadline value, not a local KVC card field.
- A deadline may carry a precise instant with hours/minutes.
- `due_date_time_present` is required to preserve the user-facing distinction between date-only and date-time deadlines.
- `due_date = null` means no deadline.
- Official examples use ISO 8601 UTC `Z`; KVC must parse any valid ISO 8601 offset form that Kaiten returns and normalize to UTC for storage.

The documentation does not explicitly describe every transformation Kaiten applies to date-only values in the REST API. Therefore KVC must preserve both the normalized instant and `due_date_time_present` rather than collapsing the marker to `DATE`.

## Official API references

- Create card: `https://developers.kaiten.ru/cards/create-new-card`
  - `due_date`: string, ISO 8601, or null.
  - `due_date_time_present`: boolean flag for hours/minutes precision.
- Update card: `https://developers.kaiten.ru/cards/update-card`
  - same mutable deadline fields.
- Retrieve card: `https://developers.kaiten.ru/cards/retrieve-card`
  - response exposes `due_date: null | string` and `due_date_time_present: boolean`.
- Retrieve card list: `https://developers.kaiten.ru/cards/retrieve-card-list`
  - list response exposes the same deadline fields.
- Imports card entity: `https://developers.kaiten.ru/imports/entities/cards`
  - `CardDateObject.value` plus `time_present` confirms date-only vs date-time distinction.

## Contradiction with `002-00a`

`002-00a` specified:

```text
notification_history.due_date DATE
uq_notification_history_dedup:
  UNIQUE (user_id, kaiten_card_id, due_date, notification_type)
```

It also used JSONB examples with `YYYY-MM-DD`.

This is insufficient because a Kaiten deadline can include time. If a card changes from:

```text
2026-08-20T12:00:00Z
```

to:

```text
2026-08-20T18:00:00Z
```

then `DATE` collapses both values to `2026-08-20` and can incorrectly suppress a notification for the changed deadline.

## Final deadline storage decision

Affected table: `notification_history`.

Replace:

| Field | PostgreSQL type | NULL | Meaning |
|---|---|---:|---|
| `due_date` | `DATE` | No | Kaiten due-date marker |

With:

| Field | PostgreSQL type | NULL | Default | Constraint | Meaning | Data class |
|---|---|---:|---|---|---|---|
| `due_at` | `TIMESTAMPTZ` | No | none | dedup UNIQUE | Normalized Kaiten deadline marker | audit/dedup state |
| `due_date_time_present` | `BOOLEAN` | No | none | dedup UNIQUE | Whether Kaiten says the deadline includes hours/minutes | audit/dedup state |

`due_at` is a dedup/audit marker copied from the current Kaiten deadline at notification time. It is not a local KVC card deadline and is not a source of truth.

Normalization contract:

- parse Kaiten `due_date` as ISO 8601;
- preserve the actual instant by storing it as `TIMESTAMPTZ`;
- normalize to UTC at application boundary;
- keep `due_date_time_present` alongside the instant;
- do not store notification history row when Kaiten `due_date` is `null`.

## Final notification dedup key

Final key:

```text
uq_notification_history_dedup:
  UNIQUE (
    user_id,
    kaiten_card_id,
    due_at,
    due_date_time_present,
    notification_type
  )
```

`due_date_time_present` remains in the key. It is not redundant for KVC because the official contract gives this flag independent semantic value: it says whether the deadline is date-only or precise to hours/minutes. Even if two normalized instants compare equal, a change in the flag is a meaningful Kaiten deadline semantic change and must not be hidden by deduplication.

No separate secondary `due_at` index is added. No duplicate index is created on the dedup tuple.

## `due_date_time_present` semantics

```text
false
```

The user/Kaiten deadline is date-only for display and local calendar classification. The normalized `due_at` exists only as a stable marker for deduplication and ordering.

```text
true
```

The user/Kaiten deadline includes hours/minutes. `due_at` is the exact instant used for deadline comparison and deduplication.

Changing only time on the same calendar date changes `due_at`, so it creates a new dedup identity.

Changing only `due_date_time_present` while the normalized instant remains the same also creates a new dedup identity because the user-facing deadline precision changed.

## DUE_SOON / DUE_TODAY / OVERDUE contract

All notification classification uses `notification_settings.timezone`, never server timezone.

### Deadline without time

When `due_date_time_present = false`:

- convert `due_at` to the user's local date in `notification_settings.timezone`;
- ignore time-of-day for classification;
- `DUE_TODAY`: local due date equals user's current local date;
- `OVERDUE`: local due date is before user's current local date;
- `DUE_SOON`: local due date is after today and within `due_soon_days`.

### Deadline with time

When `due_date_time_present = true`:

- compare the exact instant `due_at` to current UTC instant for overdue detection;
- use the user's timezone for local calendar display and for deciding whether the deadline falls on the user's local today;
- `OVERDUE`: `due_at <= now_utc` after the deadline instant has passed;
- `DUE_TODAY`: the local date of `due_at` equals user's current local date and the instant is not overdue yet;
- `DUE_SOON`: deadline instant is in the future and its local date is within `due_soon_days` after today, excluding today.

If product wording later wants "overdue only after the user's local day ends" for time-present deadlines, that is a product-policy change and must be decided separately.

## Updated JSONB deadline contracts

JSONB remains temporary, bounded, versioned context. It is not a Kaiten cache.

### `dialog_sessions.last_card_list`

Updated item deadline fields:

```json
{
  "version": 1,
  "source": "cards.list",
  "generated_at": "2026-08-14T00:00:00Z",
  "items": [
    {
      "ordinal": 1,
      "entity_type": "card",
      "external_id": "kaiten-card-id",
      "display_code": "008-08",
      "title": "short display snapshot",
      "column_name": "optional display snapshot",
      "due_date": "2026-08-20T21:00:00.000Z",
      "due_date_time_present": true
    }
  ]
}
```

Required per item:

```text
ordinal
entity_type
external_id
```

Optional per item:

```text
display_code
title
column_name
due_date
due_date_time_present
```

If `due_date` is present, `due_date_time_present` must also be present. If Kaiten has no deadline, use `due_date: null` and `due_date_time_present: false` or omit both fields consistently in the application mapper.

### `pending_commands.candidates`

Candidate metadata may include the same temporary deadline snapshot:

```json
{
  "version": 1,
  "items": [
    {
      "ordinal": 1,
      "entity_type": "card",
      "external_id": "kaiten-card-id",
      "display": "008-03 API audit",
      "metadata": {
        "column_name": "В работе",
        "due_date": "2026-08-20T21:00:00.000Z",
        "due_date_time_present": true
      }
    }
  ]
}
```

These values are display/resolution snapshots only.

## Updated `pending_commands.arguments`

Do not constrain deadline command arguments to `YYYY-MM-DD`.

Recommended versioned contract for due-date commands:

### Set or change deadline

```json
{
  "version": 1,
  "payload": {
    "operation": "set_due_date",
    "card_id": "kaiten-card-id",
    "due_date": "2026-08-20T21:00:00.000Z",
    "due_date_time_present": true,
    "source_text": "поставь срок на 20 августа в 21:00"
  }
}
```

Date-only deadline:

```json
{
  "version": 1,
  "payload": {
    "operation": "set_due_date",
    "card_id": "kaiten-card-id",
    "due_date": "2026-08-20",
    "due_date_time_present": false,
    "source_text": "поставь срок на 20 августа"
  }
}
```

### Clear deadline

```json
{
  "version": 1,
  "payload": {
    "operation": "clear_due_date",
    "card_id": "kaiten-card-id",
    "due_date": null,
    "due_date_time_present": false,
    "source_text": "убери срок"
  }
}
```

Rules:

- `operation = set_due_date` covers both setting and changing a deadline.
- `operation = clear_due_date` maps to Kaiten `due_date = null`.
- `due_date_time_present = true` requires an ISO 8601 date-time value.
- `due_date_time_present = false` represents date-only user intent.
- the final Kaiten adapter must serialize to Kaiten's REST fields `due_date` and `due_date_time_present`.

## Timestamp/timezone correction

KVC lifecycle instants remain unchanged and use `TIMESTAMPTZ`:

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
```

Kaiten deadline marker in KVC notification history:

```text
notification_history.due_at TIMESTAMPTZ NOT NULL
notification_history.due_date_time_present BOOLEAN NOT NULL
```

Remove the `002-00a` statement that Kaiten deadline should be stored as PostgreSQL `DATE` in the first migration.

After this correction, PostgreSQL `DATE` is no longer required by the first migration type inventory.

User timezone:

- `notification_settings.timezone` remains `TEXT NOT NULL DEFAULT 'UTC'`;
- it must be an IANA timezone string;
- it is used for local calendar interpretation/display;
- server timezone must not affect notification classification.

## `RESERVED/SENT/FAILED` recovery semantics

The schema still uses:

```text
RESERVED
SENT
FAILED
```

Problem acknowledged:

- a `FAILED` row occupies the dedup key;
- a stale `RESERVED` row after process crash also occupies the dedup key;
- without recovery, future polling could skip the event forever.

Minimal recovery semantics without outbox:

```text
RESERVED -> SENT
RESERVED -> FAILED
FAILED -> RESERVED -> SENT/FAILED
stale RESERVED -> RESERVED reclaim -> SENT/FAILED
```

Concurrency guard:

- retry/reclaim must run in one transaction;
- select the existing dedup row with row-level lock;
- verify `delivery_status IN ('FAILED', 'RESERVED')`;
- for stale `RESERVED`, require `updated_at` older than a configured reclaim threshold;
- update `delivery_status` to `RESERVED` and `updated_at = now()`;
- perform MAX send;
- update to `SENT` or `FAILED`.

No extra migration field is required now:

- `updated_at` is already present and can act as reservation freshness marker;
- `failed_at` and `error_type` are already present for safe failure audit;
- `attempt_count`, `last_attempt_at`, and `reserved_at` are not added until retry policy needs reporting or hard retry limits.

## Updated affected index/query matrix

| Query scenario | Table | Lookup/filter | Index/constraint | Unique | Partial | Reason |
|---|---|---|---|---:|---:|---|
| Notification dedup/reservation | `notification_history` | `user_id, kaiten_card_id, due_at, due_date_time_present, notification_type` | `uq_notification_history_dedup` | Yes | No | Prevent duplicate notification identity while preserving time precision |
| Failed/stale reservation recovery | `notification_history` | same dedup key, then row lock | `uq_notification_history_dedup` | Yes | No | Recovery starts from the exact event identity |

No standalone `due_at` index is added. No duplicate secondary index is added over the dedup tuple.

## Updated affected first-migration contract

Only the affected `notification_history` contract changes.

Fields:

```text
remove due_date DATE
add due_at TIMESTAMPTZ NOT NULL
add due_date_time_present BOOLEAN NOT NULL
```

Unique key:

```text
uq_notification_history_dedup:
  UNIQUE (
    user_id,
    kaiten_card_id,
    due_at,
    due_date_time_present,
    notification_type
  )
```

PostgreSQL type inventory after correction:

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

`DATE` is removed from the first migration type inventory.

Unchanged notification history fields:

```text
id UUID PK
user_id UUID NOT NULL FK -> users.id ON DELETE RESTRICT
kaiten_card_id TEXT NOT NULL
notification_type TEXT NOT NULL
delivery_status TEXT NOT NULL DEFAULT 'RESERVED'
sent_at TIMESTAMPTZ NULL
failed_at TIMESTAMPTZ NULL
error_type TEXT NULL
created_at TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

Unchanged checks:

```text
ck_notification_history_type:
  notification_type IN ('DUE_SOON', 'DUE_TODAY', 'OVERDUE')

ck_notification_history_delivery_status:
  delivery_status IN ('RESERVED', 'SENT', 'FAILED')
```

First business migration remains one coherent initial migration. It must be created with the corrected deadline contract and must not require an immediate follow-up migration.

## Unchanged `002-00a` decisions

Unchanged:

- Kaiten remains the only source of truth.
- KVC does not store persistent Kaiten content/cache.
- Seven-table MVP model remains unchanged.
- Application-generated UUID PKs.
- MAX private 1:1 only.
- One Kaiten connection per user.
- `max_chat_binding_id` remains the internal FK to `max_chats`.
- `TEXT + CHECK`, no PostgreSQL ENUM.
- PendingCommand includes `FAILED`, `CANCELLED`, `EXPIRED`.
- `notification_settings.timezone = 'UTC'` default.
- No physical user deletion.
- No JSONB GIN indexes.
- No full outbox.
- No new business tables.
- No production implementation in this stage.

## Consistency review

| Check | Result |
|---|---|
| Deadline time is not lost | PASS: `due_at TIMESTAMPTZ` preserves time/offset-normalized instant |
| Deadline without time remains interpretable | PASS: `due_date_time_present = false` preserves date-only semantics |
| Meaningful time-only change affects dedup identity | PASS: changed instant changes `due_at` |
| User timezone is not replaced by server timezone | PASS: classification uses `notification_settings.timezone` |
| JSONB remains temporary context snapshot | PASS |
| Command arguments distinguish set/change/clear deadline | PASS |
| `FAILED` and stale `RESERVED` can be recovered without duplicate send | PASS: row lock plus dedup row status recovery |
| No duplicate indexes | PASS |
| Initial business migration remains one coherent migration | PASS |
| Unaffected `002-00a` decisions are preserved | PASS |

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
codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
```

Other:

```text
none
```

## Quality gate

Final quality gate:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
25 passed in 2.40s

.venv\Scripts\python.exe -m pytest -W error
25 passed in 2.06s

.venv\Scripts\python.exe -m ruff format --check .
46 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 21 source files

git diff --check
<no output, exit code 0>

git status --short
?? codex/prompts/002_00_mvp_service_data_model_audit_prompt.md
?? codex/prompts/002_00a_mvp_service_data_model_final_specification_prompt.md
?? codex/prompts/002_00b_kaiten_deadline_notification_semantics_correction_prompt.md
?? codex/reports/002_00_mvp_service_data_model_audit_report.md
?? codex/reports/002_00a_mvp_service_data_model_final_specification.md
?? codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md

git diff --stat
<no output, exit code 0; working-tree changes are untracked>
```

## Final status

ACCEPTED CORRECTION - READY FOR 002-01
