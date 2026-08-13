# 001-01a — TestClient dependency cleanup and clean bootstrap baseline

## Контекст

Проект: **Kaiten Voice Control**.

Предыдущий этап `001-01 — Project bootstrap` выполнен и принят функционально.

Исходный отчёт:

```text
codex/reports/001_01_project_bootstrap_environment_codex_git_report.md
```

Продуктовая спецификация вручную добавлена пользователем в:

```text
docs/specifications/
```

Текущее подтверждённое состояние среды:

```text
Python 3.12.9

pytest:
4 passed, 1 warning

ruff:
All checks passed!

mypy:
Success: no issues found in 16 source files

FastAPI /health:
работает

Git:
ветка main
коммитов пока нет
```

Текущий warning при запуске тестов:

```text
StarletteDeprecationWarning:
Using `httpx` with `starlette.testclient` is deprecated;
install `httpx2` instead.
```

При ручном запуске Hypercorn сервер работает штатно и endpoint `/health` доступен.

После остановки Hypercorn через `Ctrl+C` под Windows может выводиться traceback вида:

```text
InterruptedError: [Errno 4] Interrupted function call
```

внутри:

```text
hypercorn/run.py
multiprocessing/connection.py
_winapi.WaitForMultipleObjects
```

Это поведение не относится к бизнес-логике Kaiten Voice Control и не должно исправляться маскированием исключения в коде приложения.

---

# Цель этапа

Получить полностью чистую bootstrap-базу проекта перед первым Git-коммитом:

1. устранить `StarletteDeprecationWarning`;
2. сохранить обычный `httpx` как runtime HTTP-клиент проекта;
3. корректно добавить необходимую тестовую зависимость для современного Starlette/FastAPI TestClient;
4. обновить dependency snapshot;
5. прогнать полный quality gate без предупреждений;
6. документально зафиксировать Windows-особенность завершения Hypercorn;
7. не затрагивать бизнес-архитектуру и внешние интеграции.

---

# 1. Обязательное предварительное обследование

Перед изменениями:

1. изучить:

```text
pyproject.toml
requirements.lock.txt
tests/
src/kvc_api/main.py
AGENTS.md
.codex/config.toml
codex/reports/001_01_project_bootstrap_environment_codex_git_report.md
```

2. проверить актуальное содержимое `docs/specifications/` и подтвердить наличие продуктовой спецификации;

3. выполнить:

```powershell
python --version
python -m pip check
pytest
ruff check .
mypy src
git status --short
```

4. зафиксировать фактический источник warning и используемый тестовый клиент.

Не менять файлы до понимания причины warning.

---

# 2. Исправление тестовой зависимости

## 2.1. Runtime `httpx` сохранить

`httpx` является штатной runtime-зависимостью Kaiten Voice Control.

Он потребуется для HTTP-взаимодействия с внешними системами, в том числе:

- Kaiten API;
- MAX Bot API;
- GigaChat;
- другими HTTP-интеграциями.

Поэтому:

```text
httpx
```

нельзя удалять из runtime dependencies только ради исправления TestClient.

---

## 2.2. TestClient dependency

Необходимо привести тестовый контур FastAPI/Starlette к актуальному механизму клиента.

Ожидаемое направление:

```text
runtime:
    httpx

dev/test:
    httpx2
```

Но перед внесением изменения Codex обязан проверить фактическую совместимость установленной версии:

```text
FastAPI 0.141.1
Starlette, установленный как зависимость FastAPI
pytest
httpx
httpx2
```

Нельзя механически менять зависимости без проверки.

Если для устранения warning достаточно добавить `httpx2` в dev dependencies — выполнить минимально необходимое изменение.

Если требуется также минимальная корректировка тестового кода — выполнить только её и подробно объяснить причину в отчёте.

Не переписывать тестовый стек без необходимости.

---

# 3. `pyproject.toml`

Обеспечить правильное разделение зависимостей.

Runtime dependencies должны оставаться в:

```toml
[project]
dependencies = [
    ...
]
```

Dev/test dependencies:

```toml
[project.optional-dependencies]
dev = [
    ...
]
```

`httpx2`, если он необходим только тестовому контуру, должен находиться среди dev dependencies.

Не добавлять новые dependency managers.

Не вводить Poetry, uv, Pipenv или иные инструменты управления окружением в рамках этой задачи.

---

# 4. Обновление virtualenv

Использовать существующую корневую среду:

```text
.venv
```

Не пересоздавать `.venv`, если для этого нет технической причины.

После изменения зависимостей выполнить установку проекта:

```powershell
python -m pip install -e ".[dev]"
```

или эквивалентную команду через Python текущей `.venv`.

После установки:

```powershell
python -m pip check
```

должен возвращать:

```text
No broken requirements found.
```

---

# 5. `requirements.lock.txt`

Текущий файл является snapshot фактической Windows-среды bootstrap.

После успешного обновления зависимостей пересоздать его:

```powershell
python -m pip freeze > requirements.lock.txt
```

Не пытаться в рамках данной задачи превращать его в кроссплатформенный lock-файл.

В отчёте сохранить замечание:

> `requirements.lock.txt` — снимок текущего Windows development environment; production Linux environment должен устанавливаться из `pyproject.toml`.

---

# 6. Тесты

Существующие тесты должны продолжать проверять как минимум:

```text
GET /health
imports
settings
```

Не удалять тесты ради устранения warning.

Не ослаблять assertions.

Если тесты используют:

```python
from fastapi.testclient import TestClient
```

либо:

```python
from starlette.testclient import TestClient
```

не менять этот подход без необходимости.

Предпочтение — минимальному dependency-level исправлению.

---

# 7. Политика предупреждений

После исправления обычный запуск:

```powershell
pytest
```

должен завершаться без секции:

```text
warnings summary
```

и без:

```text
StarletteDeprecationWarning
```

Дополнительно выполнить:

```powershell
pytest -W error
```

или эквивалентную проверку, превращающую warnings в ошибки.

Цель — доказать, что текущий собственный тестовый контур проекта не генерирует предупреждений.

Если сторонние библиотеки генерируют warning, который невозможно устранить без необоснованного изменения архитектуры или версий, не скрывать его автоматически через blanket-фильтр. Описать проблему в отчёте.

Не добавлять глобальное:

```text
ignore::Warning
```

или аналогичные широкие подавления.

---

# 8. Hypercorn / Windows shutdown

Не вносить в приложение код, предназначенный только для подавления:

```text
InterruptedError: [Errno 4] Interrupted function call
```

при остановке Hypercorn под Windows.

Запрещено добавлять:

```python
try:
    ...
except InterruptedError:
    pass
```

или аналогичное подавление вокруг приложения, ASGI lifecycle либо server startup/shutdown, если исключение возникает внутри процесса Hypercorn.

Никакой бизнес-код не должен зависеть от особенностей завершения Hypercorn под Windows.

В документации проекта добавить короткое эксплуатационное примечание в подходящий существующий файл, предпочтительно:

```text
docs/operations/
```

Например:

```text
docs/operations/local_development.md
```

Зафиксировать:

- локальная разработка выполняется под Windows;
- Hypercorn может вывести `InterruptedError` после `Ctrl+C`;
- если до остановки сервер работал и `/health` отвечал штатно, данный traceback не означает сбой приложения;
- production environment планируется Linux/NetAngels;
- не маскировать этот upstream/server-level эффект в коде приложения.

Не превращать это в большой документ.

---

# 9. Границы задачи

В рамках `001-01a` запрещено реализовывать:

- Kaiten API;
- MAX Bot API;
- GigaChat integration;
- STT;
- PostgreSQL connection;
- SQLAlchemy models;
- Alembic migrations;
- пользователей;
- диалоговые сессии;
- PendingCommand;
- уведомления;
- command handlers;
- worker scheduling;
- webhook endpoints;
- authentication;
- Docker;
- CI/CD;
- production deployment.

Также не проводить архитектурный рефакторинг созданной структуры каталогов.

Это узкий corrective step.

---

# 10. Quality gate

После завершения изменений выполнить из активированной `.venv`:

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
pytest: PASS, 0 warnings
pytest -W error: PASS
ruff format --check: PASS
ruff check: PASS
mypy src: PASS
```

Также проверить imports:

```powershell
python -c "import fastapi, hypercorn, sqlalchemy, alembic, httpx, pydantic, gigachat; import kvc_api, kvc_worker, kvc_domain, kvc_application, kvc_persistence, kvc_notifications, kvc_config, kvc_integrations; print('runtime and project imports ok')"
```

Если `httpx2` предоставляет отдельный import-модуль, проверить и его согласно фактической документации установленного пакета. Не придумывать имя импортируемого модуля.

Проверить TOML:

```powershell
python -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); tomllib.load(open('.codex/config.toml','rb')); print('toml ok')"
```

Git:

```powershell
git diff --check
git status --short
git check-ignore -v -- .env .venv
```

Убедиться, что:

```text
.env
.venv/
```

игнорируются.

Убедиться, что не игнорируются:

```text
AGENTS.md
.codex/config.toml
requirements.lock.txt
docs/specifications/
docs/operations/
```

---

# 11. Git

Коммит в рамках задачи **не выполнять**.

Staging также не выполнять, если это не требуется исключительно для диагностической проверки.

Проект должен остаться в состоянии, пригодном для ручной приёмки пользователем перед первым коммитом.

Не менять:

- global Git config;
- remote;
- user.name;
- user.email.

---

# 12. Отчёт

Создать:

```text
codex/reports/001_01a_testclient_dependency_cleanup_report.md
```

Отчёт должен содержать:

## 12.1. Исходное состояние

- версии Python;
- версии FastAPI / Starlette / httpx / httpx2;
- исходный warning;
- исходный результат pytest.

## 12.2. Причина warning

Кратко описать фактическую техническую причину.

Не ограничиваться формулировкой «добавили пакет».

## 12.3. Выполненные изменения

Перечислить:

- изменённые зависимости;
- изменённые тестовые файлы, если были;
- обновлённый snapshot;
- добавленное operation note.

## 12.4. Hypercorn shutdown note

Зафиксировать, что:

- приложение и `/health` работали;
- traceback появляется после `Ctrl+C` под Windows;
- application-level workaround не добавлялся.

## 12.5. Проверки

Привести фактические результаты всех quality gates.

Особенно явно:

```text
pytest:
X passed, 0 warnings
```

и:

```text
pytest -W error:
PASS
```

## 12.6. Git state

Привести:

```text
git status --short
git diff --check
```

Подтвердить отсутствие commit/staging.

## 12.7. Отклонения

Если пришлось отклониться от ожидаемого подхода:

```text
runtime httpx + dev httpx2
```

обязательно объяснить почему.

## 12.8. Итог

Один из статусов:

```text
PASS
PASS WITH NOTES
FAIL
```

`PASS` допустим только если:

- warning устранён;
- все тесты проходят;
- `pytest -W error` проходит;
- Ruff проходит;
- mypy проходит;
- pip check проходит;
- Git diff check проходит;
- бизнес-архитектура не затронута.

---

# 13. Критерий завершения этапа

Этап `001-01a` считается завершённым, если bootstrap проекта имеет чистый quality gate:

```text
Python 3.12.x
        ↓
dependencies valid
        ↓
pytest PASS / 0 warnings
        ↓
pytest -W error PASS
        ↓
Ruff PASS
        ↓
mypy PASS
        ↓
imports PASS
        ↓
TOML PASS
        ↓
git diff --check PASS
```

После этого пользователь отдельно выполняет ручную приёмку и принимает решение о первом Git commit.

Следующий архитектурный этап после принятия `001-01a`:

```text
001-02 — Configuration and PostgreSQL persistence foundation
```

Но его реализация **не входит** в текущую задачу.
