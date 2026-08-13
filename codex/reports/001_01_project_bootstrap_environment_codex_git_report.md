# 001-01 — Project bootstrap report

## 1. Исходное состояние

- Рабочий каталог: `D:\Prog\KVControl`.
- На старте в каталоге был только `codex/prompts/001_01_project_bootstrap_environment_codex_git_prompt.md` и пустой каталог `codex/reports/`.
- `.git` отсутствовал: `git status --short` вернул `fatal: not a git repository`.
- `pyproject.toml` отсутствовал.
- `requirements*.txt` отсутствовали.
- `.venv` отсутствовала.
- Спецификация `Kaiten Voice Control*` в корне каталога не найдена, поэтому в `docs/specifications/` ничего не переносилось и не генерировалось.
- `py -0p` показал доступные launcher-версии:
  - `Python 3.14`: `C:\Python314\python.exe`;
  - `Python 3.10`: `C:\Python310\python.exe`.
- Отдельный Python 3.12 найден по пути `C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe`, версия `Python 3.12.9`.
- Существующих пользовательских файлов за пределами `codex/prompts` не было.

## 2. Созданная структура проекта

Фактическое дерево без `.git`, `.venv` и cache-каталогов:

```text
D:\Prog\KVControl
├── .codex
│   └── config.toml
├── codex
│   ├── prompts
│   │   └── 001_01_project_bootstrap_environment_codex_git_prompt.md
│   └── reports
│       └── 001_01_project_bootstrap_environment_codex_git_report.md
├── docs
│   ├── architecture
│   │   └── technology_stack.md
│   ├── operations
│   └── specifications
├── scripts
├── src
│   ├── kvc_api
│   │   ├── __init__.py
│   │   └── main.py
│   ├── kvc_application
│   │   └── __init__.py
│   ├── kvc_config
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── kvc_domain
│   │   └── __init__.py
│   ├── kvc_integrations
│   │   ├── __init__.py
│   │   ├── gigachat
│   │   │   └── __init__.py
│   │   ├── kaiten
│   │   │   └── __init__.py
│   │   ├── max
│   │   │   └── __init__.py
│   │   └── stt
│   │       ├── __init__.py
│   │       └── salutespeech
│   ├── kvc_notifications
│   │   └── __init__.py
│   ├── kvc_persistence
│   │   └── __init__.py
│   └── kvc_worker
│       ├── __init__.py
│       └── __main__.py
├── tests
│   ├── integration
│   ├── smoke
│   │   └── test_health.py
│   └── unit
│       ├── test_imports.py
│       └── test_settings.py
├── .editorconfig
├── .env.example
├── .gitattributes
├── .gitignore
├── AGENTS.md
├── pyproject.toml
├── README.md
└── requirements.lock.txt
```

Служебные файлы, появившиеся при проверках и установке, игнорируются Git: `.venv/`, `.coverage`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.egg-info/`, `__pycache__/`.

## 3. Python и virtualenv

- Создана одна корневая виртуальная среда: `.venv`.
- Так как `py -3.12` через Python Launcher недоступен, использован найденный абсолютный путь к Python 3.12.
- Фактические версии:
  - `.venv\Scripts\python.exe --version`: `Python 3.12.9`;
  - `.venv\Scripts\python.exe -m pip --version`: `pip 26.2.1 from D:\Prog\KVControl\.venv\Lib\site-packages\pip (python 3.12)`.
- Базовые packaging tools обновлены командой:

```text
.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
```

Результат: `Successfully installed packaging-26.3 pip-26.2.1 setuptools-84.0.0 wheel-0.48.0`.

## 4. Установленные зависимости

Проект установлен в editable-режиме:

```text
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Результат: `Successfully built kaiten-voice-control`, `Successfully installed ... kaiten-voice-control-0.1.0`.

Фактические версии ключевых пакетов:

```text
fastapi==0.141.1
hypercorn==0.18.0
pydantic==2.13.4
pydantic-settings==2.15.0
httpx==0.28.1
sqlalchemy==2.0.52
alembic==1.19.1
asyncpg==0.31.0
cryptography==50.0.0
python-multipart==0.0.32
gigachat==0.2.3
pytest==9.1.1
pytest-asyncio==1.4.0
pytest-cov==7.1.0
ruff==0.16.2
mypy==2.3.0
```

Снимок окружения сохранен в `requirements.lock.txt` командой:

```text
.venv\Scripts\python.exe -m pip freeze > requirements.lock.txt
```

## 5. Packaging

- Создан `pyproject.toml`.
- Используется `setuptools.build_meta`.
- Пакеты обнаруживаются из `src/` через `[tool.setuptools.packages.find]`.
- `requires-python = ">=3.12,<3.13"`.
- Runtime dependencies заданы в `[project.dependencies]`.
- Dev dependencies заданы в `[project.optional-dependencies].dev`.
- Добавлен script entrypoint `kvc-worker = "kvc_worker.__main__:main"`.
- Настроены `pytest`, coverage, Ruff и mypy.
- `pyproject.toml` проверен как валидный TOML.

## 6. Application shell

- Создан минимальный FastAPI shell в `src/kvc_api/main.py`.
- Добавлен endpoint:

```text
GET /health
```

Ответ:

```json
{"status": "ok", "service": "kaiten-voice-control"}
```

- Создан no-op worker entrypoint `src/kvc_worker/__main__.py`.
- Внешние подключения к Kaiten, MAX, GigaChat, PostgreSQL и STT не реализовывались.
- Добавлен конфигурационный слой `kvc_config` на `pydantic-settings`.
- Реальные секреты для `/health` не требуются.
- Добавлена заменяемая STT-граница `SpeechToTextProvider` без provider-specific логики.

## 7. Конфигурация Codex

- Создан `AGENTS.md` с архитектурными правилами, правилами секретов, quality gates, отчетами и работой со спецификациями.
- Создан `.codex/config.toml`:

```toml
#:schema https://developers.openai.com/codex/config-schema.json

approval_policy = "on-request"
sandbox_mode = "workspace-write"
project_doc_max_bytes = 65536

[sandbox_workspace_write]
network_access = true
```

- `.codex/config.toml` проверен как валидный TOML.
- Секреты в project-scoped Codex config не добавлялись.
- Глобальная конфигурация `~/.codex/config.toml` не изменялась.
- `codex --version` в PowerShell заблокирован локальной Execution Policy для `codex.ps1`.
- `codex.cmd --version` успешно вернул: `codex-cli 0.147.0`.

## 8. Git configuration

- Git-репозиторий отсутствовал и был создан командой:

```text
git init -b main
```

Результат: `Initialized empty Git repository in D:/Prog/KVControl/.git/`.

- Remote не создавался.
- Commit не выполнялся.
- Глобальные настройки Git не изменялись.
- Создан `.gitignore` с правилами для `.venv/`, `.env`, cache/build/runtime файлов и IDE файлов.
- Создан `.gitattributes` для LF-нормализации и binary-исключений.
- Создан `.editorconfig` с UTF-8, final newline, trim trailing whitespace, LF и 4 пробелами для Python.
- Проверка ignore:

```text
git check-ignore -v -- .env .venv .codex/config.toml AGENTS.md requirements.lock.txt
```

Результат:

```text
.gitignore:2:.env    .env
.gitignore:1:.venv/  .venv
```

`AGENTS.md`, `.codex/config.toml` и `requirements.lock.txt` не игнорируются.

## 9. Созданные/изменённые файлы

Созданы:

```text
.codex/config.toml
.editorconfig
.env.example
.gitattributes
.gitignore
AGENTS.md
README.md
docs/architecture/technology_stack.md
pyproject.toml
requirements.lock.txt
src/kvc_api/__init__.py
src/kvc_api/main.py
src/kvc_application/__init__.py
src/kvc_config/__init__.py
src/kvc_config/settings.py
src/kvc_domain/__init__.py
src/kvc_integrations/__init__.py
src/kvc_integrations/gigachat/__init__.py
src/kvc_integrations/kaiten/__init__.py
src/kvc_integrations/max/__init__.py
src/kvc_integrations/stt/__init__.py
src/kvc_integrations/stt/salutespeech/__init__.py
src/kvc_notifications/__init__.py
src/kvc_persistence/__init__.py
src/kvc_worker/__init__.py
src/kvc_worker/__main__.py
tests/smoke/test_health.py
tests/unit/test_imports.py
tests/unit/test_settings.py
codex/reports/001_01_project_bootstrap_environment_codex_git_report.md
```

Созданы каталоги:

```text
docs/specifications
docs/architecture
docs/operations
scripts
tests/integration
```

Существующий файл промпта не изменялся:

```text
codex/prompts/001_01_project_bootstrap_environment_codex_git_prompt.md
```

## 10. Проверки и фактические результаты

```text
.venv\Scripts\python.exe --version
Python 3.12.9
```

```text
.venv\Scripts\python.exe -m pip --version
pip 26.2.1 from D:\Prog\KVControl\.venv\Lib\site-packages\pip (python 3.12)
```

```text
.venv\Scripts\python.exe -m pip check
No broken requirements found.
```

```text
.venv\Scripts\python.exe -m pytest
collected 4 items
tests\smoke\test_health.py .. [ 50%]
tests\unit\test_imports.py .  [ 75%]
tests\unit\test_settings.py . [100%]
4 passed, 1 warning in 1.14s
coverage TOTAL: 90%
```

Предупреждение pytest:

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

```text
.venv\Scripts\python.exe -m ruff format --check .
23 files already formatted
```

```text
.venv\Scripts\python.exe -m ruff check .
All checks passed!
```

```text
.venv\Scripts\python.exe -m mypy src
Success: no issues found in 16 source files
```

```text
.venv\Scripts\python.exe -c "import fastapi, hypercorn, sqlalchemy, alembic, httpx, pydantic, gigachat; import kvc_api, kvc_worker, kvc_domain, kvc_application, kvc_persistence, kvc_notifications, kvc_config, kvc_integrations; print('runtime and project imports ok')"
runtime and project imports ok
```

```text
.venv\Scripts\python.exe -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); tomllib.load(open('.codex/config.toml','rb')); print('toml ok')"
toml ok
```

```text
git diff --check
```

Результат: без вывода, exit code 0.

```text
git status --short
?? .codex/
?? .editorconfig
?? .env.example
?? .gitattributes
?? .gitignore
?? AGENTS.md
?? README.md
?? codex/
?? docs/
?? pyproject.toml
?? requirements.lock.txt
?? src/
?? tests/
```

```text
git ls-files -- .env .venv .codex/config.toml AGENTS.md requirements.lock.txt
```

Результат: без вывода, так как commit/staging не выполнялись.

## 11. Отклонения от задания

- `py -3.12` недоступен через Python Launcher. Использован найденный локальный Python 3.12.9 по абсолютному пути.
- Для запуска Python 3.12 и `.venv` в текущей sandbox-конфигурации требовалось выполнение вне sandbox, потому что базовый интерпретатор находится вне workspace.
- PowerShell shim `codex.ps1` блокируется Execution Policy; версия Codex получена через `codex.cmd`.
- Исходная продуктовая спецификация в корне не найдена, поэтому перенос в `docs/specifications/` не выполнялся.

## 12. Риски и замечания

- `pytest` проходит, но FastAPI/Starlette выдает deprecation warning про `fastapi.testclient` и `httpx`; это не ломает текущий bootstrap, но может потребовать обновления тестового клиента на следующем этапе.
- `requirements.lock.txt` является снимком текущей Windows-среды первого bootstrap, а не кроссплатформенным lock-файлом.
- Production Linux окружение на NetAngels должно повторно устанавливать зависимости из `pyproject.toml`; `.venv` не должен переноситься между ОС.
- Бизнес-логика и внешние интеграции намеренно не реализованы.

## 13. Итоговый статус

PASS WITH NOTES

