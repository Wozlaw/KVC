# 001-01a — TestClient dependency cleanup report

## 12.1. Исходное состояние

- Рабочий каталог: `D:\Prog\KVControl`.
- Git branch: `main`.
- Коммитов и staging не было; проект остается перед первым ручным коммитом.
- Продуктовая спецификация присутствует в `docs/specifications/`:
  - `Kaiten Voice Control — спецификация MVP v0.1.md`.
- Используемый тестовый клиент: `from fastapi.testclient import TestClient`.
- `fastapi.testclient` импортирует `TestClient` из `starlette.testclient`.
- Исходные версии:

```text
Python 3.12.9
fastapi==0.141.1
starlette==1.6.0
httpx==0.28.1
httpx2: not installed
pytest==9.1.1
```

Исходный `pip check`:

```text
No broken requirements found.
```

Исходный `pytest`:

```text
collected 4 items
tests\smoke\test_health.py .. [ 50%]
tests\unit\test_imports.py .  [ 75%]
tests\unit\test_settings.py . [100%]
4 passed, 1 warning in 1.05s
coverage TOTAL: 90%
```

Исходный warning:

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

Baseline checks до правок:

```text
ruff check .
All checks passed!
```

```text
mypy src
Success: no issues found in 16 source files
```

## 12.2. Причина warning

Фактическая причина находится в установленном `starlette.testclient` из Starlette 1.6.0.

Логика импорта такая:

```text
try:
    import httpx2 as httpx
except ModuleNotFoundError:
    import httpx
    warnings.warn(... StarletteDeprecationWarning ...)
```

То есть тестовый клиент Starlette сначала ищет новый backend `httpx2`. Так как `httpx2` не был установлен, Starlette использовал fallback на runtime-пакет `httpx` и сам выдавал deprecation warning. Runtime `httpx` при этом нужен проекту для будущих HTTP-интеграций и не должен удаляться.

## 12.3. Выполненные изменения

- В `pyproject.toml` добавлен `httpx2` в `[project.optional-dependencies].dev`.
- Runtime dependency `httpx` оставлена в `[project].dependencies`.
- Тестовые файлы не изменялись; подход `from fastapi.testclient import TestClient` сохранен.
- Существующая `.venv` не пересоздавалась.
- Выполнена переустановка проекта:

```text
.venv\Scripts\python.exe -m pip install -e ".[dev]"
Successfully installed httpcore2-2.10.0 httpx2-2.10.0 kaiten-voice-control-0.1.0 truststore-0.10.4
```

- Обновлен `requirements.lock.txt` через `pip freeze`.
- В `docs/operations/local_development.md` добавлено короткое примечание про Windows shutdown behavior Hypercorn.

Фактические версии после изменения:

```text
fastapi==0.141.1
starlette==1.6.0
httpx==0.28.1
httpx2==2.10.0
pytest==9.1.1
```

Фрагмент обновленного snapshot:

```text
httpcore==1.0.9
httpcore2==2.10.0
httpx==0.28.1
httpx2==2.10.0
truststore==0.10.4
```

`requirements.lock.txt` — снимок текущего Windows development environment; production Linux environment должен устанавливаться из `pyproject.toml`.

## 12.4. Hypercorn shutdown note

- Ручной запуск Hypercorn и `/health` были подтверждены на предыдущем этапе.
- Traceback `InterruptedError: [Errno 4] Interrupted function call` может появляться после `Ctrl+C` под Windows внутри Hypercorn/Python multiprocessing internals.
- Если до остановки сервер работал и `/health` отвечал штатно, это не является сбоем приложения.
- Production environment планируется Linux/NetAngels.
- Application-level workaround не добавлялся: в код приложения не внесено подавление `InterruptedError`.

## 12.5. Проверки

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
4 passed in 1.15s
coverage TOTAL: 90%
```

`pytest`: 4 passed, 0 warnings.

```text
.venv\Scripts\python.exe -m pytest -W error
collected 4 items
tests\smoke\test_health.py .. [ 50%]
tests\unit\test_imports.py .  [ 75%]
tests\unit\test_settings.py . [100%]
4 passed in 1.03s
coverage TOTAL: 90%
```

`pytest -W error`: PASS.

```text
.venv\Scripts\python.exe -m ruff format --check .
27 files already formatted
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
.venv\Scripts\python.exe -c "import fastapi, hypercorn, sqlalchemy, alembic, httpx, pydantic, gigachat, httpx2; import kvc_api, kvc_worker, kvc_domain, kvc_application, kvc_persistence, kvc_notifications, kvc_config, kvc_integrations; print('runtime, httpx2, and project imports ok')"
runtime, httpx2, and project imports ok
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
git check-ignore -v -- .env .venv AGENTS.md .codex/config.toml requirements.lock.txt docs/specifications docs/operations
.gitignore:2:.env    .env
.gitignore:1:.venv/  .venv
```

`AGENTS.md`, `.codex/config.toml`, `requirements.lock.txt`, `docs/specifications/` и `docs/operations/` не игнорируются.

## 12.6. Git state

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
git diff --cached --name-status
```

Результат: без вывода, staging отсутствует.

```text
git diff --check
```

Результат: без вывода, exit code 0.

Commit не выполнялся. Staging не выполнялся.

## 12.7. Отклонения

Отклонений от ожидаемого подхода `runtime httpx + dev httpx2` нет.

Зависимость `httpx2` добавлена только в dev group, потому что она нужна текущему тестовому клиенту Starlette/FastAPI. Runtime `httpx` сохранен для проектных HTTP-интеграций.

## 12.8. Итог

PASS

