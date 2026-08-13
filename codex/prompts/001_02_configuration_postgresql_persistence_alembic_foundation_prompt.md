# 001-02 — Configuration, PostgreSQL persistence and Alembic foundation

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
```

Оба этапа завершены. После `001-01a` подтверждён чистый bootstrap quality gate:

```text
Python 3.12.9
pip check: PASS
pytest: PASS, 0 warnings
pytest -W error: PASS
Ruff: PASS
mypy: PASS
imports: PASS
TOML: PASS
git diff --check: PASS
```

Продуктовая спецификация находится в:

```text
docs/specifications/
```

Исходные отчёты:

```text
codex/reports/001_01_project_bootstrap_environment_codex_git_report.md
codex/reports/001_01a_testclient_dependency_cleanup_report.md
```

Перед запуском текущего этапа пользователь должен выполнить первый baseline Git commit проекта.

Рекомендуемое сообщение baseline commit:

```text
chore: bootstrap Kaiten Voice Control project
```

Текущий технологический стек проекта:

```text
Python 3.12
FastAPI / ASGI
Hypercorn
Pydantic / pydantic-settings
PostgreSQL
SQLAlchemy 2.x
Alembic
asyncpg
httpx
GigaChat provider — в последующих этапах
MAX Bot API — в последующих этапах
Kaiten API — в последующих этапах
```

Production-ориентир:

```text
Linux / NetAngels
```

Local development:

```text
Windows
```

На этом этапе бизнес-сущности сервиса ещё не создаются.

---

# 1. Цель этапа

Создать устойчивый инфраструктурный фундамент для дальнейшей разработки:

1. формализовать конфигурационное ядро приложения;
2. определить development / test / production environment contract;
3. подготовить безопасную загрузку секретов и переменных окружения;
4. реализовать асинхронный PostgreSQL persistence foundation на SQLAlchemy;
5. подготовить `AsyncEngine` и `async_sessionmaker`;
6. определить единый SQLAlchemy metadata/base contract;
7. настроить Alembic для будущих миграций;
8. реализовать безопасную диагностическую проверку соединения PostgreSQL;
9. документировать локальную конфигурацию PostgreSQL;
10. сохранить текущий `/health` независимым от внешних сервисов;
11. не создавать преждевременно предметные таблицы.

Этап должен закончиться готовой инфраструктурой, на которую следующий этап сможет положить сервисную модель данных.

---

# 2. Жёсткие архитектурные границы

## 2.1. PostgreSQL — единственная целевая СУБД приложения

Не использовать и не вводить в проект:

```text
SQLite
DuckDB
MySQL
MariaDB
```

в качестве fallback, test substitute или временного persistence backend.

Если локальный PostgreSQL недоступен, это не является основанием заменять его SQLite.

---

## 2.2. Асинхронный runtime database path

Runtime persistence должен использовать:

```text
SQLAlchemy 2.x async API
+
asyncpg
```

Ожидаемый URL:

```text
postgresql+asyncpg://...
```

Не создавать параллельный sync runtime repository layer.

---

## 2.3. Бизнес-модель пока не реализовывать

На этом этапе запрещено создавать таблицы:

```text
users
kaiten_connections
max_chats
dialog_sessions
pending_commands
notification_settings
notification_history
```

и любые иные предметные таблицы.

Также не создавать фиктивные модели только ради демонстрации SQLAlchemy.

---

## 2.4. Не создавать пустую migration только ради номера этапа

Не создавать бессодержательную Alembic revision вида:

```text
00102_initial
```

с пустыми:

```python
upgrade()
downgrade()
```

только ради проверки Alembic.

Первая migration должна появиться вместе с первой реальной схемой данных на следующем этапе.

---

# 3. Предварительный аудит

Перед изменениями изучить:

```text
AGENTS.md
README.md
pyproject.toml
.env.example
src/kvc_config/
src/kvc_persistence/
src/kvc_api/
tests/
docs/specifications/
docs/architecture/
docs/operations/
.codex/config.toml
```

и оба предыдущих отчёта.

Проверить Git:

```powershell
git status --short
git log --oneline --decorate -5
git diff --check
```

## 3.1. Baseline commit

Убедиться, что в Git существует как минимум один commit, фиксирующий bootstrap проекта.

Не требовать строго определённого SHA или сообщения commit.

Если baseline commit отсутствует:

- не создавать commit самостоятельно;
- не выполнять текущую архитектурную задачу;
- создать отчёт со статусом `BLOCKED`;
- явно указать, что требуется ручной baseline commit пользователя.

Наличие самого текущего prompt-файла в `codex/prompts/` как нового/изменённого файла не считать архитектурным загрязнением рабочего дерева.

---

# 4. Инвентаризация PostgreSQL на локальной машине

До реализации проверить доступность PostgreSQL tooling без изменения системной конфигурации:

```powershell
psql --version
where.exe psql
Get-Service *postgres*
```

или эквивалентными безопасными read-only командами.

Также проверить, задана ли конфигурация БД через environment / локальный `.env`.

При диагностике:

- не печатать пароль;
- не печатать полный database URL, если он содержит credentials;
- не сохранять реальные credentials в отчёт.

## 4.1. Запрещено автоматически

Не выполнять без отдельного задания пользователя:

- установку PostgreSQL через системный installer;
- Chocolatey/Scoop/Winget install;
- создание Windows service;
- изменение системного PATH;
- создание PostgreSQL user/database с придуманными credentials;
- изменение глобального `postgresql.conf`;
- Docker installation;
- запуск PostgreSQL через Docker только ради текущего этапа.

Если PostgreSQL отсутствует, инфраструктурную реализацию продолжить, но live PostgreSQL integration smoke обозначить как не выполненный из-за отсутствия внешнего сервиса.

В таком случае итог может быть максимум:

```text
PASS WITH NOTES
```

при условии, что весь остальной quality gate проходит.

---

# 5. Конфигурационное ядро

Работать в существующем модуле:

```text
src/kvc_config/
```

Не переносить конфигурацию в `kvc_api`, `kvc_persistence` или integrations.

---

## 5.1. Environment contract

Формализовать минимум три environment:

```text
development
test
production
```

Рекомендуемый тип:

```python
Literal["development", "test", "production"]
```

или отдельный Enum, если он упрощает валидацию.

Основная переменная:

```text
KVC_APP_ENV
```

Допустимый безопасный default для локальной разработки:

```text
development
```

Не разрешать произвольные значения environment без валидации.

---

## 5.2. Минимальный Settings contract

Минимально предусмотреть:

```text
KVC_APP_ENV
KVC_LOG_LEVEL
KVC_DATABASE_URL
KVC_DATABASE_ECHO
```

Не добавлять заранее десятки настроек будущих MAX/Kaiten/GigaChat/STT интеграций, если они ещё не используются.

Существующие placeholders в `.env.example`, относящиеся к уже согласованному стеку, можно сохранить, но не строить на них runtime-код этого этапа.

---

## 5.3. Database URL

`KVC_DATABASE_URL`:

- не должен иметь hardcoded production/development пароль;
- не должен автоматически подменяться SQLite;
- должен поддерживать PostgreSQL async URL;
- должен валидироваться перед созданием persistence engine;
- должен скрываться в repr/logging.

Предпочтительно хранить URL в конфигурационной модели как секретное значение (`SecretStr` или эквивалентный безопасный механизм), если это не усложняет корректное использование SQLAlchemy.

При передаче URL в SQLAlchemy получать фактическое значение только непосредственно внутри database factory.

---

## 5.4. Отсутствующий database URL

Простой импорт приложения и запуск базового:

```text
GET /health
```

не должны требовать доступной БД.

Причина:

```text
/health = process/application liveness
```

а не database readiness.

При попытке реально создать database engine / выполнить DB check без `KVC_DATABASE_URL` должна возникать понятная контролируемая конфигурационная ошибка.

Не допускать неясных:

```text
AttributeError
NoneType error
```

---

## 5.5. `.env`

Использовать существующую систему `pydantic-settings`.

Ожидаемый приоритет:

```text
явные environment variables
        ↓
.env для local development
        ↓
безопасные defaults для несекретных параметров
```

Не хранить реальные секреты в:

```text
.env.example
pyproject.toml
AGENTS.md
README.md
docs/
tests/
source code
```

`.env` должен оставаться Git-ignored.

---

# 6. `.env.example`

Актуализировать `.env.example`.

Можно использовать шаблон вида:

```dotenv
KVC_APP_ENV=development
KVC_LOG_LEVEL=INFO
KVC_DATABASE_URL=postgresql+asyncpg://kvc_user:change_me@127.0.0.1:5432/kvc_dev
KVC_DATABASE_ECHO=false
```

Это только пример.

Не использовать реальные локальные credentials пользователя.

Добавить комментарий, что:

```text
.env.example
```

можно копировать в:

```text
.env
```

после ручного задания реальных локальных credentials.

---

# 7. Структура persistence-модуля

Работать внутри:

```text
src/kvc_persistence/
```

Сохранить физическое разделение ответственности.

Допустимая целевая структура:

```text
src/
└── kvc_persistence/
    ├── __init__.py
    ├── base.py
    ├── engine.py
    ├── session.py
    ├── health.py
    └── migrations/
        ├── env.py
        ├── script.py.mako
        └── versions/
```

Названия файлов могут быть немного скорректированы, если текущая структура проекта диктует более чистое решение.

Не создавать один огромный:

```text
database.py
```

с Base, engine, sessions, health check и Alembic logic одновременно.

---

# 8. SQLAlchemy Base / metadata

Создать единый metadata contract будущих моделей.

Использовать SQLAlchemy 2.x:

```python
DeclarativeBase
```

или эквивалентный современный API.

Рекомендуется определить naming convention минимум для:

```text
index
unique constraint
check constraint
foreign key
primary key
```

Например концептуально:

```text
ix
uq
ck
fk
pk
```

Цель — стабильные имена ограничений и предсказуемые будущие Alembic migrations.

Не добавлять таблицы в metadata на этом этапе.

---

# 9. AsyncEngine

Реализовать factory для:

```text
sqlalchemy.ext.asyncio.AsyncEngine
```

с драйвером:

```text
asyncpg
```

## Требования

- engine не должен создаваться при импорте модуля;
- database URL должен читаться из Settings;
- пароль не должен логироваться;
- production/development код должен использовать один и тот же factory contract;
- `pool_pre_ping=True` допустим и предпочтителен;
- не вводить сложную pool tuning policy без фактической необходимости;
- `echo` должен управляться конфигурацией;
- предоставить корректный lifecycle dispose для тестов/будущего application shutdown.

Не создавать глобальный сетевой connection при import-time.

---

# 10. Async session factory

Реализовать:

```text
async_sessionmaker
```

с:

```text
AsyncSession
expire_on_commit=False
```

или обоснованным эквивалентом.

Не реализовывать repository pattern до появления бизнес-модели.

Не добавлять Unit of Work abstraction только «на будущее».

Не вводить API dependency `get_db()` в `kvc_api`, если она пока нигде не используется.

---

# 11. Database health probe

Реализовать внутри persistence layer простую операцию проверки соединения PostgreSQL.

Логика:

```text
AsyncEngine
    ↓
connection
    ↓
SELECT 1
    ↓
success / controlled failure
```

Использовать SQLAlchemy:

```python
text("SELECT 1")
```

или эквивалентный корректный API.

Health probe:

- не должен раскрывать credentials;
- не должен менять данные;
- не должен создавать таблицы;
- должен корректно закрывать соединение;
- должен быть пригоден для будущего readiness endpoint/worker startup check.

На этом этапе не обязательно публиковать отдельный HTTP endpoint.

Существующий:

```text
GET /health
```

не менять на DB-dependent endpoint.

---

# 12. Alembic foundation

Настроить Alembic для будущей модели.

Предпочтительная структура:

```text
alembic.ini
src/kvc_persistence/migrations/
```

Не размещать migrations в произвольном общем каталоге, если они относятся только к persistence-модулю.

---

## 12.1. `alembic.ini`

Не хранить реальный:

```text
sqlalchemy.url
```

с credentials в version-controlled файле.

URL должен подставляться runtime из project Settings / environment.

Если Alembic требует placeholder — использовать безопасный placeholder.

---

## 12.2. `env.py`

Настроить Alembic для SQLAlchemy async PostgreSQL.

Он должен:

- использовать тот же `KVC_DATABASE_URL`;
- импортировать единый persistence metadata;
- установить:

```python
target_metadata = Base.metadata
```

или эквивалент;
- не создавать собственную вторую Base;
- поддерживать offline configuration там, где это корректно;
- поддерживать online migrations через async SQLAlchemy;
- не печатать полный URL с паролем.

Использовать официальный async-подход, совместимый с фактически установленной версией Alembic/SQLAlchemy.

---

## 12.3. Миграции

Каталог:

```text
src/kvc_persistence/migrations/versions/
```

создать, но оставить без фиктивной revision.

Допускается `.gitkeep`, если иначе пустой каталог не попадает в Git.

Первая содержательная revision будет создана на этапе сервисной модели данных.

---

# 13. Проверка Alembic без фиктивной migration

Проверить, что Alembic:

- загружает config;
- видит migration environment;
- не падает из-за импортов;
- корректно получает metadata;
- не требует hardcoded credentials.

При наличии доступной тестовой PostgreSQL database выполнить безопасные команды, не создающие предметную схему, например подходящий набор из:

```powershell
alembic heads
alembic history
alembic current
alembic check
```

Но выбирать команды по фактическому поведению установленной Alembic версии.

Не генерировать пустую migration только ради `upgrade head`.

Если `alembic check` при отсутствии revisions/таблиц имеет специфическое штатное поведение, зафиксировать его в отчёте, а не обходить фиктивной revision.

---

# 14. Live PostgreSQL smoke

## 14.1. Если PostgreSQL и credentials доступны

Выполнить реальную read-only проверку:

```text
connect
SELECT 1
disconnect
```

через созданный persistence layer.

Подтвердить:

- asyncpg path;
- SQLAlchemy AsyncEngine;
- session factory создаётся;
- connection disposal проходит;
- credentials не выводятся.

Если для теста используется отдельная test database, не создавать в ней бизнес-таблицы.

---

## 14.2. Если PostgreSQL или credentials недоступны

Не падать обратно на SQLite.

Не придумывать пароль.

Не выполнять системную установку.

В отчёте:

```text
Live PostgreSQL smoke: NOT RUN
Reason: ...
```

При этом статические/unit tests persistence foundation должны быть полностью реализованы.

---

# 15. Тестирование

Добавить unit tests минимум для следующих контрактов.

## 15.1. Settings

Проверить:

- default environment = development;
- корректная загрузка environment variables;
- допустимые environment values;
- invalid environment отклоняется;
- boolean `KVC_DATABASE_ECHO` парсится корректно;
- database URL не раскрывается через обычный repr/str settings;
- отсутствующий URL не ломает импорт приложения;
- попытка создать database infrastructure без URL даёт контролируемую ошибку.

---

## 15.2. Persistence

Без реального сетевого подключения проверить:

- единый Base/metadata существует;
- naming convention задан;
- engine factory создаёт `AsyncEngine`;
- URL использует PostgreSQL/asyncpg contract;
- session factory использует `AsyncSession`;
- `expire_on_commit` соответствует принятому контракту;
- создание engine не выполняет connection при import-time;
- dispose path корректен.

Использовать заведомо тестовый URL без реальных credentials.

Не выполнять случайный network call в unit tests.

---

## 15.3. Health probe

Проверить поведение health probe через mock/fake connection на unit-уровне так, чтобы не требовать PostgreSQL для обычного:

```text
pytest
```

Не мокать SQLAlchemy настолько глубоко, чтобы тест перестал проверять проектный контракт.

---

## 15.4. Existing tests

Существующие тесты bootstrap должны продолжать проходить.

Нельзя:

- удалять их;
- ослаблять assertions;
- скрывать warnings;
- снижать coverage threshold, если он задан.

---

# 16. Local development documentation

Создать или актуализировать краткий документ:

```text
docs/operations/postgresql_local_development.md
```

Он должен описывать:

1. что проект использует PostgreSQL, а не SQLite;
2. что runtime driver — `asyncpg`;
3. пример `KVC_DATABASE_URL`;
4. что реальные credentials хранятся только в локальном `.env` / environment;
5. как проверить наличие `psql`;
6. как выполнить database health smoke через реализованный проектный механизм;
7. что автоматическая установка PostgreSQL не является частью Codex-задач без отдельного указания;
8. что production будет на Linux/NetAngels и локальную Windows `.venv` туда не переносят.

Не превращать документ в руководство по администрированию PostgreSQL.

---

# 17. Architecture documentation

Актуализировать:

```text
docs/architecture/technology_stack.md
```

или создать небольшой отдельный документ, если это лучше соответствует текущей структуре.

Зафиксировать:

```text
PostgreSQL
SQLAlchemy 2.x async
asyncpg
Alembic
pydantic-settings
```

и принцип:

> Persistence infrastructure не содержит предметной бизнес-логики и не зависит от MAX, Kaiten, GigaChat или STT.

---

# 18. Dependency policy

Перед добавлением новых Python-пакетов проверить, действительно ли они необходимы.

Текущий bootstrap уже содержит:

```text
sqlalchemy
alembic
asyncpg
pydantic
pydantic-settings
```

Не добавлять альтернативы этим библиотекам.

Не добавлять:

```text
psycopg
psycopg2
databases
SQLModel
Tortoise ORM
peewee
```

без отдельной архитектурной необходимости.

Если дополнительных runtime dependencies не требуется — не добавлять их.

После любых dependency changes:

```powershell
python -m pip install -e ".[dev]"
python -m pip check
python -m pip freeze > requirements.lock.txt
```

Если dependencies не менялись, бессмысленно не переписывать lock-файл только ради timestamp/ordering noise.

---

# 19. Что не входит в этап

Не реализовывать:

- таблицы пользователей;
- Kaiten connections;
- encrypted token storage;
- MAX chats;
- dialog sessions;
- PendingCommand;
- notification settings/history;
- repository/service слой бизнес-сущностей;
- Kaiten API adapter;
- MAX API adapter;
- GigaChat provider;
- STT provider implementation;
- webhook endpoints;
- scheduler;
- polling Kaiten;
- Redis;
- Celery;
- Docker;
- CI/CD;
- NetAngels deployment;
- authentication/authorization;
- коммерческий доступ;
- тарифы.

Шифрование Kaiten token будет реализовываться вместе с моделью `kaiten_connections`, а не как абстрактная инфраструктура без данных.

---

# 20. Quality gate

После изменений выполнить из активированной `.venv`:

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

Обязательное ожидание:

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

Дополнительно:

```powershell
python -c "import kvc_config, kvc_persistence; print('config and persistence imports ok')"
```

Проверить, что обычный импорт:

```text
kvc_api
```

не инициирует database connection.

Проверить TOML:

```powershell
python -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); tomllib.load(open('.codex/config.toml','rb')); print('toml ok')"
```

Git:

```powershell
git diff --check
git status --short
```

---

# 21. Database-specific quality gate

При наличии рабочей PostgreSQL configuration дополнительно выполнить:

```text
project database health probe
```

и подходящие безопасные Alembic diagnostics.

Ожидается:

```text
PostgreSQL connection: PASS
SELECT 1: PASS
AsyncEngine dispose: PASS
Alembic environment load: PASS
```

Если PostgreSQL недоступен:

```text
PostgreSQL live smoke: NOT RUN
```

Это должно быть явно отражено в итоговом статусе.

---

# 22. Проверка секретов

Перед завершением выполнить поиск потенциальных credentials минимум в version-controlled файлах:

```text
src/
tests/
docs/
.codex/
AGENTS.md
README.md
pyproject.toml
.env.example
alembic.ini
```

Не выводить найденные реальные секреты в отчёт.

Проверить:

```powershell
git check-ignore -v -- .env .venv
```

и убедиться, что `.env` и `.venv/` игнорируются.

---

# 23. Git

Codex:

- не выполняет commit;
- не выполняет push;
- не создаёт remote;
- не меняет global Git config;
- не изменяет user.name/user.email.

Staging не выполнять, кроме диагностической необходимости.

Все изменения оставить пользователю для ручной приёмки.

---

# 24. Отчёт

Создать:

```text
codex/reports/001_02_configuration_postgresql_persistence_alembic_foundation_report.md
```

Отчёт должен содержать следующие разделы.

## 24.1. Baseline

- baseline commit SHA и message;
- исходный Git status;
- Python/package versions;
- PostgreSQL tooling inventory;
- наличие/отсутствие доступной local database configuration.

Не публиковать secrets.

## 24.2. Configuration contract

Показать итоговый список:

```text
KVC_APP_ENV
KVC_LOG_LEVEL
KVC_DATABASE_URL
KVC_DATABASE_ECHO
```

с типами/defaults и правилами обязательности.

## 24.3. Persistence structure

Показать фактическое дерево:

```text
src/kvc_persistence/
```

и назначение файлов.

## 24.4. SQLAlchemy contract

Зафиксировать:

- Base;
- metadata naming convention;
- AsyncEngine factory;
- asyncpg;
- async_sessionmaker;
- disposal lifecycle.

## 24.5. Alembic

Показать:

- расположение `alembic.ini`;
- migration directory;
- откуда берётся URL;
- target metadata;
- результат diagnostic commands;
- подтвердить отсутствие фиктивной empty migration.

## 24.6. PostgreSQL live smoke

Один из вариантов:

```text
PASS
```

с фактическими командами/результатами без credentials;

либо:

```text
NOT RUN
```

с точной причиной.

## 24.7. Tests

Привести результаты:

```text
pytest
pytest -W error
ruff
mypy
pip check
imports
TOML
git diff --check
```

## 24.8. Security

Подтвердить:

- реальные database credentials не закоммичены;
- `.env` игнорируется;
- database URL не выводится с паролем;
- Alembic config не содержит real credentials.

## 24.9. Changed files

Перечислить созданные/изменённые файлы.

## 24.10. Deviations

Описать все отклонения от задания.

## 24.11. Final status

Использовать:

```text
PASS
PASS WITH NOTES
BLOCKED
FAIL
```

### `PASS`

Допустим, если:

- весь quality gate чистый;
- PostgreSQL live smoke выполнен и PASS;
- Alembic environment валиден;
- secrets отсутствуют;
- архитектурные границы соблюдены.

### `PASS WITH NOTES`

Допустим, если:

- код и automated quality gates полностью PASS;
- PostgreSQL live smoke не выполнен исключительно из-за отсутствия локального PostgreSQL/credentials;
- SQLite fallback не вводился;
- все остальные требования выполнены.

### `BLOCKED`

Использовать, если:

- отсутствует baseline commit;
- невозможно безопасно продолжить без изменения внешней/system configuration;
- обнаружено противоречие, которое нельзя разрешить в рамках задания.

### `FAIL`

Использовать при нарушении quality gate или архитектурных инвариантов.

---

# 25. Критерий завершения этапа

Целевой результат:

```text
kvc_config
    ↓
validated environment contract
    ↓
secure PostgreSQL URL handling
    ↓
kvc_persistence
    ├── Base / metadata
    ├── AsyncEngine
    ├── async_sessionmaker
    └── DB health probe
    ↓
Alembic environment
    ↓
готовность к первой реальной модели данных
```

При этом:

```text
0 предметных таблиц
0 фиктивных migrations
0 SQLite fallback
0 secrets в Git
0 warnings
```

Следующий этап после принятия `001-02` должен быть посвящён **проектированию и реализации собственной сервисной модели данных MVP** на уже готовом PostgreSQL/Alembic foundation.

Реализация этой модели данных в текущий этап не входит.
