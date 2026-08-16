# 002-00c - Live Kaiten deadline representation acceptance probe

## Executive summary

Live Kaiten deadline round-trip probing completed successfully on the configured test card.

Result: Contract A from `002-00b` is accepted for the initial business migration:

```text
notification_history.due_at TIMESTAMPTZ NOT NULL
notification_history.due_date_time_present BOOLEAN NOT NULL
```

Important implementation rule:

```text
When due_date_time_present = false, recover the selected calendar date
from the UTC date component of due_at. Do not convert date-only due_at
through notification_settings.timezone.
```

This rule is safe because live Kaiten returned date-only `2026-09-20` as exactly:

```text
2026-09-20T00:00:00.000Z
due_date_time_present = false
```

Date-time deadlines are distinct instants. Kaiten also showed its own normalization for date-time values: requests for `12:00:00.000Z` and `18:00:00.000Z` returned `12:00:59.999Z` and `18:00:59.999Z`. KVC must use the persisted/read-back Kaiten value for notification dedup, not the pre-update request value.

Final status: `ACCEPTED LIVE CONTRACT - READY FOR 002-01`.

## Test environment summary

Working directory:

```text
D:\Prog\KVControl
```

Current branch/commit:

```text
0501ca3 (HEAD -> main) feat: add PostgreSQL persistence foundation
4e4d728 chore: bootstrap Kaiten Voice Control project
```

Safe `.env` key inventory:

```text
KVC_APP_ENV
KVC_LOG_LEVEL
KVC_DATABASE_URL
KVC_DATABASE_ECHO
KVC_KAITEN_API_TOKEN
KVC_KAITEN_API_BASE_URL
KVC_KAITEN_TEST_CARD_ID
```

Safe live diagnostics:

```json
{
  "base_kind": "api/latest",
  "initial_get_status": 200,
  "token_present": true,
  "test_card_id_present": true
}
```

No `.env` values were printed. No token, cookie, Authorization header, full API URL, or secret-bearing value was written to this report.

## Test card safety statement

The probe used the configured test card:

```text
card id: 68729805
title: <sanitized>
```

Initial state was read before mutation:

```json
{
  "card_id": "68729805",
  "title": "<sanitized>",
  "due_date": null,
  "due_date_time_present": false
}
```

The card deadline was restored after the probe:

```json
{
  "request": {
    "due_date": null,
    "due_date_time_present": false
  },
  "update_status": 200,
  "get_status": 200,
  "get_response": {
    "due_date": null,
    "due_date_time_present": false
  }
}
```

## Official Kaiten contract references

Official pages checked:

- `https://developers.kaiten.ru/`
- `https://developers.kaiten.ru/cards/create-new-card`
- `https://developers.kaiten.ru/cards/update-card`
- `https://developers.kaiten.ru/cards/retrieve-card`
- `https://developers.kaiten.ru/cards/retrieve-card-list`
- `https://developers.kaiten.ru/imports/entities/cards`

Relevant official contract:

- REST base URL is `https://<your_domain>.kaiten.ru/api/v1`; latest API is also available at `/api/latest`.
- Requests use Bearer authorization.
- Retrieve card endpoint: `GET /api/latest/cards/{card_id}`.
- Update card endpoint: `PATCH /api/latest/cards/{card_id}`.
- Create/update card accept `due_date` as ISO 8601 string or `null`.
- Create/update card accept `due_date_time_present` as a boolean flag indicating hours/minutes precision.
- Retrieve card and retrieve card list expose `due_date: null | string` and `due_date_time_present: boolean`.
- Import `CardDateObject` defines `value: string` and `time_present: boolean | null`, preserving date-only vs date-time distinction.

## Probe A - date-only evidence

Request intent:

```text
deadline = calendar date only
due_date_time_present = false
```

Evidence:

```json
{
  "probe": "date_only",
  "request": {
    "due_date": "2026-09-20",
    "due_date_time_present": false
  },
  "update_status": 200,
  "update_response": {
    "due_date": "2026-09-20T00:00:00.000Z",
    "due_date_time_present": false
  },
  "get_status": 200,
  "get_response": {
    "due_date": "2026-09-20T00:00:00.000Z",
    "due_date_time_present": false
  }
}
```

Observed date-only wire representation:

```text
Kaiten returns date-only 2026-09-20 as 2026-09-20T00:00:00.000Z
with due_date_time_present = false.
```

## Probe B - same date with exact time

Request intent:

```text
deadline = same calendar date, exact time 12:00 UTC
due_date_time_present = true
```

Evidence:

```json
{
  "probe": "date_time_12",
  "request": {
    "due_date": "2026-09-20T12:00:00.000Z",
    "due_date_time_present": true
  },
  "update_status": 200,
  "update_response": {
    "due_date": "2026-09-20T12:00:59.999Z",
    "due_date_time_present": true
  },
  "get_status": 200,
  "get_response": {
    "due_date": "2026-09-20T12:00:59.999Z",
    "due_date_time_present": true
  }
}
```

Observed behavior:

- `due_date_time_present = true` is preserved.
- Kaiten normalized `12:00:00.000Z` to `12:00:59.999Z`.
- KVC must store the read-back value for notification dedup.

## Probe C - time-only change evidence

Request intent:

```text
same calendar date
change time from 12:00 to 18:00 UTC
due_date_time_present = true
```

Evidence:

```json
{
  "probe": "date_time_18",
  "before": {
    "due_date": "2026-09-20T12:00:59.999Z",
    "due_date_time_present": true
  },
  "request": {
    "due_date": "2026-09-20T18:00:00.000Z",
    "due_date_time_present": true
  },
  "update_status": 200,
  "update_response": {
    "due_date": "2026-09-20T18:00:59.999Z",
    "due_date_time_present": true
  },
  "get_status": 200,
  "get_response": {
    "due_date": "2026-09-20T18:00:59.999Z",
    "due_date_time_present": true
  }
}
```

Conclusion:

```text
Changing only time is visible in REST representation and must change
notification dedup identity.
```

## Probe D - clear deadline evidence

Request intent:

```text
remove deadline
due_date = null
```

Evidence:

```json
{
  "probe": "clear_deadline",
  "request": {
    "due_date": null,
    "due_date_time_present": false
  },
  "update_status": 200,
  "update_response": {
    "due_date": null,
    "due_date_time_present": false
  },
  "get_status": 200,
  "get_response": {
    "due_date": null,
    "due_date_time_present": false
  }
}
```

Observed clear-deadline representation:

```text
due_date = null
due_date_time_present = false
```

No `notification_history` row is created for cards without a deadline.

## Optional list-endpoint evidence

Retrieve card list was checked for date-only and date-time states using the same test card.

Date-only list evidence:

```json
{
  "probe": "list_date_only",
  "request": {
    "due_date": "2026-09-20",
    "due_date_time_present": false
  },
  "update_status": 200,
  "get_status": 200,
  "get_response": {
    "due_date": "2026-09-20T00:00:00.000Z",
    "due_date_time_present": false
  },
  "list_status": 200,
  "list_response": {
    "due_date": "2026-09-20T00:00:00.000Z",
    "due_date_time_present": false
  }
}
```

Date-time list evidence:

```json
{
  "probe": "list_date_time",
  "request": {
    "due_date": "2026-09-20T18:00:00.000Z",
    "due_date_time_present": true
  },
  "update_status": 200,
  "get_status": 200,
  "get_response": {
    "due_date": "2026-09-20T18:00:59.999Z",
    "due_date_time_present": true
  },
  "list_status": 200,
  "list_response": {
    "due_date": "2026-09-20T18:00:59.999Z",
    "due_date_time_present": true
  }
}
```

Retrieve card and retrieve card list returned matching deadline semantics for the tested states.

## Observed normalization/timezone behavior

Observed facts:

- Date-only request `2026-09-20` returns `2026-09-20T00:00:00.000Z`.
- Date-only response keeps `due_date_time_present = false`.
- Date-time requests preserve `due_date_time_present = true`.
- Date-time requests at `HH:MM:00.000Z` returned as `HH:MM:59.999Z`.
- Changing only time from 12:00 to 18:00 changes the returned `due_date`.
- Clearing deadline returns `due_date = null` and `due_date_time_present = false`.

Date-only restoration rule:

```text
If due_date_time_present = false:
  selected_due_date = UTC calendar date component of due_at.
```

Do not derive the date-only selected date by converting `due_at` through `notification_settings.timezone`. That conversion could turn midnight UTC into the previous local date for negative offsets. User timezone is used to determine the user's current local date for classification, not to reinterpret the stored date-only marker.

## Final choice: Contract A

Final choice:

```text
Contract A - unified deadline marker
```

Storage:

```text
due_at TIMESTAMPTZ NOT NULL
due_date_time_present BOOLEAN NOT NULL
```

This is accepted because the live date-only representation is a stable midnight UTC marker paired with `due_date_time_present = false`, and the original calendar date is recovered from the UTC date component.

## Exact rationale

Contract A is physically sufficient when paired with these interpretation rules:

- for date-time deadlines, `due_at` is the exact deadline instant;
- for date-only deadlines, `due_at` is the Kaiten UTC midnight marker for the selected calendar date;
- `due_date_time_present` chooses the interpretation mode;
- date-only classification never timezone-converts `due_at` to find the due date;
- notification dedup uses the read-back Kaiten value, so Kaiten normalization is preserved.

This prevents the selected date `2026-09-20` from becoming `2026-09-19` or `2026-09-21` when `notification_settings.timezone` changes, because timezone conversion is not part of date-only due-date extraction.

## Final `notification_history` field contract

Affected table: `notification_history`.

| Field | PostgreSQL type | NULL | Default | Constraint | Meaning | Data class |
|---|---|---:|---|---|---|---|
| `due_at` | `TIMESTAMPTZ` | No | none | dedup UNIQUE | Kaiten deadline marker parsed from read-back `due_date` | audit/dedup state |
| `due_date_time_present` | `BOOLEAN` | No | none | dedup UNIQUE | Kaiten precision flag | audit/dedup state |

No `due_date DATE` column is required in the first migration.

## Final CHECK constraints

No additional deadline-specific CHECK is required for Contract A beyond:

```text
due_at IS NOT NULL
due_date_time_present IS NOT NULL
```

Existing notification checks remain:

```text
ck_notification_history_type:
  notification_type IN ('DUE_SOON', 'DUE_TODAY', 'OVERDUE')

ck_notification_history_delivery_status:
  delivery_status IN ('RESERVED', 'SENT', 'FAILED')
```

Application/repository validation must ensure no notification history row is created when Kaiten `due_date` is `null`.

## Final dedup UNIQUE design

Final dedup key:

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

Rationale:

- time-only changes alter `due_at`;
- precision-mode changes alter `due_date_time_present`;
- `notification_type` distinguishes `DUE_SOON`, `DUE_TODAY`, and `OVERDUE`;
- no nullable deadline column participates in the unique key;
- the index is physically enforceable by PostgreSQL.

No duplicate secondary index is created over this unique key.

## Final classification semantics

Date-only deadline:

```text
due_date_time_present = false
due_date_for_classification = due_at converted to UTC, then .date()
today_for_user = current date in notification_settings.timezone
```

- `DUE_TODAY`: `due_date_for_classification == today_for_user`.
- `OVERDUE`: `due_date_for_classification < today_for_user`.
- `DUE_SOON`: `today_for_user < due_date_for_classification <= today_for_user + due_soon_days`.

Date-time deadline:

```text
due_date_time_present = true
deadline instant = due_at
today_for_user = current date in notification_settings.timezone
deadline_local_date = due_at converted to notification_settings.timezone, then .date()
```

- `OVERDUE`: `due_at <= now_utc`.
- `DUE_TODAY`: `deadline_local_date == today_for_user` and `due_at > now_utc`.
- `DUE_SOON`: `today_for_user < deadline_local_date <= today_for_user + due_soon_days` and `due_at > now_utc`.

Server timezone is never used.

## Updated JSONB deadline contract

JSONB remains temporary context/resolver state. It must preserve the external semantic pair and distinguish:

```text
date-only
date-time
no deadline
```

### `dialog_sessions.last_card_list`

Date-only item:

```json
{
  "ordinal": 1,
  "entity_type": "card",
  "external_id": "kaiten-card-id",
  "display_code": "008-08",
  "title": "short display snapshot",
  "column_name": "optional display snapshot",
  "due_date": "2026-09-20T00:00:00.000Z",
  "due_date_time_present": false
}
```

Date-time item:

```json
{
  "ordinal": 1,
  "entity_type": "card",
  "external_id": "kaiten-card-id",
  "display_code": "008-08",
  "title": "short display snapshot",
  "column_name": "optional display snapshot",
  "due_date": "2026-09-20T18:00:59.999Z",
  "due_date_time_present": true
}
```

No deadline:

```json
{
  "due_date": null,
  "due_date_time_present": false
}
```

### `pending_commands.candidates`

Candidate metadata uses the same pair:

```json
{
  "metadata": {
    "column_name": "optional display snapshot",
    "due_date": "2026-09-20T00:00:00.000Z",
    "due_date_time_present": false
  }
}
```

No JSONB GIN index is required.

## Updated command deadline contract

Command arguments distinguish set/change date-only, set/change date-time, and clear.

Date-only set/change intent:

```json
{
  "version": 1,
  "payload": {
    "operation": "set_due_date",
    "card_id": "kaiten-card-id",
    "due_date": "2026-09-20",
    "due_date_time_present": false,
    "source_text": "поставь срок на 20 сентября"
  }
}
```

Date-time set/change intent:

```json
{
  "version": 1,
  "payload": {
    "operation": "set_due_date",
    "card_id": "kaiten-card-id",
    "due_date": "2026-09-20T18:00:00.000Z",
    "due_date_time_present": true,
    "source_text": "поставь срок на 20 сентября в 18:00"
  }
}
```

Clear intent:

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

After successful Kaiten update, notification dedup must use a fresh read-back value from update response or subsequent GET, because Kaiten may normalize date-time seconds.

## Notification delivery guarantee clarification

The `002-00b` recovery design remains valid operationally:

```text
RESERVED -> SENT
RESERVED -> FAILED
FAILED -> RESERVED -> SENT/FAILED
stale RESERVED -> RESERVED reclaim -> SENT/FAILED
```

Guarantee wording:

```text
UNIQUE dedup reservation prevents ordinary parallel/repeated polling sends
before external MAX send.
```

It does not prove exactly-once delivery.

Crash window:

```text
MAX send succeeded
process crashed before SENT was committed
later reclaim/retry sends again
```

MVP guarantee:

```text
at-least-once delivery with database dedup/reservation before send
```

If MAX later provides an idempotency key, that must be verified in a separate integration audit.

## Updated affected first-migration contract

Affected table:

```text
notification_history
```

Deadline fields:

```text
due_at TIMESTAMPTZ NOT NULL
due_date_time_present BOOLEAN NOT NULL
```

Dedup unique:

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

PostgreSQL type inventory:

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

`DATE` is not required by the first migration.

Unchanged notification fields/checks:

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
ck_notification_history_type
ck_notification_history_delivery_status
```

The first business migration can now be created once with the final deadline contract.

## Test-card restoration/cleanup evidence

Initial card deadline:

```json
{
  "due_date": null,
  "due_date_time_present": false
}
```

Restoration after primary probe:

```json
{
  "request": {
    "due_date": null,
    "due_date_time_present": false
  },
  "update_status": 200,
  "get_status": 200,
  "get_response": {
    "due_date": null,
    "due_date_time_present": false
  }
}
```

Restoration after optional list probe:

```json
{
  "request": {
    "due_date": null,
    "due_date_time_present": false
  },
  "update_status": 200,
  "get_status": 200,
  "get_response": {
    "due_date": null,
    "due_date_time_present": false
  }
}
```

Cleanup status:

```text
PASS - test card restored to initial deadline state.
```

## Unchanged architecture decisions

Unchanged from `002-00a`/`002-00b`:

- Kaiten remains the only source of truth.
- No persistent local Kaiten cache.
- Seven-table model remains the target.
- Application-generated UUID PKs.
- MAX private 1:1 only.
- One Kaiten connection per user.
- `max_chat_binding_id` for internal MAX chat binding FK.
- `TEXT + CHECK`, no PostgreSQL ENUM.
- PendingCommand includes `FAILED`, `CANCELLED`, `EXPIRED`.
- `notification_settings.timezone = 'UTC'` default.
- No physical user deletion.
- No JSONB GIN indexes.
- No full outbox.
- No production implementation in this stage.

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
codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
```

Temporary diagnostics:

```text
none
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
25 passed in 2.71s

.venv\Scripts\python.exe -m pytest -W error
25 passed in 2.29s

.venv\Scripts\python.exe -m ruff format --check .
48 files already formatted

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
?? codex/prompts/002_00c_live_kaiten_deadline_representation_acceptance_probe_prompt.md
?? codex/reports/002_00_mvp_service_data_model_audit_report.md
?? codex/reports/002_00a_mvp_service_data_model_final_specification.md
?? codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
?? codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md

git diff --stat
<no output, exit code 0; working-tree changes are untracked>
```

## Final status

ACCEPTED LIVE CONTRACT - READY FOR 002-01
