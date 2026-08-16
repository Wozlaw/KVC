# 003-06 — Corrective closeout completion prompt

## Контекст

Ты продолжаешь **тот же этап**:

```text
003-06 — Branch acceptance, Git integration and closeout
```

Это **не новая стадия `003-07`** и не новый функциональный этап.

Текущая ветка:

```text
003-application-service-user-onboarding
```

Основной closeout report уже создан:

```text
codex/reports/003_06_branch_acceptance_git_integration_closeout_report.md
```

В нём техническая приёмка ветки завершена успешно, но последние post-report действия не были выполнены:

```text
final documentation staged audit
final documentation commit
actual final HEAD capture
clean-worktree verification
post-commit sequential quality gate
final PostgreSQL baseline verification
terminal closeout summary
```

Исправить нужно **только этот незавершённый хвост `003-06`**.

---

# 1. Главная цель

Довести `003-06` до фактически завершённого состояния:

```text
accepted 003-06 report
    ↓
final documentation staging
    ↓
final documentation commit
    ↓
actual final HEAD
    ↓
clean worktree
    ↓
post-commit sequential full gate
    ↓
PostgreSQL baseline confirmation
    ↓
terminal closeout summary
```

Финальный статус после успешного выполнения:

```text
BRANCH 003 ACCEPTED AND CLOSED - READY FOR NEXT BRANCH
```

---

# 2. Важная коррекция исходного closeout contract

Исходный prompt требовал одновременно:

```text
создать closeout report до final documentation commit
```

и:

```text
записать SHA этого final documentation commit внутрь самого report
```

Это самоссылочное требование.

Commit SHA зависит от содержимого report, поэтому:

```text
SHA commit, содержащего report,
невозможно заранее записать внутрь этого же report
без изменения содержимого и, следовательно, SHA.
```

## Corrected frozen rule

В `003-06` считать правильным контрактом:

```text
closeout report
    фиксирует все pre-commit результаты
    и явно указывает, что post-commit facts будут возвращены в terminal summary;

final documentation commit SHA
clean worktree status
post-commit gate result
final DB baseline
    фиксируются в финальном terminal response,
    а не записываются обратно в уже committed report.
```

После final documentation commit:

```text
НЕ изменять closeout report
НЕ создавать новый report ради SHA
НЕ делать amend
```

Terminal summary является авторитетным доказательством post-commit closeout facts.

---

# 3. Нормативная база

Использовать:

```text
codex/reports/003_05_full_application_service_acceptance_report.md
codex/reports/003_06_branch_acceptance_git_integration_closeout_report.md
codex/prompts/003_06_branch_acceptance_git_integration_closeout_prompt.md
```

А также текущий corrective prompt:

```text
codex/prompts/003_06_branch_closeout_completion_correction_prompt.md
```

Не пересматривать технические выводы `003-05`/`003-06`, если текущий state им не противоречит.

---

# 4. Запрещено

В рамках корректирующего prompt запрещено:

- менять production code;
- менять tests;
- менять application contracts;
- менять repositories;
- менять config;
- менять `.env.example`;
- менять schema;
- создавать Alembic revision;
- добавлять dependency;
- выполнять новый live Kaiten call;
- выполнять MAX/GigaChat/STT call;
- добавлять feature work;
- открывать ветку `004`;
- merge;
- push;
- rebase;
- amend предыдущих commits;
- `git reset --hard`;
- `git clean -fd`.

Разрешены только:

```text
минимальная documentation correction closeout report
final documentation staging
final documentation commit
read-only verification
test execution
terminal closeout summary
```

---

# 5. Initial state audit

Сначала выполнить:

```powershell
git branch --show-current
git status --short
git status --ignored --short
git log --oneline --decorate --graph -10
git diff --check
git diff --stat
git diff --name-status
```

Ожидаемая ветка:

```text
003-application-service-user-onboarding
```

Ожидаемый последний committed functional checkpoint:

```text
d69afcf test: add full application service acceptance
```

или эквивалентный фактический HEAD, если SHA объективно отличается.

---

# 6. Expected closeout documentation tail

После добавления этого corrective prompt ожидаются три документа:

```text
codex/prompts/003_06_branch_acceptance_git_integration_closeout_prompt.md
codex/prompts/003_06_branch_closeout_completion_correction_prompt.md
codex/reports/003_06_branch_acceptance_git_integration_closeout_report.md
```

Они должны стать содержимым **одного final documentation commit**.

Не оставлять corrective prompt untracked после closeout.

---

# 7. Minimal correction of existing `003-06` report

До staging разрешено **минимально** поправить только:

```text
codex/reports/003_06_branch_acceptance_git_integration_closeout_report.md
```

Не переписывать техническую часть.

Добавить в конец или в соответствующие final sections короткое уточнение:

```text
Closeout execution note:
- final documentation commit contains:
  - original 003-06 prompt
  - corrective 003-06 completion prompt
  - 003-06 closeout report
- final commit SHA cannot be embedded self-referentially in this committed report;
- exact final HEAD, clean worktree result, post-commit gate and final DB baseline
  are reported in the terminal closeout summary after commit creation;
- the report must not be modified after the final documentation commit.
```

Также скорректировать, если необходимо, wording в разделах:

```text
Final documentation commit plan
Final documentation staged audit
Final documentation commit SHA/message
Final worktree clean state
Final post-commit quality gate
```

так, чтобы они **не утверждали**, что SHA/post-commit facts должны быть записаны обратно в report.

Не менять ранее полученные:

```text
225 passed
architecture audit
schema audit
secret audit
accepted lifecycle results
```

---

# 8. Pre-staging documentation check

После минимальной правки report:

```powershell
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
git diff --check
git status --short
```

Если Ruff меняет/проверяет Python snippets в prompts/reports, разрешено минимальное formatting-only исправление этих **трёх final documentation artifacts**.

Production/tests не трогать.

---

# 9. Explicit final documentation staging

Не использовать:

```text
git add .
```

Явно stage:

```powershell
git add -- `
  codex/prompts/003_06_branch_acceptance_git_integration_closeout_prompt.md `
  codex/prompts/003_06_branch_closeout_completion_correction_prompt.md `
  codex/reports/003_06_branch_acceptance_git_integration_closeout_report.md
```

Адаптировать PowerShell continuation syntax к фактической shell, если нужно.

Затем:

```powershell
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
git status --short
```

Expected staged inventory:

```text
A codex/prompts/003_06_branch_acceptance_git_integration_closeout_prompt.md
A codex/prompts/003_06_branch_closeout_completion_correction_prompt.md
A codex/reports/003_06_branch_acceptance_git_integration_closeout_report.md
```

Если оригинальный prompt/report уже каким-то образом tracked, status может быть `M`, но staged content должен быть ограничен этими тремя closeout docs.

---

# 10. Staged secret audit

Провести staged audit.

Не печатать matched lines с потенциальными секретами.

Проверить минимум:

```text
Authorization
Bearer
KVC_KAITEN_API_TOKEN
KVC_TOKEN_ENCRYPTION_KEYS
password
PRIVATE KEY
Fernet
plaintext_token
encrypted_api_token
```

Допустимы только:

```text
normative security wording
environment variable names
field names
sanitized prior PASS metadata
```

Не должно быть:

```text
real token
Authorization value
real Fernet key
database password
real Kaiten user id
raw provider JSON
```

Если найден реальный secret:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

Commit не выполнять.

---

# 11. Re-run staged diff audit after any documentation correction

Если report был изменён после первого staging/audit:

```text
restage report
rerun:
    git diff --cached --check
    git diff --cached --stat
    git diff --cached --name-status
    staged secret audit
```

Последний staged audit должен относиться **к точному content**, который будет committed.

---

# 12. Final documentation commit

Если staged inventory и secret audit чисты:

```powershell
git commit -m "docs: close application service onboarding branch"
```

Не amend.

Не squash.

Не push.

Не merge.

Сразу после commit получить:

```powershell
git log -1 --oneline
git rev-parse HEAD
git status --short
```

Сохранить фактические:

```text
FINAL_HEAD_SHA
FINAL_HEAD_SUBJECT
```

в памяти текущего выполнения для terminal summary.

## Критически важно

После получения SHA:

```text
НЕ открывать report на редактирование
НЕ записывать SHA в report
НЕ делать amend
```

---

# 13. Clean-worktree gate immediately after commit

Проверить:

```powershell
git status --short
```

Expected:

```text
<no output>
```

Если есть tracked/untracked non-ignored artifact:

```text
не удалять автоматически
классифицировать
```

Если это незапланированный closeout artifact:

```text
BLOCKED - GIT HYGIENE CORRECTION REQUIRED
```

Ignored environment/cache files не являются dirty worktree.

---

# 14. Final branch history

После commit:

```powershell
git log --oneline --decorate --graph 002-mvp-service-data-model..HEAD
```

Ожидаемая логическая последовательность:

```text
docs: close application service onboarding branch
test: add full application service acceptance
feat: add Kaiten connection service
feat: add versioned token cipher adapter
feat: add identity onboarding service
feat: add application service contracts
```

Не переписывать историю ради совпадения текста.

Сохранить actual history summary для terminal response.

---

# 15. Final branch base/diff verification

Выполнить:

```powershell
git merge-base 002-mvp-service-data-model HEAD
git merge-base --is-ancestor 002-mvp-service-data-model HEAD

git diff --check 002-mvp-service-data-model...HEAD
git diff --stat 002-mvp-service-data-model...HEAD
git diff --name-status 002-mvp-service-data-model...HEAD
```

Expected:

```text
ancestry exit code 0
diff --check PASS
only accepted 003 scope
```

Не сравнивать `main` как основной closeout baseline.

---

# 16. Final post-commit quality gate — strictly sequential

После final documentation commit выполнить **последовательно**:

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

git diff --check 002-mvp-service-data-model...HEAD
git status --short
```

## Не запускать pytest параллельно

Полные PostgreSQL-backed:

```text
pytest
pytest -W error
```

запускать строго последовательно против общей:

```text
kvc_dev
```

Reference:

```text
225 passed
225 passed with -W error
Python 3.12.9
Ruff PASS
mypy PASS
pip check PASS
Alembic current = 00201_mvp_service_model
Alembic check = no drift
```

Фактический test count является источником истины.

---

# 17. Failure handling for post-commit gate

Если после docs commit падает только documentation formatting/lint из-за final docs:

1. не менять production/tests;
2. локализовать конкретный docs formatting defect;
3. поскольку final docs commit уже создан, **не amend автоматически**;
4. остановиться со статусом:

```text
BLOCKED - FINAL DOCUMENTATION GATE CORRECTION REQUIRED
```

и описать проблему.

Если падают production/tests:

```text
BLOCKED - BRANCH CLOSEOUT CORRECTION REQUIRED
```

Не создавать новый feature code.

Если всё PASS — продолжить.

---

# 18. Final PostgreSQL verification

После полного gate read-only проверить:

```text
KVC_APP_ENV = development
current_database() = kvc_dev
alembic_version = 00201_mvp_service_model
```

Снять counts:

```text
users
max_chats
kaiten_connections
dialog_sessions
pending_commands
notification_settings
notification_history
```

Expected historical baseline:

```text
all = 0
```

Но фактический pre-closeout baseline является источником истины.

Не выполнять broad cleanup.

Если tests оставили synthetic rows:

```text
BLOCKED - TEST DATABASE BASELINE NOT RESTORED
```

Если legitimate user-created rows присутствовали до gate и остались без изменений — это PASS.

---

# 19. Final ignored environment verification

Проверить:

```powershell
git status --ignored --short .env .venv .python312
```

Expected:

```text
ignored markers only
```

Не удалять local environment.

`.env` не читать и не выводить.

---

# 20. No live provider call

Corrective closeout не должен делать повторный live Kaiten probe.

Принятое доказательство уже находится в `003-05`:

```text
GET /users/current
PASS
mutation performed: no
```

В terminal summary указать:

```text
live external calls during corrective closeout: none
```

---

# 21. Final terminal closeout summary — mandatory

После успешного выполнения **не создавать новый файл**.

Вернуть финальный ответ в terminal/chat summary со следующими фактическими данными:

```text
Branch:
003-application-service-user-onboarding

Final HEAD:
<actual SHA> docs: close application service onboarding branch

Base:
002-mvp-service-data-model
merge-base=<actual SHA>
ancestry=PASS

Final documentation commit:
PASS
files:
  codex/prompts/003_06_branch_acceptance_git_integration_closeout_prompt.md
  codex/prompts/003_06_branch_closeout_completion_correction_prompt.md
  codex/reports/003_06_branch_acceptance_git_integration_closeout_report.md

Worktree:
clean

Post-commit quality gate:
Python: <actual>
pip check: PASS
pytest: <actual passed>
pytest -W error: <actual passed>
ruff format: PASS
ruff check: PASS
mypy: PASS
Alembic current: 00201_mvp_service_model
Alembic check: PASS
branch diff --check: PASS

PostgreSQL:
environment=development
database=kvc_dev
alembic_version=00201_mvp_service_model
business-table counts=<actual counts>
baseline restored=<yes/no>

Live external calls during corrective closeout:
none

Final status:
BRANCH 003 ACCEPTED AND CLOSED - READY FOR NEXT BRANCH
```

Не выводить:

```text
real token
Authorization
real Kaiten user id
Fernet key
database password
```

---

# 22. No post-summary repository action

После successful terminal summary:

```text
не создавать новый branch
не делать push
не merge
не добавлять новый commit
```

Оставить repository на:

```text
003-application-service-user-onboarding
```

с clean worktree.

Фактический final HEAD является:

```text
accepted base commit for next functional branch
```

---

# 23. Acceptance criteria

Corrective `003-06` завершён только если:

- текущая ветка `003-application-service-user-onboarding`;
- closeout report минимально скорректирован под non-self-referential SHA contract;
- original `003-06` prompt staged;
- corrective `003-06` prompt staged;
- `003-06` report staged;
- staged diff check PASS;
- staged secret audit PASS;
- final docs commit создан;
- exact final HEAD SHA получен;
- report после commit не изменён;
- worktree clean;
- branch derives from accepted `002`;
- full post-commit gate выполнен последовательно;
- pytest PASS;
- pytest `-W error` PASS;
- Ruff PASS;
- mypy PASS;
- pip check PASS;
- Alembic current/check PASS;
- branch diff check PASS;
- PostgreSQL baseline restored;
- ignored `.env`/venv remain ignored;
- no live provider call сделан;
- final terminal summary возвращает actual SHA/gate/DB facts;
- никакая следующая ветка не создана.

---

# 24. Final statuses

Успех:

```text
BRANCH 003 ACCEPTED AND CLOSED - READY FOR NEXT BRANCH
```

Если documentation commit нельзя безопасно сформировать:

```text
BLOCKED - GIT HYGIENE CORRECTION REQUIRED
```

Если staged secret обнаружен:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

Если post-commit project gate падает:

```text
BLOCKED - BRANCH CLOSEOUT CORRECTION REQUIRED
```

Если только committed documentation нарушает final gate:

```text
BLOCKED - FINAL DOCUMENTATION GATE CORRECTION REQUIRED
```

Если DB baseline не восстановлен:

```text
BLOCKED - TEST DATABASE BASELINE NOT RESTORED
```

---

## Главное правило

Не создавать новый этап.

Не пытаться записывать SHA final documentation commit внутрь report, содержащегося в этом commit.

Завершить уже принятый `003-06` через:

```text
final docs commit
+
actual SHA captured after commit
+
clean worktree
+
post-commit sequential gate
+
final DB verification
+
terminal closeout summary
```

После этого ветка `003` действительно закрыта.
