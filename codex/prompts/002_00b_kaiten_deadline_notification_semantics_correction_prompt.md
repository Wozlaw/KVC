# 002-00b — Kaiten deadline semantics and notification dedup correction

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**, ветка `002 — MVP service data model`.

Предыдущие документы:

```text
codex/reports/002_00_mvp_service_data_model_audit_report.md
codex/reports/002_00a_mvp_service_data_model_final_specification.md
```

`002-00a` принят как базовый frozen MVP-контракт, однако перед `002-01` обнаружен один потенциально существенный дефект: deadline Kaiten в спецификации сведен к `DATE` / `YYYY-MM-DD`, хотя реальный API может поддерживать deadline с точным временем.

Этот этап — **только корректировка спецификации**. Не начинай SQLAlchemy/Alembic-реализацию.

## Цель

Проверить официальный Kaiten API contract для deadline и скорректировать только затронутые части модели так, чтобы:

- время deadline не терялось;
- изменение только времени срока корректно влияло на notification dedup;
- dialog/resolver snapshots сохраняли реальную семантику API;
- команды могли задавать дату, дату+время и удаление срока;
- KVC по-прежнему не хранил локальную копию карточек Kaiten;
- первая business migration в `002-01` сразу создавалась в окончательном виде.

## 1. Обязательная проверка официального Kaiten API

Используй **официальную документацию Kaiten API** как нормативный внешний источник.

Проверь как минимум:

```text
due_date
due_date_time_present
```

Установи:

1. фактические названия полей;
2. тип и формат `due_date`;
3. может ли deadline содержать часы/минуты;
4. назначение `due_date_time_present`;
5. как представляется deadline без времени;
6. timezone/offset semantics;
7. что происходит при изменении только времени при той же календарной дате.

Если актуальный API отличается от предположения выше, следуй фактическому контракту и явно укажи расхождение.

В отчете дай ссылки на официальные разделы API. Не используй сторонние статьи как нормативный источник.

## 2. Базовую архитектуру не менять

Остаются неизменными принципы `002-00a`:

- Kaiten — единственный source of truth;
- KVC не хранит постоянный cache boards/cards/comments/attachments/state;
- UUID application-generated PK;
- MAX только private 1:1;
- один Kaiten connection на пользователя;
- `max_chat_binding_id` для внутренней FK-ссылки;
- `TEXT + CHECK`, не PostgreSQL ENUM;
- `FAILED`, `CANCELLED`, `EXPIRED` у PendingCommand;
- `timezone = 'UTC'` по умолчанию;
- нет physical user delete;
- нет JSONB GIN indexes без query requirement;
- нет outbox в MVP;
- нет новых business tables.

## 3. Проблема текущего контракта

В `002-00a` зафиксировано:

```text
notification_history.due_date DATE
```

Dedup key:

```text
(user_id, kaiten_card_id, due_date, notification_type)
```

и JSONB examples в основном используют `YYYY-MM-DD`.

Если Kaiten допускает:

```text
2026-08-20 12:00
```

и затем срок меняется на:

```text
2026-08-20 18:00
```

то `DATE` теряет изменение и старый dedup key может ошибочно подавить новое уведомление.

## 4. Коррекция `notification_history`

Если официальный API подтверждает deadline с временем, заменить:

```text
due_date DATE
```

на:

```text
due_at TIMESTAMPTZ
due_date_time_present BOOLEAN NOT NULL
```

Семантика:

- `due_at` — точный нормализованный deadline marker из Kaiten;
- `due_date_time_present` — отражает, был ли deadline задан с точным временем;
- это dedup/audit marker, а не локальная карточечная сущность.

Если официальный API требует иной способ без потери семантики — используй его и обоснуй.

## 5. Dedup key

Пересмотри:

```text
uq_notification_history_dedup
```

Базовый кандидат:

```text
(
    user_id,
    kaiten_card_id,
    due_at,
    due_date_time_present,
    notification_type
)
```

Проверь, нужен ли `due_date_time_present` именно в UNIQUE key. Если при одинаковом `due_at` он не добавляет различимой семантики, выбери минимально достаточный ключ и обоснуй.

Главное требование:

> изменение deadline, которое Kaiten считает значимым, не должно теряться в dedup identity.

Не создавай дублирующие secondary indexes.

## 6. Notification classification

Формально определить:

```text
DUE_SOON
DUE_TODAY
OVERDUE
```

для двух случаев.

### Deadline без времени

Если API показывает отсутствие точного времени, классификация должна опираться на календарную дату пользователя в:

```text
notification_settings.timezone
```

### Deadline с временем

Если время присутствует, учитывать точный instant deadline, а пользовательскую timezone использовать для локальной календарной классификации и отображения.

Не использовать timezone сервера как источник пользовательской семантики.

## 7. JSONB contracts

Проверить и скорректировать только затронутые контракты:

```text
dialog_sessions.last_card_list
pending_commands.arguments
pending_commands.candidates
```

### `last_card_list`

Не терять время deadline.

Предпочтительно хранить временный snapshot вида:

```json
{
  "due_date": "ISO-8601 value or null",
  "due_date_time_present": true
}
```

или фактически эквивалентный контракт Kaiten API.

Snapshot:

- versioned;
- bounded;
- temporary;
- overwriteable;
- не является локальным cache карточки.

### `pending_commands.arguments`

Не ограничивать deadline только `YYYY-MM-DD`.

Контракт должен однозначно различать:

```text
установить дату без времени
установить дату и точное время
изменить срок
удалить срок
```

Сделай versioned JSON contract, согласованный с реальным Kaiten API.

## 8. Timestamp contract

После проверки API разделить:

### KVC lifecycle instants

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

Хранятся как `TIMESTAMPTZ`.

### Kaiten deadline marker

Если deadline является timestamp:

```text
notification_history.due_at TIMESTAMPTZ
```

Удалить из `002-00a` утверждение, что Kaiten deadline всегда должен храниться как PostgreSQL `DATE`.

Если `DATE` после корректировки нигде в первой migration больше не нужен — исключить его из migration type inventory.

## 9. `RESERVED / SENT / FAILED` recovery semantics

Отдельно проверить текущий минимальный delivery contract:

```text
RESERVED -> SENT
RESERVED -> FAILED
```

Проблема:

- `FAILED` row продолжает занимать UNIQUE dedup key;
- stale `RESERVED` после аварии процесса также занимает ключ;
- следующий polling cycle не должен навсегда считать такой event обработанным.

Не реализовывать retry worker и не вводить полноценный outbox.

Но зафиксировать минимальную future recovery semantics, например:

```text
FAILED -> RESERVED -> SENT/FAILED
stale RESERVED -> reclaim -> RESERVED
```

с обязательным concurrency guard.

Если для этого уже в первой migration действительно требуется дополнительное поле (`attempt_count`, `last_attempt_at`, `reserved_at` и т.п.), сначала докажи необходимость. Не расширяй schema «на всякий случай».

## 10. Индексы

Повторно проверить только затронутую часть index/query matrix:

- notification dedup;
- возможный stale reservation lookup;
- отсутствие duplicate indexes;
- отсутствие отдельного `due_at` index без доказанного query case.

## 11. First migration contract

Не создавай Alembic revision.

Обнови спецификацию первой migration только в затронутой части:

- исправленные поля `notification_history`;
- исправленный UNIQUE dedup key;
- необходимые CHECK/default semantics;
- актуальный список PostgreSQL types.

Первая реальная migration в `002-01` должна сразу содержать корректный deadline contract. Не создавать ситуацию, когда сразу после initial migration потребуется migration №2 для исправления deadline.

## 12. Что запрещено

Не делать на `002-00b`:

- production Python code changes;
- SQLAlchemy models;
- Alembic revision;
- DDL;
- `alembic upgrade`;
- live PostgreSQL schema changes;
- Kaiten client;
- MAX bot;
- notification worker;
- retry scheduler;
- outbox;
- encryption implementation;
- новые business tables;
- local Kaiten cache;
- переход к `002-01`.

## 13. Итоговый отчет

Создай:

```text
codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
```

Отчет должен содержать:

1. Executive summary.
2. Проверенный официальный Kaiten deadline contract.
3. Official API references.
4. Точное противоречие с `002-00a`.
5. Final deadline storage decision.
6. Final notification dedup key.
7. `due_date_time_present` semantics.
8. DUE_SOON / DUE_TODAY / OVERDUE contract.
9. Updated JSONB deadline contracts.
10. Updated `pending_commands.arguments`.
11. Timestamp/timezone correction.
12. `RESERVED/SENT/FAILED` recovery semantics.
13. Updated affected index/query matrix.
14. Updated affected first-migration contract.
15. Explicit list of unchanged `002-00a` decisions.
16. Consistency review.
17. Changed files.
18. Quality gate.
19. Final status.

Это corrective addendum к `002-00a`, а не полный редизайн модели.

## 14. Consistency checks

Перед завершением обязательно подтвердить:

1. Время deadline не теряется.
2. Deadline без времени остается однозначно интерпретируемым.
3. Значимое изменение только времени влияет на dedup identity.
4. User timezone не подменяется server timezone.
5. JSONB остается временным context snapshot.
6. Command arguments различают set/change/clear deadline.
7. `FAILED` и stale `RESERVED` принципиально могут быть восстановлены без duplicate send.
8. Нет дублирующих indexes.
9. Initial business migration остается одной цельной migration.
10. Все незатронутые решения `002-00a` сохранены.

## 15. Quality gate

Выполни baseline gate проекта:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src
git diff --check
git status --short
git diff --stat
```

Не исправляй несвязанные baseline issues автоматически.

## 16. Git discipline

Не коммить автоматически.

В отчете отдельно показать:

```text
Production code changes:
Tests:
Documentation:
Report:
Other:
```

Ожидается:

```text
Production code changes:
none

Tests:
none
```

## 17. Финальный статус

Если официальный Kaiten API contract подтвержден и коррекция полностью определена:

```text
ACCEPTED CORRECTION — READY FOR 002-01
```

Если официальная документация недостаточна или противоречива для безопасного решения:

```text
BLOCKED — KAITEN DEADLINE CONTRACT REQUIRES USER DECISION
```

В этом случае не начинать реализацию.

## Главное правило

`002-00b` — это **точечная коррекция frozen MVP data model до первой business migration**.

После этого этапа `002-01` должен реализовывать уже окончательно корректный deadline и notification dedup contract.
