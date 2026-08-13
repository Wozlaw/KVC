# 001-02a — Live PostgreSQL acceptance

## Контекст

Проект: **Kaiten Voice Control**.

Рабочий каталог:

```text
D:\Prog\KVControl
```

Предыдущие этапы:

```text
001-01  Project bootstrap
001-01a TestClient dependency cleanup
001-02  Configuration, PostgreSQL persistence and Alembic foundation
```

Отчёт предыдущего этапа:

```text
codex/reports/001_02_configuration_postgresql_persistence_alembic_foundation_report.md
```

Статус `001-02`:

```text
PASS WITH NOTES
```

Единственное незакрытое замечание:

```text
PostgreSQL live smoke: NOT RUN
```

Причиной на момент выполнения `001-02` было отсутствие локально установленного PostgreSQL и `KVC_DATABASE_URL`.

После этого пользователь вручную подготовил локальный PostgreSQL-контур.

Подтверждено вручную:

```text
PostgreSQL 18.6
psql доступен в PATH проекта
PostgreSQL Windows service: Running
127.0.0.1:5432: accepting connections
```

Созданы:

```text
role:     kvc_user
database: kvc_dev
```

Ручная проверка через `psql`:

```sql
SELECT current_user, current_database();
```

результат:

```text
current_user     = kvc_user
current_database = kvc_dev
```

```sql
SELECT 1;
```

результат:

```text
1
```

Проверено право создания объектов в БД:

```sql
SELECT has_database_privilege(
    current_user,
    current_database(),
    'CREATE'
);
```

результат:

```text
true
```

В корне проекта создан локальный:

```text
.env
```

с реальным `KVC_DATABASE_URL`.

`.env` подтверждён как Git-ignored и не должен попадать в репозиторий.

---

# 1. Цель этапа

Закрыть единственное примечание этапа `001-02` реальной интеграционной проверкой PostgreSQL.

Необходимо проверить фактический production-like маршрут локального приложения:

```text
.env
  ↓
AppSettings
  ↓
KVC_DATABASE_URL
  ↓
SQLAlchemy AsyncEngine
  ↓
asyncpg
  ↓
PostgreSQL 18.6
  ↓
kvc_dev
  ↓
SELECT 1
  ↓
AsyncSession
  ↓
dispose
```

И отдельно:

```text
Alembic
  ↓
project Settings
  ↓
same KVC_DATABASE_URL
  ↓
online PostgreSQL connection
  ↓
shared Base.metadata
```

Этап является **приёмочным**, а не архитектурным.

---

# 2. Жёсткие границы

В рамках `001-02a` запрещено:

- создавать предметные таблицы;
- создавать модели `users`, `kaiten_connections`, `dialog_sessions` и т. п.;
- создавать первую Alembic revision;
- создавать фиктивную empty migration;
- изменять согласованную структуру persistence;
- добавлять repository / Unit of Work;
- добавлять API endpoints;
- менять `/health`;
- реализовывать Kaiten/MAX/GigaChat/STT;
- добавлять scheduler/worker logic;
- вводить SQLite fallback;
- менять PostgreSQL role/database;
- менять системную конфигурацию PostgreSQL;
- менять пароль пользователя;
- печатать пароль или полный `KVC_DATABASE_URL`;
- добавлять secrets в отчёт;
- выполнять Git commit/push.

Если текущая реализация `001-02` работает как задумано, предпочтительный результат этапа — **вообще без изменений production-кода**.

Допустимы только:

- минимальные тестовые/диагностические изменения, если обнаружен реальный дефект;
- документационная корректировка;
- сам отчёт.

---

# 3. Предварительный аудит

До любых изменений изучить:

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

Проверить Git:

```powershell
git status --short
git diff --check
git log --oneline --decorate -5
```

Наличие текущего prompt-файла и будущего report-файла не считать архитектурным загрязнением.

---

# 4. Проверка PostgreSQL tooling

В активированной `.venv` выполнить:

```powershell
psql --version
where.exe psql
pg_isready -h 127.0.0.1 -p 5432
Get-Service *postgres*
```

Ожидается:

```text
PostgreSQL 18.6
psql найден
127.0.0.1:5432 accepting connections
postgresql-x64-18 Running
```

Не считать точное имя Windows service жёстким контрактом, если версия/имя сервиса отличается, но сервер фактически доступен.

---

# 5. Проверка `.env`

Подтвердить:

```text
.env существует
KVC_APP_ENV загружается
KVC_DATABASE_URL загружается
KVC_DATABASE_ECHO загружается
```

При этом:

- не выводить значение пароля;
- не выводить полный URL;
- не копировать `.env` в отчёт;
- не читать секрет в диагностический print.

Разрешено показывать только безопасную информацию, например:

```text
scheme = postgresql+asyncpg
host = 127.0.0.1
port = 5432
database = kvc_dev
credentials_present = true
```

если текущие проектные API позволяют получить это без риска утечки.

---

# 6. Settings live acceptance

Использовать существующий `AppSettings` / фактический settings API проекта.

Проверить:

```text
KVC_APP_ENV = development
KVC_DATABASE_URL присутствует
KVC_DATABASE_ECHO корректно парсится
database URL проходит project validation
```

Не создавать новый параллельный конфигурационный механизм.

Проверить, что обычный:

```python
import kvc_api
```

по-прежнему:

- не требует соединения с БД;
- не выполняет network call;
- не падает при import-time.

---

# 7. AsyncEngine live smoke

Использовать **реальный factory из `kvc_persistence`**, а не самостоятельный вызов `create_async_engine()` в тестовом скрипте.

Проверить:

1. engine создаётся через project Settings;
2. фактический объект — `AsyncEngine`;
3. используется PostgreSQL async driver contract;
4. соединение открывается;
5. выполняется:

```sql
SELECT 1
```

6. получен результат `1`;
7. соединение закрывается;
8. engine корректно dispose.

Не печатать:

```text
engine.url
```

если это может раскрыть пароль.

Если SQLAlchemy предоставляет безопасный redacted rendering URL — допустимо использовать только его.

---

# 8. Project database health probe

Использовать уже реализованный в `001-02` project health probe.

Он должен на реальной БД вернуть успешный результат.

Ожидаемый смысл:

```text
ok = true
```

и отсутствие error.

Зафиксировать фактический контракт результата, а не придумывать новый.

Проверить, что health probe:

- выполняет read-only `SELECT 1`;
- не создаёт таблицы;
- не изменяет данные;
- не раскрывает credentials.

---

# 9. AsyncSession live acceptance

Использовать существующий session factory проекта.

Через реальный:

```text
async_sessionmaker
```

создать `AsyncSession`.

Выполнить read-only:

```sql
SELECT 1
```

через SQLAlchemy:

```python
text("SELECT 1")
```

или существующий эквивалент.

Подтвердить:

```text
AsyncSession creation: PASS
SELECT 1 via AsyncSession: PASS
session close: PASS
```

Не выполнять `CREATE`, `INSERT`, `UPDATE`, `DELETE`.

---

# 10. Database identity check через application path

Через SQLAlchemy/asyncpg, а не `psql`, выполнить read-only запрос:

```sql
SELECT current_user, current_database();
```

Ожидается:

```text
current_user = kvc_user
current_database = kvc_dev
```

Это необходимо, чтобы доказать, что приложение подключается именно к ожидаемой локальной БД и роли.

Пароль не выводить.

---

# 11. Проверка текущей схемы до Alembic

До любых Alembic online-команд зафиксировать список пользовательских таблиц.

Допустим read-only запрос к PostgreSQL catalog / `information_schema`.

Ожидается отсутствие предметных таблиц проекта.

Если имеется только системная инфраструктура PostgreSQL — это нормально.

Если уже присутствует:

```text
alembic_version
```

зафиксировать это как факт и выяснить происхождение, но не удалять автоматически.

Если присутствуют неожиданные пользовательские таблицы:

- не удалять;
- остановить destructive действия;
- описать в отчёте;
- итоговый статус не выше `PASS WITH NOTES`, а при конфликте с ожидаемой пустой схемой — `BLOCKED`.

---

# 12. Alembic online acceptance

Использовать существующий:

```text
alembic.ini
src/kvc_persistence/migrations/env.py
```

и реальный `KVC_DATABASE_URL` из `.env`.

Не подставлять URL вручную в `alembic.ini`.

## 12.1. Обязательные безопасные diagnostics

Выполнить:

```powershell
python -m alembic -c alembic.ini heads
python -m alembic -c alembic.ini history
python -m alembic -c alembic.ini current
```

Ожидается:

```text
heads: no revisions
history: no revisions
current: no project revision
```

Точный текст зависит от Alembic; важен смысл и exit code.

## 12.2. `alembic check`

Выполнить:

```powershell
python -m alembic -c alembic.ini check
```

если эта команда поддерживается установленной Alembic `1.19.1` в текущем environment.

Цель:

- реальное online подключение;
- загрузка `Base.metadata`;
- autogenerate comparison;
- подтверждение отсутствия schema drift относительно пустой metadata.

Ожидаемый смысл:

```text
No new upgrade operations detected
```

или штатный эквивалент.

Если команда имеет другое штатное поведение при отсутствии revisions — зафиксировать реальный результат.

Не обходить проверку созданием пустой revision.

## 12.3. `upgrade head`

Не выполнять `alembic upgrade head` автоматически, если это может создать служебную таблицу `alembic_version` при отсутствии реальных revisions.

Сначала определить по фактической версии Alembic/реализации, будет ли команда модифицировать БД.

Цель текущего этапа — **live acceptance без искусственного изменения схемы**.

Если безопасные `current` + `check` уже доказали online connection и корректность migration environment, этого достаточно.

---

# 13. Проверка схемы после Alembic diagnostics

После online diagnostics повторно проверить пользовательские таблицы.

Целевой инвариант:

```text
0 предметных таблиц Kaiten Voice Control
0 фиктивных migration tables/revisions, созданных только ради проверки
```

Если `alembic_version` существовала до проверки — просто зафиксировать.

Если она неожиданно была создана выполняемой диагностической командой:

- не скрывать;
- определить точную причину;
- не удалять автоматически;
- описать отклонение.

---

# 14. Integration test policy

Обычный:

```powershell
pytest
```

должен оставаться независимым от наличия локального PostgreSQL.

Не превращать весь unit/smoke suite в network-dependent suite.

Если для live PostgreSQL acceptance имеет смысл добавить integration test, он должен:

- находиться в `tests/integration/`;
- явно требовать `KVC_DATABASE_URL`;
- безопасно skip при отсутствии live DB config;
- не создавать/изменять бизнес-таблицы;
- выполнять только read-only operations;
- не выводить credentials.

Но **не добавлять integration test только ради количества тестов**, если live acceptance можно корректно выполнить существующим проектным диагностическим API и зафиксировать в отчёте.

---

# 15. Нормальный quality gate

После live-проверок выполнить полный существующий gate:

```powershell
python --version
python -m pip --version
python -m pip check
pytest
pytest -W error
ruff format --check .
ruff check .
mypy src
```

Ожидается:

```text
Python 3.12.x
pip check: PASS
pytest: PASS
pytest warnings: 0
pytest -W error: PASS
ruff format --check: PASS
ruff check: PASS
mypy src: PASS
```

Не снижать coverage threshold и не подавлять warnings.

---

# 16. Import/TOML checks

Выполнить:

```powershell
python -c "import kvc_config, kvc_persistence, kvc_api; print('config, persistence and api imports ok')"
```

Подтвердить, что import не инициирует network connection.

Проверить TOML:

```powershell
python -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); tomllib.load(open('.codex/config.toml','rb')); print('toml ok')"
```

---

# 17. Security acceptance

Проверить:

```powershell
git check-ignore -v -- .env .venv
git status --short
git diff --check
```

Подтвердить:

```text
.env ignored
.venv ignored
```

Проверить version-controlled файлы на случайное попадание:

- локального пароля;
- полного `KVC_DATABASE_URL`;
- иных credentials.

Не включать реальные secret values в команды отчёта.

Если shell history содержит пароль из ручных действий пользователя, это не является содержимым Git, но не копировать такую историю в отчёт.

---

# 18. Что не исправлять без дефекта

Если live acceptance проходит, **не менять production-код ради косметики**.

Не выполнять:

- рефакторинг `Settings`;
- переименование persistence modules;
- переписывание Alembic;
- изменение naming convention;
- pool tuning;
- добавление CLI;
- добавление readiness endpoint;
- добавление migrations;
- добавление business models.

Если обнаружен реальный дефект `001-02`, исправить только минимально необходимое и подробно зафиксировать:

```text
observed failure
root cause
minimal correction
verification
```

---

# 19. Отчёт

Создать:

```text
codex/reports/001_02a_live_postgresql_acceptance_report.md
```

## 19.1. Baseline

Указать:

- текущий commit SHA/message;
- Git status;
- Python version;
- PostgreSQL version;
- service status;
- `pg_isready`.

## 19.2. Safe configuration summary

Без secrets:

```text
app_env
database scheme
host
port
database
database user
database echo
```

Пароль:

```text
REDACTED / not reported
```

Не выводить полный URL.

## 19.3. Application connection

Привести фактический результат:

```text
Settings load
AsyncEngine creation
connection
SELECT 1
current_user
current_database
dispose
```

## 19.4. Health probe

Показать фактический safe result.

## 19.5. AsyncSession

Показать результат session lifecycle и `SELECT 1`.

## 19.6. Alembic online diagnostics

Зафиксировать результаты:

```text
heads
history
current
check
```

и подтвердить:

```text
real PostgreSQL connection used
shared Base.metadata used
no fake revision created
```

## 19.7. Schema state

До и после диагностики показать только имена пользовательских таблиц.

Цель:

```text
no Kaiten Voice Control business tables
```

Не публиковать лишние системные каталоги.

## 19.8. Automated quality gate

Привести результаты:

```text
pip check
pytest
pytest -W error
ruff format --check
ruff check
mypy
imports
TOML
git diff --check
```

## 19.9. Security

Подтвердить:

```text
.env ignored
no credentials in Git
no full DB URL in report/log excerpts
```

## 19.10. Changed files

Явно разделить:

```text
production code
tests
documentation
report
```

Если production code не менялся — написать:

```text
Production code changes: none
```

Это предпочтительный результат.

## 19.11. Deviations

Описать любые отклонения.

## 19.12. Final status

Использовать:

```text
PASS
PASS WITH NOTES
BLOCKED
FAIL
```

### PASS

Только если:

```text
PostgreSQL reachable
Settings live load PASS
AsyncEngine PASS
SELECT 1 PASS
current_user = kvc_user
current_database = kvc_dev
health probe PASS
AsyncSession PASS
dispose PASS
Alembic online diagnostics PASS
no fake revisions
no unexpected business tables
full quality gate PASS
0 warnings
secrets safe
```

### PASS WITH NOTES

Допустим только при некритическом внешнем/инструментальном нюансе, не влияющем на correctness.

### BLOCKED

Если:

- `.env` отсутствует;
- PostgreSQL недоступен;
- credentials не работают;
- обнаружена неожиданная схема, которую нельзя безопасно менять;
- требуется системная конфигурация вне задания.

### FAIL

Если:

- project persistence implementation не может реально подключиться;
- SQLAlchemy/asyncpg contract нарушен;
- Alembic online environment не работает;
- quality gate падает;
- секреты утекли в version-controlled files.

---

# 20. Критерий завершения

Этап завершён, когда реальная локальная цепочка доказана:

```text
.env
  ↓
AppSettings
  ↓
SQLAlchemy AsyncEngine
  ↓
asyncpg
  ↓
PostgreSQL 18.6 / kvc_dev / kvc_user
  ↓
SELECT 1
  ↓
AsyncSession
  ↓
health probe
  ↓
Alembic online diagnostics
  ↓
clean dispose
```

и одновременно сохранены инварианты:

```text
0 бизнес-таблиц
0 fake migrations
0 SQLite fallback
0 secrets in Git
0 warnings
```

После `PASS` этап `001-02` считается полностью закрытым без примечаний.

Следующий этап:

```text
001-03 — MVP service data model design and implementation
```

На нём уже допускается проектирование первой реальной схемы данных и первой содержательной Alembic migration.

Реализация `001-03` в текущую задачу не входит.
