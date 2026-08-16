# 002-04 — Branch acceptance, Git integration and closeout

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Текущий функциональный этап:

```text
002 — MVP service data model
```

Этапы ветки `002` уже выполнены:

```text
002-00   MVP service data model audit
002-00a  Final MVP service data model specification
002-00b  Kaiten deadline semantics correction
002-00c  Live Kaiten deadline acceptance probe
002-01   SQLAlchemy models + initial Alembic migration
002-01a  Python 3.12 persistence clean gate
002-02   Live PostgreSQL persistence acceptance
002-03   Repository/query contracts implementation
```

Основной входной отчёт:

```text
codex/reports/002_03_repository_query_contracts_implementation_report.md
```

Его финальный статус:

```text
IMPLEMENTED - READY FOR 002 BRANCH ACCEPTANCE/CLOSEOUT
```

Технически функциональность ветки `002` принята, но Git-состояние ещё не интегрировано:

- `HEAD` всё ещё находится на `main`;
- изменения `002-00 ... 002-03` находятся в modified/untracked worktree;
- persistence implementation, Alembic revision, repositories, tests, prompts/reports ещё не зафиксированы коммитами.

Этот этап должен **закрыть ветку 002 организационно и технически**.

---

# 1. Главная цель

Выполнить финальную branch acceptance:

1. проверить полный diff всей ветки `002`;
2. убедиться в отсутствии случайных файлов, secrets и unrelated изменений;
3. корректно вынести текущий worktree из `main` в отдельную ветку `002`;
4. повторно выполнить финальный project/database gate;
5. сформировать логическую последовательность Git-коммитов;
6. добиться чистого worktree;
7. подготовить closeout report;
8. оставить ветку готовой к переходу к следующему функциональному этапу.

На `002-04` **не добавлять новую функциональность**.

---

# 2. Нормативные документы

Перед работой изучи:

```text
codex/reports/002_00_mvp_service_data_model_audit_report.md
codex/reports/002_00a_mvp_service_data_model_final_specification.md
codex/reports/002_00b_kaiten_deadline_notification_semantics_correction.md
codex/reports/002_00c_live_kaiten_deadline_representation_acceptance_probe.md
codex/reports/002_01_mvp_service_data_model_implementation_report.md
codex/reports/002_01a_python312_persistence_clean_gate_report.md
codex/reports/002_02_live_postgresql_persistence_acceptance_report.md
codex/reports/002_03_repository_query_contracts_implementation_report.md
```

Ключевые принятые факты:

```text
Python = 3.12.9
Alembic head = 00201_mvp_service_model
PostgreSQL development DB = kvc_dev
business tables = 7
repository/query layer implemented
full gate = 61 passed
alembic check = no new upgrade operations detected
synthetic DB rows after tests = 0
```

Не пересматривать архитектурные решения `002`.

---

# 3. Зафиксированный технический scope ветки 002

Ветка `002` должна содержать только уже принятый persistence foundation:

```text
SQLAlchemy models
initial Alembic migration
Alembic model registry wiring
repository/query layer
PostgreSQL integration tests
structural/unit tests
branch prompts/reports
local runtime hygiene (.gitignore)
```

Не добавлять сейчас:

```text
Kaiten adapter
MAX bot
GigaChat/STT
application service layer
command parser
entity resolver
token encryption service
notification worker
retry/reclaim scheduler
outbox
seed data
new API/CLI commands
new database tables
new migration
```

---

# 4. Baseline Git audit — до любых действий

Сначала выполнить и сохранить результаты:

```powershell
git status --short
git status --ignored --short
git branch --show-current
git branch --list
git log --oneline --decorate --graph -10
git diff --check
git diff --stat
git diff --name-status
```

Также получить список untracked files безопасным способом.

Не выполнять:

```text
git reset --hard
git clean -fd
git checkout .
git restore .
```

Нельзя потерять накопленный worktree `002`.

---

# 5. Проверка текущей ветки

По последнему отчёту ожидается:

```text
HEAD -> main
commit 0501ca3
```

Если это подтверждается, изменения `002` необходимо перенести в отдельную ветку **без потери worktree**.

Целевое имя ветки:

```text
002-mvp-service-data-model
```

Сначала проверить:

```powershell
git branch --list 002-mvp-service-data-model
```

## Если ветка ещё не существует

Создать её из текущего `HEAD`, сохранив текущие modified/untracked files:

```powershell
git switch -c 002-mvp-service-data-model
```

После переключения проверить:

```powershell
git branch --show-current
git status --short
```

Все изменения должны остаться на месте.

## Если ветка уже существует

Не создавать дубликат.

Безопасно определить её base/состояние и переключиться на неё только если текущий worktree можно сохранить без конфликтов.

Если переключение создаёт риск потери/перезаписи изменений:

```text
BLOCKED - EXISTING BRANCH CONFLICT REQUIRES REVIEW
```

Не использовать destructive workaround.

---

# 6. Branch base verification

После перехода на ветку проверить:

```powershell
git merge-base main HEAD
git log --oneline --decorate --graph --all -15
```

Ожидается, что ветка `002` основана на accepted commit ветки `001`:

```text
0501ca3 feat: add PostgreSQL persistence foundation
```

Если база другая — исследовать до staging.

Не выполнять rebase автоматически без необходимости.

---

# 7. Полный changed-files audit

Сформировать полный inventory всех tracked + untracked файлов ветки `002`.

Классифицировать их:

```text
Production code
Persistence models
Repositories
Alembic
Tests
Prompts
Reports
Configuration/hygiene
Environment-only
Unexpected
```

Ожидаемые meaningful paths включают:

```text
src/kvc_persistence/models.py
src/kvc_persistence/repositories/
src/kvc_persistence/migrations/env.py
src/kvc_persistence/migrations/versions/00201_mvp_service_model.py

tests/unit/test_persistence.py
tests/unit/test_imports.py
tests/unit/test_alembic_foundation.py
tests/unit/test_persistence_models.py
tests/unit/test_repository_contracts.py
tests/integration/test_repositories_postgresql.py

codex/prompts/002_*.md
codex/reports/002_*.md

.gitignore
```

Не считать этот список исчерпывающим без фактического diff.

---

# 8. Unexpected-file gate

Любой файл, не относящийся к `002`, должен быть отдельно исследован.

Особенно не должны попасть в commit:

```text
.env
.venv/
.python312/
__pycache__/
.pytest_cache/
.coverage
*.pyc
database dumps
temporary SQL dumps
temporary requirements files
API response dumps
tokens/secrets
IDE caches
```

Если unexpected file содержит полезную работу другого этапа — не удалять автоматически. Исключить из commit и описать.

---

# 9. `.gitignore` review

Проверить изменение `.gitignore`.

Принятый локальный runtime:

```text
.python312/
```

может оставаться ignored как **local environment-only runtime recovery artifact**.

Также должны оставаться ignored:

```text
.env
.venv/
```

Не добавлять избыточные глобальные ignore rules, скрывающие полезный source code.

---

# 10. Secret audit

Перед staging провести secret/hygiene audit всех файлов, которые планируется коммитить.

Проверить минимум признаки:

```text
KVC_KAITEN_API_TOKEN
Authorization: Bearer
password=
DATABASE_URL with embedded password
real Kaiten token
real MAX token
GigaChat credentials
SaluteSpeech credentials
private keys
```

Важно:

- не печатать найденное secret value;
- в отчёте указывать только file/key/category;
- `.env` не читать в report и не staging.

Допустимы названия environment variables без значений.

Примеры/placeholder values в prompts/reports допустимы только если явно не являются реальными secrets.

Если реальный secret обнаружен в commit candidate:

1. STOP staging этого файла;
2. удалить/санитизировать secret;
3. проверить Git history/staging;
4. повторить audit.

---

# 11. Test-data privacy audit

Проверить, что source/tests/reports не содержат реальные пользовательские:

```text
Kaiten token
MAX user IDs
private card contents
private workspace data
database password
```

Synthetic IDs/UUIDs разрешены.

Live-probe report может содержать test card ID, если он уже принят как diagnostic non-secret reference, но не должен содержать token или secret URL.

Не расширять отчёты дополнительными live values без необходимости.

---

# 12. Diff review по production code

Проверить полный diff production files.

Особенно подтвердить:

```text
ровно 7 ORM business tables
notification_history.due_at
notification_history.due_date_time_present
absence of due_date DATE
TEXT + CHECK
UUID application defaults
correct ON DELETE
correct partial UNIQUE
no duplicate indexes
caller-owned transaction contract
PendingCommand ownership invariant enforcement
notification ON CONFLICT DO NOTHING reservation
no repository commit/rollback
no plaintext token path
```

Не исправлять стиль/архитектуру, если нет конкретного дефекта.

---

# 13. Alembic final audit

Проверить:

```text
src/kvc_persistence/migrations/versions/00201_mvp_service_model.py
```

Подтвердить:

```text
revision = 00201_mvp_service_model
down_revision = None
seven business tables
correct downgrade
no ENUM
no extension creation
no seed data
```

И:

```powershell
.venv\Scripts\python.exe -m alembic -c alembic.ini heads
.venv\Scripts\python.exe -m alembic -c alembic.ini history
.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

Ожидается:

```text
head/current = 00201_mvp_service_model
No new upgrade operations detected
```

---

# 14. PostgreSQL final-state verification

Без повторения полного `002-02` round-trip проверить безопасно:

```text
current database = kvc_dev
alembic_version = 00201_mvp_service_model
7 business tables
all business table row counts = 0
```

Не выполнять downgrade в closeout, если схема уже принята.

Не выполнять manual DDL.

---

# 15. Repository final audit

Подтвердить наличие:

```text
UserRepository
MaxChatRepository
KaitenConnectionRepository
DialogSessionRepository
PendingCommandRepository
NotificationSettingsRepository
NotificationHistoryRepository
PersistenceInvariantError
```

Проверить:

```text
no .commit()
no .rollback()
FOR UPDATE paths present
PendingCommand ownership invariant enforced
ON CONFLICT DO NOTHING used for notification reserve
no HTTP/API calls
no encryption implementation
```

---

# 16. Final test gate — до commit

Выполнить на Python 3.12:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip check

.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error

.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src

.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check

git diff --check
```

Ожидаемый baseline из `002-03`:

```text
61 passed
61 passed with -W error
Ruff PASS
mypy PASS
Alembic current = 00201_mvp_service_model
Alembic check = no drift
```

Количество тестов может увеличиться только если `002-04` добавил строго необходимые closeout tests; новой feature work быть не должно.

---

# 17. Решение по коммитам

После полного diff audit сформировать **логические коммиты**, а не один случайный dump.

Рекомендуемый plan:

## Commit 1 — persistence model/migration

Пример message:

```text
feat: add MVP service persistence model
```

Включить логически связанные:

```text
SQLAlchemy models
Alembic env wiring
initial migration
persistence model/foundation tests
related import adjustments
```

Не включать repositories.

---

## Commit 2 — repository/query layer

Пример message:

```text
feat: add persistence repository contracts
```

Включить:

```text
src/kvc_persistence/repositories/
repository unit tests
PostgreSQL integration repository tests
repository-related import adjustments
```

---

## Commit 3 — branch documentation/hygiene

Пример message:

```text
docs: close MVP service data model branch
```

Включить:

```text
codex/prompts/002_*.md
codex/reports/002_*.md
.gitignore local runtime hygiene
```

Если `.gitignore` лучше логически относится к environment recovery, допустим отдельный небольшой commit:

```text
chore: ignore local Python runtime
```

Не создавать искусственно много микрокоммитов.

---

# 18. Commit-plan flexibility

Рекомендуемый plan выше не является поводом ломать логически связанный diff.

Перед staging проверь зависимости между файлами.

Если один tracked file содержит изменения разных этапов и их безопасное разделение потребует ручного patch surgery с риском ошибки, допустимо объединить связанные изменения.

Главное:

- commits должны быть reviewable;
- каждый commit должен оставлять coherent source history;
- не использовать случайный `git add .` без предварительного inventory.

---

# 19. Staging discipline

Для каждого commit:

1. staging только явно выбранных paths;
2. выполнить:

```powershell
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
```

3. просмотреть staged diff;
4. повторить secret audit staged content;
5. только затем commit.

Не staging:

```text
.env
.venv/
.python312/
temporary files
unexpected files
```

---

# 20. Commit execution

В этом этапе **разрешено и требуется создать Git commits**, поскольку цель `002-04` — Git integration/closeout.

Не выполнять:

```text
git push
git merge main
git rebase --onto
force push
remote operations
```

Remote integration пользователь выполнит отдельно, если потребуется.

После каждого commit показать:

```powershell
git log -1 --oneline
git status --short
```

---

# 21. Commit-message quality

Commit messages должны:

- быть короткими;
- описывать результат;
- не содержать номера prompt/task вместо смысла;
- не содержать secret/data values.

Предпочтительный стиль:

```text
feat: ...
fix: ...
docs: ...
chore: ...
```

---

# 22. Worktree clean gate

После всех commits:

```powershell
git status --short
```

Ожидается:

```text
<no output>
```

Игнорируемые:

```text
.env
.venv/
.python312/
```

могут существовать и не считаются dirty worktree.

Проверить:

```powershell
git status --ignored --short .env .venv .python312
```

Ожидается только:

```text
!!
```

---

# 23. Final branch history

После commit sequence получить:

```powershell
git log --oneline --decorate --graph main..HEAD
```

История должна ясно показывать вклад ветки `002`.

Также:

```powershell
git branch --show-current
```

Ожидается:

```text
002-mvp-service-data-model
```

Не переключаться обратно на `main` автоматически.

---

# 24. Final diff against main

Проверить:

```powershell
git diff --check main...HEAD
git diff --stat main...HEAD
git diff --name-status main...HEAD
```

Сформировать итоговую классификацию изменений ветки.

Убедиться, что branch diff не содержит unrelated work.

---

# 25. Final quality gate — после commits

После commit sequence повторить критический gate ещё раз:

```powershell
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src
.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check
git status --short
git diff --check main...HEAD
```

Commit process не должен менять результаты gate.

---

# 26. Что допускается исправить

Если closeout audit выявил:

- реальный secret;
- случайный temporary file;
- formatting error;
- broken test;
- obvious documentation inconsistency;
- accidental unrelated change;
- missing ignore rule для local environment artifact;

допускается минимальное исправление.

Если обнаружен functional/schema/repository defect:

```text
не маскировать его closeout-коммитом
```

Оценить:

```text
implementation bug
или
architecture decision
```

При существенном defect:

```text
BLOCKED - BRANCH CLOSEOUT CORRECTION REQUIRED
```

и не объявлять ветку закрытой до повторной приемки затронутого слоя.

---

# 27. Что нельзя делать

На `002-04` запрещено:

- новая business feature;
- новая DB table/column;
- новая Alembic revision;
- Kaiten/MAX integration;
- encryption service;
- notification worker;
- application service layer;
- dependency upgrades без причины;
- destructive Git cleanup;
- merge в `main`;
- push;
- force operations;
- удаление accepted reports/prompts ради уменьшения diff.

---

# 28. Closeout report

Создай:

```text
codex/reports/002_04_branch_acceptance_git_integration_closeout_report.md
```

Report должен содержать минимум:

1. Executive summary.
2. Initial branch/worktree state.
3. Branch creation/switch result.
4. Branch base verification.
5. Full changed-file inventory.
6. Unexpected-file review.
7. `.gitignore` review.
8. Secret audit.
9. Test-data/privacy audit.
10. Production diff review.
11. Alembic final audit.
12. PostgreSQL final-state verification.
13. Repository final audit.
14. Pre-commit quality gate.
15. Commit plan.
16. Commit hashes/messages.
17. Files included in each commit.
18. Staged diff/secret checks.
19. Final branch history.
20. Final diff vs `main`.
21. Worktree clean state.
22. Final post-commit quality gate.
23. Database final state.
24. Explicit deferred work.
25. Final branch status.

---

# 29. Deferred work

Closeout report должен явно отделить то, что **не относится к ветке 002**:

```text
application transaction orchestration
Kaiten adapter/API integration
MAX bot integration
token encryption/decryption service
GigaChat/STT integration
business command state machine
entity resolution
notification polling/retry/reclaim
cleanup/retention
commercial/user onboarding layer
```

Это будущие ветки, а не незавершённость `002`.

---

# 30. Acceptance criteria

Ветка `002` считается закрытой только если:

- полный diff audited;
- unexpected files отсутствуют либо исключены;
- secrets отсутствуют в commit candidates;
- `.env`, `.venv`, `.python312` не committed;
- рабочая ветка имеет имя `002-mvp-service-data-model`;
- ветка основана на правильном `main` baseline;
- production persistence code соответствует принятым reports;
- Alembic head/current = `00201_mvp_service_model`;
- `alembic check` не показывает drift;
- live development DB содержит 7 пустых business tables;
- repositories соответствуют transaction/locking contracts;
- pre-commit full gate проходит;
- изменения оформлены логическими commits;
- post-commit full gate проходит;
- `git status --short` пуст;
- `git diff --check main...HEAD` проходит;
- branch diff не содержит unrelated work;
- closeout report создан и включён в final documentation commit либо отдельный финальный docs commit;
- remote push/merge не выполнялись.

---

# 31. Финальный статус

Если всё успешно:

```text
BRANCH 002 ACCEPTED AND CLOSED - READY FOR NEXT BRANCH
```

Если обнаружен secret или неожиданный unrelated diff:

```text
BLOCKED - GIT HYGIENE CORRECTION REQUIRED
```

Если выявлен functional defect:

```text
BLOCKED - BRANCH CLOSEOUT CORRECTION REQUIRED
```

Если существующая ветка `002-mvp-service-data-model` конфликтует с текущим worktree:

```text
BLOCKED - EXISTING BRANCH CONFLICT REQUIRES REVIEW
```

---

## Главное правило

`002-04` не должен добавлять новый продуктовый функционал.

Его задача:

```text
audit
+
branch isolation
+
secret/hygiene verification
+
logical commits
+
final quality gate
+
clean worktree
+
closeout report
```

После этого ветка `002` должна быть не просто технически выполнена, а **полностью интегрирована в Git и готова к закрытию**.
