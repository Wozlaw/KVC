# 002-00c — Live Kaiten deadline representation acceptance probe

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
```

Обязательные исходные документы:

```text
codex/reports/002_00_mvp_service_data_model_audit_report.md
codex/reports/002_00a_mvp_service_data_model_final_specification.md
codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
```

`002-00b` подтвердил по официальной документации Kaiten, что deadline состоит из семантической пары:

```text
due_date
due_date_time_present
```

и что deadline может включать точное время.

Однако перед созданием первой business migration остался один недоказанный момент:

> как Kaiten REST API фактически кодирует и возвращает **ненулевой deadline без времени** (`due_date_time_present = false`) и можно ли безопасно восстановить исходную календарную дату только из `TIMESTAMPTZ`.

Этот этап — **узкий live acceptance probe внешнего API**, а не новая архитектурная ветка.

---

# 1. Главная цель

Экспериментально проверить реальное round-trip поведение Kaiten для четырех операций:

```text
1. установить deadline только датой;
2. установить ту же дату с точным временем;
3. изменить только время при неизменной календарной дате;
4. удалить deadline.
```

Для каждого шага необходимо получить фактический REST response и зафиксировать семантическую пару:

```text
due_date
due_date_time_present
```

Итог этапа должен однозначно ответить:

```text
Достаточно ли:
due_at TIMESTAMPTZ + due_date_time_present BOOLEAN

или для date-only deadline необходимо отдельное календарное поле DATE.
```

После `002-00c` должен существовать окончательный storage contract, пригодный для непосредственной реализации `002-01`.

---

# 2. Scope

Разрешено:

- читать официальную документацию Kaiten API;
- использовать уже имеющиеся локальные credentials/configuration;
- выполнять live API-запросы к Kaiten;
- изменять deadline **только у специально выбранной тестовой карточки**;
- читать карточку после каждого изменения;
- сохранить обезличенные/sanitized результаты в отчете;
- восстановить исходное состояние тестовой карточки после проверки.

Запрещено:

- менять production Python code;
- создавать SQLAlchemy models;
- создавать Alembic revision;
- изменять PostgreSQL schema;
- реализовывать Kaiten adapter;
- реализовывать notification worker;
- реализовывать retry/outbox;
- менять реальные рабочие карточки без явного признака тестового объекта;
- выводить API token или иные secrets;
- коммитить автоматически;
- начинать `002-01`.

---

# 3. Безопасность live-проверки

## 3.1. Credentials

Используй только уже существующий способ конфигурации проекта.

Не:

- печатай token;
- записывай token в report;
- записывай token в command history намеренно;
- добавляй token в source files;
- добавляй token в fixtures;
- меняй `.env` без необходимости.

Если token отсутствует или Kaiten недоступен, не имитируй результат.

Финальный статус в этом случае:

```text
BLOCKED — LIVE KAITEN ACCESS REQUIRED
```

и перечисли только минимально необходимые условия для повторного запуска.

---

## 3.2. Test card

Live mutation разрешена только для:

- явно существующей тестовой карточки;
- либо временной карточки в явно предназначенной для тестов доске/пространстве.

Не выбирай произвольную рабочую карточку.

Перед первым изменением зафиксируй текущее состояние:

```text
card id
card title/code — sanitized if necessary
due_date
due_date_time_present
```

После завершения:

- восстанови исходный deadline;
- либо удали созданную временную карточку, если ее создание было безопасно и разрешено текущим API/configuration.

В отчете обязательно указать, что cleanup/restoration выполнен.

Если безопасный test target отсутствует:

```text
BLOCKED — SAFE TEST CARD REQUIRED
```

Не производи mutation на рабочей карточке.

---

# 4. Нормативная документация

Повторно сверить официальный Kaiten REST API contract как минимум для:

```text
Create card
Update card
Retrieve card
Retrieve card list
```

и полей:

```text
due_date
due_date_time_present
```

Использовать официальные Kaiten API pages как нормативный источник.

Live probe имеет приоритет для определения фактического wire representation, если документация не описывает date-only round-trip достаточно подробно.

Не использовать сторонние статьи как нормативный источник.

---

# 5. Методика live-probe

Используй один и тот же test card.

Для каждого шага фиксируй:

```text
request payload
HTTP status
response due_date
response due_date_time_present
subsequent GET due_date
subsequent GET due_date_time_present
```

Не сохраняй полный response, если он содержит лишние рабочие данные.

Нужен минимальный sanitized fragment.

---

# 6. Probe A — date-only deadline

Установи конкретную будущую календарную дату без времени.

Используй стабильную дату, не зависящую от текущего дня, например:

```text
2026-09-20
```

или другую безопасную будущую дату, если тест проводится позднее.

Intent:

```text
deadline = calendar date only
due_date_time_present = false
```

После UPDATE обязательно выполнить отдельный GET карточки.

Зафиксировать:

```text
точный request due_date
request due_date_time_present
response due_date
response due_date_time_present
GET due_date
GET due_date_time_present
```

Ключевой вопрос:

> Возвращает ли Kaiten date-only deadline как `YYYY-MM-DD`, как timestamp в UTC/offset, как timestamp некоторой workspace timezone или иным образом?

Не интерпретировать значение до того, как записан фактический raw field.

---

# 7. Probe B — same date with exact time

На той же карточке установить **ту же календарную дату**, но с явно заданным временем.

Например:

```text
2026-09-20 12:00
```

и:

```text
due_date_time_present = true
```

После UPDATE выполнить GET.

Зафиксировать те же поля.

Проверить:

- меняется ли только `due_date`;
- как передается timezone/offset;
- нормализует ли Kaiten значение;
- сохраняется ли `due_date_time_present = true`.

---

# 8. Probe C — change only time

Не меняя календарную дату, изменить только время:

```text
12:00 -> 18:00
```

После UPDATE выполнить GET.

Зафиксировать:

```text
before due_date
after due_date
before due_date_time_present
after due_date_time_present
```

Подтвердить:

> изменение только времени является различимым по REST representation и должно менять notification dedup identity.

---

# 9. Probe D — clear deadline

Удалить срок через официальный update contract.

Ожидаемый смысл:

```text
due_date = null
```

Проверить фактический response и GET после обновления.

Зафиксировать:

```text
due_date
due_date_time_present
```

Отдельно определить, какое значение флага возвращает API при отсутствии deadline.

Не придумывать значение, если API его не возвращает или контракт отличается.

---

# 10. Optional probe — list endpoint

Если безопасно и просто, дополнительно проверить ту же карточку через list endpoint.

Цель:

подтвердить, что:

```text
Retrieve card
Retrieve card list
```

возвращают одинаковую deadline semantics.

Если list endpoint требует лишнего scope или затрудняет тест без дополнительной ценности — можно не выполнять, но указать причину.

---

# 11. Raw evidence format

В отчете для каждого шага дать компактный evidence block, например:

```json
{
  "probe": "date_only",
  "request": {
    "due_date": "...",
    "due_date_time_present": false
  },
  "update_response": {
    "due_date": "...",
    "due_date_time_present": false
  },
  "get_response": {
    "due_date": "...",
    "due_date_time_present": false
  }
}
```

Все unrelated card fields исключить.

Не включать:

- token;
- cookies;
- Authorization header;
- личные данные;
- URL с secret/query token;
- полные payloads рабочего пространства.

---

# 12. Главный архитектурный вопрос

По результатам Probe A выбрать один из контрактов.

## Contract A — единый instant marker допустим

Оставить контракт `002-00b`:

```text
due_at TIMESTAMPTZ NOT NULL
due_date_time_present BOOLEAN NOT NULL
```

только если live probe доказывает, что для date-only deadline исходная пользовательская календарная дата однозначно и стабильно восстанавливается без timezone ambiguity.

В отчете показать конкретное правило восстановления.

Не ограничиваться фразой «Kaiten возвращает timestamp».

Нужно доказать:

> почему преобразование не способно превратить выбранное пользователем 20 сентября в 19 или 21 сентября при смене `notification_settings.timezone`.

---

## Contract B — раздельное хранение date-only и date-time

Если date-only representation нельзя безопасно трактовать как универсальный instant, зафиксировать более строгую модель.

Предпочтительный кандидат:

```text
due_date DATE NULL
due_at TIMESTAMPTZ NULL
due_date_time_present BOOLEAN NOT NULL
```

CHECK-инвариант:

```text
due_date_time_present = false
  -> due_date IS NOT NULL
     AND due_at IS NULL

due_date_time_present = true
  -> due_at IS NOT NULL
     AND due_date IS NULL
```

Для notification history строки без deadline не создаются.

Если фактический API требует другой вариант — предложить минимальный корректный контракт.

Главный критерий:

> date-only deadline хранится как календарное значение и никогда не меняет день из-за timezone conversion.

---

# 13. Dedup contract после live probe

Пересчитать dedup key согласно выбранному storage contract.

## Если Contract A

Кандидат:

```text
(
  user_id,
  kaiten_card_id,
  due_at,
  due_date_time_present,
  notification_type
)
```

## Если Contract B

Нужно корректно учитывать взаимоисключающие:

```text
due_date
due_at
```

PostgreSQL UNIQUE с nullable columns имеет особенности.

Поэтому не копируй механически:

```text
UNIQUE(user_id, kaiten_card_id, due_date, due_at, ...)
```

если `NULL` semantics ослабляет дедупликацию.

Спроектируй физически enforceable PostgreSQL solution, например:

- два partial UNIQUE index;
- либо иной простой и однозначный вариант.

Предпочтительно при Contract B:

```text
UNIQUE (
  user_id,
  kaiten_card_id,
  due_date,
  notification_type
)
WHERE due_date_time_present = false
```

и:

```text
UNIQUE (
  user_id,
  kaiten_card_id,
  due_at,
  notification_type
)
WHERE due_date_time_present = true
```

Проверь naming convention проекта.

Не добавляй дополнительные индексы поверх этих UNIQUE indexes без отдельного query case.

---

# 14. Notification classification

По итогам live probe окончательно заморозить classification.

## Date-only

Дата должна сравниваться как **calendar date**:

```text
DUE_TODAY
OVERDUE
DUE_SOON
```

без timezone-induced смещения самой выбранной даты.

User timezone используется для определения текущей локальной даты пользователя.

## Date-time

Точный deadline сравнивается как instant:

```text
due_at vs now_utc
```

а `notification_settings.timezone` используется для локального отображения и определения local today.

---

# 15. JSONB contract

После live probe привести в соответствие:

```text
dialog_sessions.last_card_list
pending_commands.arguments
pending_commands.candidates
```

Не создавать лишнюю внутреннюю модель, если достаточно сохранять внешний semantic pair.

Важно различать:

```text
date-only
date-time
no deadline
```

Если Contract B принят для relational dedup storage, JSONB не обязан копировать внутренние SQL columns один-в-один. Он должен сохранять понятную внешнюю/intent semantics без потери данных.

---

# 16. Notification delivery guarantee — уточнение формулировки

`002-00b` содержит recovery contract:

```text
FAILED -> RESERVED -> ...
stale RESERVED -> reclaim
```

Его можно сохранить как operational recovery design.

Но необходимо исправить слишком сильное утверждение о предотвращении duplicate send.

Зафиксировать:

> UNIQUE dedup reservation предотвращает обычные параллельные/повторные polling sends до внешней отправки, но без idempotency primitive со стороны MAX невозможно гарантировать exactly-once delivery при crash window между успешной отправкой в MAX и фиксацией `SENT` в PostgreSQL.

Crash window:

```text
MAX send succeeded
        ↓
process crashed
        ↓
SENT not committed
```

После reclaim повторная отправка потенциально возможна.

На этом этапе:

- не решать эту проблему outbox-ом;
- не добавлять новую инфраструктуру;
- не обещать exactly-once;
- классифицировать MVP guarantee как минимум `at-least-once with dedup before send` / эквивалентную точную формулировку.

Если официальный MAX API позже предоставляет idempotency key, это должно быть проверено отдельным integration-аудитом.

---

# 17. Что не пересматривать

Если live probe не выявляет иных противоречий, не менять:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
```

Не пересматривать:

- UUID;
- one active dialog;
- one active PendingCommand;
- MAX private-only;
- one Kaiten connection;
- secret contract;
- ownership invariant;
- `TEXT + CHECK`;
- `timezone = UTC`;
- no physical delete;
- no JSONB GIN;
- no outbox;
- seven-table model.

---

# 18. First migration contract

Не создавать migration.

Но после выбора Contract A/B окончательно обновить affected part будущей первой migration:

- `notification_history` deadline fields;
- CHECK constraints;
- UNIQUE / partial UNIQUE indexes;
- PostgreSQL type inventory;
- JSONB examples where relevant.

Цель:

```text
002-01
```

создает сразу окончательную initial business schema.

Не должно потребоваться немедленное `002-01a` только для исправления deadline representation.

---

# 19. Итоговый отчет

Создай:

```text
codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
```

Отчет должен содержать:

1. Executive summary.
2. Test environment summary без secrets.
3. Test card safety statement.
4. Official Kaiten contract references.
5. Probe A — date-only evidence.
6. Probe B — date-time evidence.
7. Probe C — time-only change evidence.
8. Probe D — clear deadline evidence.
9. Optional list-endpoint evidence.
10. Observed normalization/timezone behavior.
11. Final choice: Contract A or Contract B.
12. Exact rationale.
13. Final `notification_history` field contract.
14. Final CHECK constraints.
15. Final dedup UNIQUE/partial UNIQUE design.
16. Final classification semantics.
17. Updated JSONB deadline contract.
18. Updated command deadline contract.
19. Notification delivery guarantee clarification.
20. Updated affected first-migration contract.
21. Test-card restoration/cleanup evidence.
22. Unchanged architecture decisions.
23. Changed files.
24. Quality gate.
25. Final status.

---

# 20. Quality gate

Production code изменяться не должен.

После live probe выполнить:

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

Если для probe создавался временный diagnostic script, предпочтительно удалить его после использования.

Не оставлять production changes.

---

# 21. Git discipline

Не выполнять commit автоматически.

В отчете отдельно показать:

```text
Production code changes:
Tests:
Documentation:
Report:
Temporary diagnostics:
Other:
```

Ожидаемый итог:

```text
Production code changes:
none

Tests:
none

Temporary diagnostics:
none
```

если временные диагностические файлы удалены после проверки.

---

# 22. Критерий приемки

Этап считается завершенным только если:

- выполнен реальный live round-trip date-only deadline;
- выполнен реальный live round-trip date-time deadline;
- проверено изменение только времени;
- проверено удаление срока;
- test card восстановлена/удалена безопасно;
- date-only timezone ambiguity снята фактическими данными;
- выбран физически корректный PostgreSQL storage contract;
- dedup physically enforceable;
- notification classification непротиворечива;
- exactly-once delivery не заявляется без доказанного idempotency primitive;
- production code/schema не изменены;
- `002-01` больше не требует решения по deadline storage.

---

# 23. Финальный статус

Если live probe успешно снял неопределенность:

```text
ACCEPTED LIVE CONTRACT — READY FOR 002-01
```

Если отсутствует безопасный доступ к Kaiten/test card:

```text
BLOCKED — LIVE KAITEN ACCEPTANCE PREREQUISITE MISSING
```

Если API фактически ведет себя нестабильно или противоречиво:

```text
BLOCKED — KAITEN DEADLINE REPRESENTATION REQUIRES ARCHITECTURAL DECISION
```

Не начинать `002-01` при любом `BLOCKED`.

---

## Главное правило

`002-00c` должен не предположить, а **экспериментально доказать** реальное representation date-only deadline в Kaiten.

Только после этого deadline storage contract можно считать действительно замороженным для первой migration.
