# 003-01 - Application service contracts implementation report

## 1. Executive summary

Implemented the branch `003` application contract layer only:

```text
DTOs
application errors
Protocol ports
package root exports
unit contract tests
```

No application services, provider adapters, crypto adapter, repository extensions, migrations, dependency changes, live external calls, or database mutations were implemented.

Final status:

```text
IMPLEMENTED - READY FOR 003-02 IDENTITY ONBOARDING SERVICE
```

## 2. Frozen contract source and precedence

Primary source:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
```

Precedence used:

```text
003-00a final specification
003-00 audit report
002-04 accepted persistence closeout
002-03 repository contract implementation report
```

No conflict with the frozen contract was found.

## 3. Initial Git/branch/worktree state

Initial branch:

```text
002-mvp-service-data-model
```

Initial status:

```text
?? codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
?? codex/prompts/003_00a_application_service_user_onboarding_final_specification_prompt.md
?? codex/prompts/003_01_application_service_contracts_implementation_prompt.md
?? codex/reports/003_00_application_service_user_onboarding_audit_report.md
?? codex/reports/003_00a_application_service_user_onboarding_final_specification.md
```

Initial ignored artifacts included local environment and cache files:

```text
.coverage
.env
.mypy_cache/
.pytest_cache/
.python312/
.ruff_cache/
.venv/
__pycache__/
src/kaiten_voice_control.egg-info/
```

Initial log:

```text
568a0bb (HEAD -> 002-mvp-service-data-model) docs: close MVP service data model branch
4abdb91 feat: add persistence repository contracts
9cd4f91 feat: add MVP service persistence model
0501ca3 (main) feat: add PostgreSQL persistence foundation
4e4d728 chore: bootstrap Kaiten Voice Control project
```

Initial `git diff --check`, `git diff --stat`, and `git diff --name-status` had no output because the existing `003` artifacts were untracked.

## 4. Branch creation/switch result

Created and switched to:

```text
003-application-service-user-onboarding
```

Command result:

```text
git switch -c 003-application-service-user-onboarding
Switched to a new branch '003-application-service-user-onboarding'
```

Post-switch branch:

```text
003-application-service-user-onboarding
```

Untracked `003-00/003-00a/003-01` artifacts were preserved.

## 5. Branch-base verification

Merge base:

```text
git merge-base 002-mvp-service-data-model HEAD
568a0bb18b64879a0923ea19ba710d17e78d52b6
```

Post-switch log:

```text
568a0bb (HEAD -> 003-application-service-user-onboarding, 002-mvp-service-data-model) docs: close MVP service data model branch
4abdb91 feat: add persistence repository contracts
9cd4f91 feat: add MVP service persistence model
0501ca3 (main) feat: add PostgreSQL persistence foundation
4e4d728 chore: bootstrap Kaiten Voice Control project
```

Branch `003` starts from the accepted closeout head of branch `002`.

## 6. Baseline quality gate

Before source implementation:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
61 passed in 4.42s

.venv\Scripts\python.exe -m pytest -W error
61 passed in 4.21s

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 33 source files

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.

git diff --check
<no output, exit code 0>
```

Initial `ruff format --check .` failed only on Python snippets inside the new untracked prompt:

```text
codex/prompts/003_01_application_service_contracts_implementation_prompt.md
```

The prompt snippets were minimally formatted. After that:

```text
.venv\Scripts\python.exe -m ruff format --check .
78 files already formatted
```

## 7. Final application package layout

Application contracts now live in:

```text
src/kvc_application/dto.py
src/kvc_application/errors.py
src/kvc_application/ports.py
src/kvc_application/__init__.py
```

No `src/kvc_application/services/` package was created.

## 8. DTO inventory

Implemented DTOs:

```text
ResolveMaxIdentityInput
IdentityResolution
BindKaitenConnectionInput
KaitenConnectionResult
KaitenCredentialSnapshot
ActiveKaitenConnectionSecret
MarkKaitenNeedsReauthInput
KaitenCredentialVerification
EncryptedToken
```

All DTOs are frozen dataclasses and use only stdlib types.

## 9. Exact DTO field inventory

```text
ResolveMaxIdentityInput:
  max_user_id
  max_chat_id
  chat_type

IdentityResolution:
  user_id
  max_chat_binding_id
  user_status
  is_new_user
  kaiten_connection_status

BindKaitenConnectionInput:
  user_id
  api_base_url
  plaintext_token

KaitenConnectionResult:
  connection_id
  user_id
  status
  api_base_url
  kaiten_user_id
  workspace_id
  last_verified_at

KaitenCredentialSnapshot:
  connection_id
  encrypted_api_token
  token_encryption_version

ActiveKaitenConnectionSecret:
  connection_id
  user_id
  api_base_url
  plaintext_token
  snapshot

MarkKaitenNeedsReauthInput:
  user_id
  snapshot
  reason

KaitenCredentialVerification:
  kaiten_user_id
  workspace_id

EncryptedToken:
  ciphertext
  version
```

No hidden product fields were added.

## 10. Frozen dataclass semantics

Tests verify:

```text
all DTOs are dataclasses
all DTOs are frozen
mutation raises FrozenInstanceError
field inventory and order match the frozen contract
```

## 11. Status type aliases

Implemented type aliases:

```python
MaxChatType = Literal["PRIVATE"]
UserStatus = Literal["ACTIVE", "DISABLED"]
KaitenConnectionStatus = Literal["ACTIVE", "DISABLED", "NEEDS_REAUTH"]
```

No Python `Enum` was introduced.

## 12. Secret repr protections

Implemented `repr=False` protections:

```text
BindKaitenConnectionInput.plaintext_token
KaitenCredentialSnapshot.encrypted_api_token
ActiveKaitenConnectionSecret.plaintext_token
ActiveKaitenConnectionSecret.snapshot
MarkKaitenNeedsReauthInput.snapshot
MarkKaitenNeedsReauthInput.reason
EncryptedToken.ciphertext
```

Tests verify secret/snapshot values are absent from repr output using synthetic fake values only.

## 13. KaitenCredentialSnapshot contract

Implemented internal snapshot DTO:

```text
connection_id
encrypted_api_token
token_encryption_version
```

This is the future stale-credential identifier. It is internal only and hidden when embedded in parent secret DTO repr.

## 14. token_encryption_version contract

Confirmed:

```text
token_encryption_version is the crypto/key version only.
```

No logical credential revision, hash field, schema field, or version-column abstraction was added.

## 15. MarkKaitenNeedsReauthInput contract

Implemented:

```text
user_id
snapshot
reason
```

`snapshot` and `reason` are hidden from repr. `reason` remains a plain `str` and is treated as an internal sanitized diagnostic reason. No enum, provider payload, or logging behavior was added.

## 16. Error hierarchy inventory

Implemented:

```text
ApplicationError
IdentityConflict
UserDisabled
KaitenConnectionMissing
KaitenConnectionDisabled
KaitenConnectionNeedsReauth
KaitenAuthenticationFailed
KaitenTemporarilyUnavailable
KaitenVerificationFailed
CredentialEncryptionFailed
CredentialDecryptionFailed
PersistenceConflict
```

All concrete errors subclass `ApplicationError`; `ApplicationError` subclasses `Exception`.

## 17. Port inventory

Implemented exactly:

```text
TokenCipher
KaitenCredentialVerifier
Clock
```

No `MaxClient`, `KaitenCardClient`, notification sender, LLM, STT, UnitOfWork, repository factory, or adapter implementation was added.

## 18. TokenCipher signature

Implemented as a structural `Protocol`:

```python
class TokenCipher(Protocol):
    def encrypt(self, plaintext: str) -> EncryptedToken: ...

    def decrypt(self, ciphertext: bytes, version: int) -> str: ...
```

The interface is synchronous and provider-neutral.

## 19. KaitenCredentialVerifier signature

Implemented as a structural `Protocol`:

```python
class KaitenCredentialVerifier(Protocol):
    async def verify(
        self,
        *,
        api_base_url: str,
        plaintext_token: str,
    ) -> KaitenCredentialVerification: ...
```

Tests verify `verify` is async and `api_base_url` / `plaintext_token` are keyword-only.

## 20. Clock signature

Implemented as a structural `Protocol`:

```python
class Clock(Protocol):
    def now(self) -> datetime: ...
```

The concrete timezone-aware UTC behavior is deferred to the future adapter/service stage.

## 21. Package export surface

`src/kvc_application/__init__.py` now re-exports the contract surface:

```text
DTOs
status type aliases
application errors
TokenCipher
KaitenCredentialVerifier
Clock
```

`__all__` is explicit and contains no services or provider code.

## 22. Dependency/import hygiene

Application source imports are limited to:

```text
dataclasses
datetime
typing
uuid
kvc_application.dto from ports.py
```

Search result for provider/config/crypto/persistence leakage in `src/kvc_application`:

```text
no matches for kvc_integrations, cryptography, httpx, pydantic, AppSettings, get_settings, service classes, commit, rollback
```

## 23. Confirmation no provider implementation exists

Confirmed:

```text
no Kaiten HTTP verifier adapter
no MAX adapter
no GigaChat adapter usage
no SaluteSpeech adapter usage
no provider request/response objects in DTOs or ports
```

## 24. Confirmation no services implemented

Confirmed:

```text
no IdentityService class
no KaitenConnectionService class
no resolve_or_onboard_private_max_user implementation
no bind_or_replace_connection implementation
no mark_needs_reauth behavior
```

## 25. Confirmation no crypto adapter implemented

Confirmed:

```text
TokenCipher is Protocol only.
EncryptedToken is DTO only.
No Fernet/MultiFernet/AES-GCM/key-ring code was added.
No key loading was added.
```

## 26. Confirmation no persistence/schema changes

Confirmed:

```text
src/kvc_persistence/models.py unchanged
src/kvc_persistence/repositories/ unchanged
Alembic revisions unchanged
pyproject.toml unchanged
no DDL/DML performed
```

Alembic remains:

```text
00201_mvp_service_model (head)
```

## 27. Tests added

Added:

```text
tests/unit/test_application_dto_contracts.py
tests/unit/test_application_error_contracts.py
tests/unit/test_application_port_contracts.py
```

Coverage includes DTO inventory, frozen semantics, secret repr protections, status literal aliases, error hierarchy, port signatures, async/sync contracts, and package-root imports.

## 28. Targeted test results

An initial targeted parallel run found two test-authoring issues:

```text
DTO frozen test used object.__setattr__, which bypasses dataclass frozen __setattr__.
Port signature tests compared postponed annotations without resolving them.
```

The same parallel run also caused a pytest-cov internal coverage write conflict on one shard after the tests had passed. Coverage data was cleared with:

```text
.venv\Scripts\python.exe -m coverage erase
```

Final targeted sequential result:

```text
.venv\Scripts\python.exe -m pytest tests/unit/test_application_dto_contracts.py tests/unit/test_application_error_contracts.py tests/unit/test_application_port_contracts.py -v
33 passed in 0.37s
```

## 29. Full quality gate

Post-implementation full gate:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
94 passed in 4.37s

.venv\Scripts\python.exe -m pytest -W error
94 passed in 4.17s

.venv\Scripts\python.exe -m ruff format --check .
84 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 36 source files

git diff --check
<no output, exit code 0>
```

## 30. Alembic unchanged state

Read-only diagnostics:

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

No `alembic upgrade`, `alembic downgrade`, manual DDL, or DML was run.

## 31. Secret audit

Checked new/changed application source, tests, prompt, and specification artifacts for secret markers.

Findings:

```text
No real Kaiten token.
No Authorization header value.
No Bearer token value.
No real encryption key.
No real database password.
No secret config value.
```

Matches were limited to normative forbidden-word references in prompts/specification text and synthetic test values explicitly marked as not for use.

## 32. Changed-file classification

Production code:

```text
src/kvc_application/__init__.py
src/kvc_application/dto.py
src/kvc_application/errors.py
src/kvc_application/ports.py
```

Tests:

```text
tests/unit/test_application_dto_contracts.py
tests/unit/test_application_error_contracts.py
tests/unit/test_application_port_contracts.py
```

Alembic/schema:

```text
none
```

Dependencies:

```text
none
```

Configuration:

```text
none
```

Prompts:

```text
codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
codex/prompts/003_00a_application_service_user_onboarding_final_specification_prompt.md
codex/prompts/003_01_application_service_contracts_implementation_prompt.md
```

Reports:

```text
codex/reports/003_00_application_service_user_onboarding_audit_report.md
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
```

Other:

```text
none
```

Git status before this report was created:

```text
 M src/kvc_application/__init__.py
?? codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
?? codex/prompts/003_00a_application_service_user_onboarding_final_specification_prompt.md
?? codex/prompts/003_01_application_service_contracts_implementation_prompt.md
?? codex/reports/003_00_application_service_user_onboarding_audit_report.md
?? codex/reports/003_00a_application_service_user_onboarding_final_specification.md
?? src/kvc_application/dto.py
?? src/kvc_application/errors.py
?? src/kvc_application/ports.py
?? tests/unit/test_application_dto_contracts.py
?? tests/unit/test_application_error_contracts.py
?? tests/unit/test_application_port_contracts.py
```

Tracked diff stat before this report:

```text
src/kvc_application/__init__.py | 60 ++++++++++++++++++++++++++++++++++++++++-
1 file changed, 59 insertions(+), 1 deletion(-)
```

Tracked name-status before this report:

```text
M src/kvc_application/__init__.py
```

Untracked files are listed above and are not included in plain `git diff --stat` until staged.

Post-report verification:

```text
.venv\Scripts\python.exe -m ruff format --check .
85 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

git diff --check
<no output, exit code 0>

git status --short
 M src/kvc_application/__init__.py
?? codex/prompts/003_00_application_service_user_onboarding_audit_prompt.md
?? codex/prompts/003_00a_application_service_user_onboarding_final_specification_prompt.md
?? codex/prompts/003_01_application_service_contracts_implementation_prompt.md
?? codex/reports/003_00_application_service_user_onboarding_audit_report.md
?? codex/reports/003_00a_application_service_user_onboarding_final_specification.md
?? codex/reports/003_01_application_service_contracts_implementation_report.md
?? src/kvc_application/dto.py
?? src/kvc_application/errors.py
?? src/kvc_application/ports.py
?? tests/unit/test_application_dto_contracts.py
?? tests/unit/test_application_error_contracts.py
?? tests/unit/test_application_port_contracts.py

git diff --stat
src/kvc_application/__init__.py | 60 ++++++++++++++++++++++++++++++++++++++++-
1 file changed, 59 insertions(+), 1 deletion(-)

git diff --name-status
M src/kvc_application/__init__.py
```

## 33. Explicit deferred work for 003-02/03/04

Deferred to `003-02`:

```text
IdentityService
first-message onboarding
MAX binding conflict detection
safe MAX chat rotation
eager notification settings creation
onboarding concurrency retry
```

Deferred to `003-03`:

```text
cryptography-based TokenCipher adapter
versioned key ring
key loading/config boundary
encryption/decryption acceptance
```

Deferred to `003-04`:

```text
KaitenConnectionService
bind/replace
disable
get_active_connection_secret behavior
stale credential snapshot compare-and-mark
mark_needs_reauth behavior
Kaiten credential verifier adapter integration
```

These are not unfinished work for `003-01`.

## 34. Final status

```text
IMPLEMENTED - READY FOR 003-02 IDENTITY ONBOARDING SERVICE
```
