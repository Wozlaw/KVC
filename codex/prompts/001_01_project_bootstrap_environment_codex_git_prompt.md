# 001-01 — Инициализация проекта, Python-среды, Codex и Git

## Роль

Ты работаешь как ведущий Python-инженер и инженер по инфраструктуре проекта **Kaiten Voice Control**.

Нужно выполнить первый инфраструктурный этап проекта: создать чистый, модульный и воспроизводимый каркас репозитория, настроить Python-окружение, базовые зависимости, проектную конфигурацию Codex и Git.

На этом этапе **не реализовывать бизнес-функции Kaiten Voice Control**, кроме минимального технического кода, необходимого для проверки корректности каркаса и запуска FastAPI.

---

## 1. Исходный контекст проекта

Проект: **Kaiten Voice Control**.

Назначение проекта: диалоговый клиент Kaiten в мессенджере MAX с поддержкой текста, голоса, прямых команд, контекста диалога, вложений, AI-summary и фонового контроля сроков.

Если в рабочем каталоге присутствует файл исходной спецификации вида:

```text
Kaiten Voice Control — спецификация MVP v0.1.md
```

считать его исходным продуктовым контрактом. Не редактировать его содержимое в рамках этой задачи. Переместить или скопировать его в каталог документации только если это можно сделать без потери исходного файла и без нарушения уже существующей структуры репозитория.

Если спецификации в рабочем каталоге нет — не пытаться восстанавливать её по памяти и не генерировать новую версию. Просто отметить это в отчёте.

### Зафиксированный технологический стек

Основные решения:

- Python 3.12;
- FastAPI;
- ASGI;
- production-размещение — NetAngels;
- локальная среда — Windows, production — Linux;
- MAX Bot API;
- production transport MAX — Webhook;
- Long Polling допустим только как вспомогательный локальный режим разработки;
- PostgreSQL;
- SQLAlchemy 2.x;
- Alembic;
- Pydantic 2;
- pydantic-settings;
- HTTP-клиенты — `httpx`;
- GigaChat — основной LLM-провайдер;
- официальный Python SDK GigaChat — `gigachat`;
- GigaChat должен быть скрыт за собственной абстракцией провайдера;
- STT должен быть скрыт за `SpeechToTextProvider`;
- SaluteSpeech рассматривается как предпочтительный STT-провайдер только при наличии действующего доступа;
- интеграция с Kaiten выполняется через собственный адаптер;
- интеграция с MAX выполняется через собственный адаптер;
- контроль сроков — отдельный Python background worker с polling Kaiten API;
- Redis в MVP не требуется;
- Celery в MVP не требуется;
- Docker не является обязательной частью первого этапа.

### Важные архитектурные инварианты

1. Kaiten остаётся единственным источником состояния карточек, досок, комментариев, сроков и вложений.
2. Собственная БД хранит только сервисное состояние приложения.
3. Любое изменение данных Kaiten выполняется только вследствие явной команды пользователя.
4. Фоновый worker имеет право читать Kaiten и отправлять уведомления, но не изменять Kaiten.
5. LLM не выполняет бизнес-операции напрямую. Она только интерпретирует намерение/аргументы либо формирует summary.
6. Бизнес-ядро не должно зависеть напрямую от SDK GigaChat, MAX, Kaiten или конкретного STT-провайдера.
7. Секреты никогда не должны попадать в Git.

---

# 2. Цель этапа

После завершения задачи репозиторий должен иметь:

1. логичную модульную файловую структуру;
2. рабочую корневую виртуальную среду `.venv`;
3. установленные runtime- и development-зависимости;
4. валидный `pyproject.toml`;
5. минимальный запускаемый FastAPI application shell;
6. отдельный каркас background worker;
7. проектную конфигурацию Codex;
8. `AGENTS.md` с правилами проекта;
9. корректно настроенный Git;
10. `.gitignore`, `.gitattributes`, `.editorconfig`;
11. `.env.example` без реальных секретов;
12. минимальный набор тестов и quality gates;
13. документацию по запуску разработки;
14. отчёт о выполнении в `codex/reports`.

---

# 3. Сначала обследовать рабочий каталог

Перед изменениями:

1. определить текущий каталог проекта;
2. вывести существующее дерево файлов разумной глубины;
3. проверить наличие `.git`;
4. проверить наличие `pyproject.toml`, `requirements*.txt`, существующей `.venv`;
5. проверить доступные версии Python;
6. проверить наличие существующих пользовательских файлов;
7. не удалять и не перезаписывать существующие данные без необходимости;
8. если репозиторий уже частично инициализирован — адаптировать решение к текущему состоянию вместо разрушительного пересоздания.

В отчёте явно зафиксировать исходное состояние.

---

# 4. Требуемая файловая архитектура

Не складывать все исходники в одну папку и не создавать плоскую структуру из десятков `.py`-файлов.

Каждый самостоятельный слой и интеграция должны находиться в собственном каталоге/пакете.

Целевая структура верхнего уровня:

```text
kaiten-voice-control/
├── .codex/
│   └── config.toml
├── codex/
│   ├── prompts/
│   └── reports/
├── docs/
│   ├── specifications/
│   ├── architecture/
│   └── operations/
├── scripts/
├── src/
│   ├── kvc_api/
│   ├── kvc_worker/
│   ├── kvc_domain/
│   ├── kvc_application/
│   ├── kvc_persistence/
│   ├── kvc_notifications/
│   ├── kvc_config/
│   └── kvc_integrations/
│       ├── kaiten/
│       ├── max/
│       ├── gigachat/
│       └── stt/
│           └── salutespeech/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── smoke/
├── .editorconfig
├── .env.example
├── .gitattributes
├── .gitignore
├── AGENTS.md
├── pyproject.toml
└── README.md
```

Допускаются небольшие технически обоснованные отклонения, если они улучшают Python packaging, но запрещено превращать проект в плоский набор файлов либо смешивать API, домен, persistence, интеграции и worker в одном каталоге.

### Назначение пакетов

#### `kvc_api`

ASGI/FastAPI transport layer.

На этом этапе допускается только:

- создание приложения;
- health endpoint;
- подключение базовой конфигурации;
- никаких Kaiten-команд.

#### `kvc_worker`

Точка входа фонового процесса.

На этом этапе:

- только каркас;
- без polling Kaiten;
- без scheduler business logic.

#### `kvc_domain`

Чистые доменные модели и контракты.

На этом этапе оставить минимальный пакет без реализации предметной модели.

#### `kvc_application`

Application/use-case layer.

Не реализовывать реальные use cases.

#### `kvc_persistence`

Будущий SQLAlchemy/PostgreSQL persistence layer.

Не проектировать таблицы и миграции в рамках этой задачи.

#### `kvc_notifications`

Будущий notification policy/background logic.

Не реализовывать polling.

#### `kvc_config`

Конфигурация приложения через `pydantic-settings`.

#### `kvc_integrations/kaiten`

Будущий Kaiten adapter.

#### `kvc_integrations/max`

Будущий MAX adapter.

#### `kvc_integrations/gigachat`

Будущий GigaChat provider.

#### `kvc_integrations/stt`

Абстракция speech-to-text.

`salutespeech` должен быть отдельным вложенным адаптером, а не частью application/domain кода.

---

# 5. Python и виртуальная среда

Целевая версия:

```text
Python 3.12.x
```

Создать **одну корневую виртуальную среду**:

```text
.venv
```

На Windows предпочтительный порядок:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
```

Если `py -3.12` недоступен, определить корректный путь к Python 3.12 и использовать его.

Не создавать отдельные virtualenv для каждого внутреннего модуля.

После установки вывести фактические версии:

```text
python --version
pip --version
```

---

# 6. Python packaging

Создать корневой `pyproject.toml`.

Использовать стандартный современный Python packaging с обнаружением пакетов из `src/`.

Проект должен устанавливаться в editable-режиме:

```powershell
python -m pip install -e ".[dev]"
```

Не использовать Poetry, Pipenv, Conda или отдельный package manager без необходимости.

---

# 7. Runtime dependencies

В runtime dependencies включить как минимум:

```text
fastapi
hypercorn
pydantic>=2
pydantic-settings
httpx
sqlalchemy>=2
alembic
asyncpg
cryptography
python-multipart
gigachat
```

Обоснование:

- `fastapi` — API/webhook слой;
- `hypercorn` — ASGI server и совместимость с целевым NetAngels-размещением;
- `pydantic`, `pydantic-settings` — контракты и конфигурация;
- `httpx` — MAX/Kaiten/STT HTTP adapters;
- `sqlalchemy`, `alembic`, `asyncpg` — будущий PostgreSQL persistence;
- `cryptography` — будущая защита Kaiten token/секретов;
- `python-multipart` — будущая работа с файлами/вложениями;
- `gigachat` — официальный Python SDK основного LLM-провайдера.

Не добавлять LangChain, LangGraph, Celery, Redis, APScheduler и другие тяжёлые зависимости без фактической необходимости текущего этапа.

Для MAX не устанавливать случайные неофициальные Python SDK. На данном этапе достаточно `httpx` и собственного adapter boundary.

Для SaluteSpeech не добавлять обязательную provider-specific библиотеку, если она не нужна: STT adapter должен иметь возможность работать поверх собственного HTTP-клиента и быть заменяемым.

---

# 8. Development dependencies

В optional group `dev` включить как минимум:

```text
pytest
pytest-asyncio
pytest-cov
ruff
mypy
```

При необходимости добавить только минимальные typing stubs.

После установки выполнить:

```powershell
python -m pip check
```

Сохранить воспроизводимый снимок реально установленного окружения в:

```text
requirements.lock.txt
```

через эквивалент:

```powershell
python -m pip freeze
```

`pyproject.toml` остаётся первичным декларативным источником зависимостей, lock-файл — снимком среды первого bootstrap.

---

# 9. Минимальный application shell

Создать минимальный FastAPI application shell.

Endpoint:

```text
GET /health
```

Ожидаемый ответ должен быть простым и стабильным, например:

```json
{
  "status": "ok",
  "service": "kaiten-voice-control"
}
```

Не подключать:

- Kaiten;
- MAX webhook;
- GigaChat;
- PostgreSQL;
- SaluteSpeech;
- notification polling.

Цель endpoint — проверить корректность packaging/import/ASGI.

Создать smoke test для `/health`.

---

# 10. Конфигурация приложения

Создать минимальный конфигурационный слой в `kvc_config` на основе `pydantic-settings`.

Не требовать реальных секретов для запуска `/health`.

Создать `.env.example` с пустыми/демонстрационными значениями как минимум для:

```text
KVC_ENV
KVC_LOG_LEVEL
KVC_DATABASE_URL
KVC_MAX_BOT_TOKEN
KVC_MAX_WEBHOOK_SECRET
KVC_KAITEN_API_TOKEN
KVC_GIGACHAT_CREDENTIALS
KVC_GIGACHAT_MODEL
KVC_STT_PROVIDER
KVC_SALUTESPEECH_AUTH_KEY
KVC_TOKEN_ENCRYPTION_KEY
```

Рекомендуемое значение модели по умолчанию в example/config:

```text
GigaChat-Pro
```

Никаких реальных токенов, API keys или паролей в репозитории.

`.env` должен быть в `.gitignore`.

---

# 11. Проектная конфигурация Codex

Создать два уровня проектной настройки:

```text
AGENTS.md
.codex/config.toml
```

## 11.1. `AGENTS.md`

Файл должен быть кратким, но содержать обязательные правила работы агента в данном репозитории.

Зафиксировать в нём:

### Архитектурные правила

- соблюдать границы модулей;
- не переносить интеграционный код в domain/application;
- Kaiten является source of truth для project state;
- не создавать локальную копию содержимого Kaiten без отдельного архитектурного решения;
- LLM не исполняет команды напрямую;
- любое изменение Kaiten — только по явной команде пользователя;
- background worker не изменяет Kaiten;
- provider-specific код должен находиться в integration adapters;
- не связывать application layer с GigaChat/SaluteSpeech/MAX/Kaiten SDK напрямую.

### Правила разработки

Перед завершением любой implementation-задачи выполнять, если применимо:

```text
pytest
ruff format --check
ruff check
mypy
pip check
git diff --check
```

### Правила секретов

- никогда не помещать секреты в tracked files;
- не выводить секреты в отчёты;
- не добавлять `.env` в Git;
- использовать только `.env.example`.

### Правила отчётов

Все отчёты Codex хранить в:

```text
codex/reports/
```

Каждый отчёт должен содержать:

- что было сделано;
- список изменённых/созданных файлов;
- принятые технические решения;
- выполненные проверки;
- фактические результаты команд;
- замечания/риски;
- статус этапа.

### Правила работы со спецификациями

Материалы из `docs/specifications/` считать проектными требованиями.

Не менять продуктовые требования молча. Если код требует пересмотра зафиксированного контракта — указать противоречие в отчёте, а не принимать новое продуктовое решение самостоятельно.

## 11.2. `.codex/config.toml`

Создать project-scoped Codex configuration.

Использовать только официально поддерживаемые project-scoped параметры.

Базовая политика:

```toml
#:schema https://developers.openai.com/codex/config-schema.json

approval_policy = "on-request"
sandbox_mode = "workspace-write"
project_doc_max_bytes = 65536

[sandbox_workspace_write]
network_access = true
```

Если установленная версия Codex не поддерживает какой-либо параметр, не придумывать замену: проверить актуальную официальную документацию Codex, использовать действующий эквивалент и подробно зафиксировать отличие в отчёте.

Не помещать в project-scoped config:

- API keys;
- auth credentials;
- GigaChat credentials;
- MAX token;
- Kaiten token;
- PostgreSQL password.

Не менять пользовательскую глобальную конфигурацию `~/.codex/config.toml` без отдельного указания пользователя.

---

# 12. Git

Если Git-репозиторий отсутствует:

```text
git init -b main
```

Если он уже существует — не переинициализировать его разрушительным образом и сохранить текущую историю/ветки.

Не создавать remote автоматически.

Не менять глобальные `user.name`, `user.email`, credential helper или другие пользовательские Git-настройки.

В рамках задачи **не выполнять commit автоматически**. Подготовить рабочее дерево к ручной проверке пользователя.

## `.gitignore`

Включить как минимум:

```text
.venv/
.env
.env.*
!.env.example
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
build/
dist/
*.egg-info/
*.log
logs/
.vscode/
.idea/
.DS_Store
Thumbs.db
.codex-log/
```

Добавить разумные временные/runtime-файлы, если они появились при инициализации.

Не игнорировать:

```text
AGENTS.md
.codex/config.toml
codex/reports/
docs/
requirements.lock.txt
```

## `.gitattributes`

Настроить стабильную нормализацию line endings для кроссплатформенной разработки Windows/Linux.

Не менять глобальный `core.autocrlf` пользователя.

## `.editorconfig`

Зафиксировать как минимум:

- UTF-8;
- final newline;
- удаление trailing whitespace;
- 4 пробела для Python;
- LF как репозиторный line ending, если это не конфликтует с существующим проектом.

---

# 13. README

Создать корневой `README.md`.

На данном этапе он должен кратко содержать:

1. назначение проекта;
2. текущий статус — infrastructure bootstrap;
3. используемый стек;
4. структуру основных модулей;
5. создание/активацию `.venv` на Windows;
6. установку проекта;
7. команды quality gates;
8. команду локального запуска ASGI;
9. информацию, что production предполагается на NetAngels;
10. указание, что реальные секреты задаются через environment variables и не хранятся в Git.

Не писать подробную пользовательскую документацию функций, которые ещё не реализованы.

---

# 14. Документирование технологического стека

Создать:

```text
docs/architecture/technology_stack.md
```

Зафиксировать там принятый технологический стек и границы компонентов.

Особо отметить:

- MAX Webhook — production transport;
- Long Polling — только вспомогательный development transport;
- GigaChat — основной LLM provider;
- `gigachat` SDK изолируется adapter layer;
- STT — через заменяемый `SpeechToTextProvider`;
- SaluteSpeech adapter допускается при наличии действующего доступа;
- PostgreSQL — service database;
- background worker — отдельная точка запуска;
- Redis/Celery не входят в MVP bootstrap;
- Docker не требуется на первом этапе.

---

# 15. Минимальные тесты

Добавить smoke/unit tests как минимум для:

1. импорта всех созданных верхнеуровневых пакетов;
2. загрузки базовых settings без реальных секретов;
3. FastAPI `GET /health`;
4. гарантии, что application shell стартует без подключения внешних API.

Не создавать фиктивные интеграционные тесты, которые на самом деле ничего не проверяют.

---

# 16. Quality configuration

Настроить в `pyproject.toml` минимальные конфигурации:

- Ruff;
- mypy;
- pytest;
- coverage.

Не вводить чрезмерно сложные правила linting на старте.

Для нового собственного кода ожидается строгий, типизированный стиль.

---

# 17. Проверки приёмки

После реализации выполнить реальные команды из созданной `.venv`.

Минимальный gate:

```text
python --version
python -m pip --version
python -m pip check
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m mypy src
```

Дополнительно проверить импорты ключевых runtime dependencies и собственных пакетов.

Примерный смысл проверки:

```text
import fastapi
import hypercorn
import sqlalchemy
import alembic
import httpx
import pydantic
import gigachat

import kvc_api
import kvc_worker
import kvc_domain
import kvc_application
import kvc_persistence
import kvc_notifications
import kvc_config
import kvc_integrations
```

Проверить FastAPI health endpoint автоматическим тестом.

Git gate:

```text
git status --short
git diff --check
```

Также:

- проверить, что `.env` не tracked;
- проверить, что `.venv` не tracked;
- проверить, что `.codex/config.toml` tracked/не игнорируется;
- проверить, что `AGENTS.md` присутствует;
- проверить, что `requirements.lock.txt` создан;
- проверить, что `pyproject.toml` является валидным TOML;
- проверить, что `.codex/config.toml` является валидным TOML.

Если какая-либо проверка не проходит — исправить причину до формирования итогового отчёта либо явно обозначить блокирующую внешнюю причину.

---

# 18. Что запрещено делать в этой задаче

Не реализовывать:

- подключение к реальному Kaiten;
- подключение к реальному MAX;
- регистрацию MAX webhook;
- GigaChat prompts/function calling;
- STT распознавание;
- SQLAlchemy entities;
- Alembic migrations;
- таблицы БД;
- user authentication;
- карточки;
- комментарии;
- сроки;
- attachments;
- summary;
- pending commands;
- notification polling;
- scheduler;
- Redis;
- Celery;
- Docker deployment;
- NetAngels deployment.

Это только foundation/bootstrap этап.

---

# 19. Итоговый отчёт

Создать:

```text
codex/reports/001_01_project_bootstrap_environment_codex_git_report.md
```

Отчёт должен содержать разделы:

```text
# 001-01 — Project bootstrap report

## 1. Исходное состояние
## 2. Созданная структура проекта
## 3. Python и virtualenv
## 4. Установленные зависимости
## 5. Packaging
## 6. Application shell
## 7. Конфигурация Codex
## 8. Git configuration
## 9. Созданные/изменённые файлы
## 10. Проверки и фактические результаты
## 11. Отклонения от задания
## 12. Риски и замечания
## 13. Итоговый статус
```

В разделе зависимостей привести **фактически установленные версии** ключевых пакетов.

В разделе структуры показать фактическое дерево репозитория после реализации.

В разделе проверок не писать только `PASS`; привести команды и их фактические результаты/сводку.

Финальный статус использовать один из:

```text
PASS — READY FOR NEXT STAGE
PASS WITH NOTES
BLOCKED
FAIL
```

---

# 20. Критерий завершения

Задача считается выполненной только если:

- проект физически разделён по пакетам/каталогам;
- Python 3.12 `.venv` работает;
- зависимости установлены без конфликтов;
- проект устанавливается editable;
- `GET /health` проходит smoke test;
- pytest проходит;
- Ruff проходит;
- mypy проходит;
- pip check проходит;
- Git и ignore rules корректны;
- Codex project configuration создана;
- `AGENTS.md` создан;
- секреты отсутствуют в tracked files;
- отчёт `001_01_project_bootstrap_environment_codex_git_report.md` создан.

Не переходить к реализации интеграций или бизнес-логики после выполнения этого gate.
