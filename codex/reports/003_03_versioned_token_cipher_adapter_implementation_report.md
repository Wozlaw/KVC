# 003-03 - Versioned TokenCipher adapter implementation report

## 1. Executive summary

Implemented the branch `003-03` security adapter boundary:

```text
plaintext application credential
<-> Fernet authenticated ciphertext bytes + explicit crypto key version
```

Implemented:

```text
VersionedFernetTokenCipher
versioned Fernet key ring
one active write version
exact-version decrypt
safe settings fields and parser/factory
unit/config/security tests
```

No `KaitenConnectionService`, Kaiten verifier, provider network call, persistence wiring, repository change, model/schema change, or Alembic revision was added.

Final status:

```text
IMPLEMENTED - READY FOR 003-04 KAITEN CONNECTION SERVICE
```

## 2. Frozen sources and precedence

Sources used:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md
```

Precedence:

```text
003-00a frozen specification
003-01 frozen DTO/port/error contracts
003-02 accepted branch state
003-03 implementation prompt
```

No frozen contract conflict was found.

## 3. Initial Git/worktree state

Initial branch:

```text
003-application-service-user-onboarding
```

Initial HEAD:

```text
f99b2c8 feat: add application service contracts
```

Initial status before the `003-02` checkpoint:

```text
 M src/kvc_application/__init__.py
 M src/kvc_persistence/repositories/max_chats.py
 M tests/integration/test_repositories_postgresql.py
 M tests/unit/test_imports.py
 M tests/unit/test_repository_contracts.py
?? codex/prompts/003_02_identity_onboarding_service_implementation_prompt.md
?? codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md
?? codex/reports/003_02_identity_onboarding_service_implementation_report.md
?? src/kvc_application/services/
?? tests/integration/test_identity_service_postgresql.py
?? tests/unit/test_identity_service.py
```

Ignored local artifacts included `.env`, virtualenv/cache directories, and coverage/cache outputs.

## 4. `003-02` prompt-path correction

The `003-02` prompt artifact was already present at the required path:

```text
codex/prompts/003_02_identity_onboarding_service_implementation_prompt.md
```

The misplaced path was absent:

```text
codex/reports/003_02_identity_onboarding_service_implementation_prompt.md
Test-Path result: False
```

No duplicate prompt copy was created.

## 5. Pre-checkpoint acceptance gate

Before staging accepted `003-02`:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
110 passed in 5.75s

.venv\Scripts\python.exe -m pytest -W error
110 passed in 5.57s

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 38 source files

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.

git diff --check
<no output, exit code 0>
```

`ruff format --check .` initially failed only because the current untracked `003-03` prompt contained an unformatted Python snippet. The prompt was formatted and left outside the `003-02` checkpoint. Final result:

```text
.venv\Scripts\python.exe -m ruff format --check .
92 files already formatted
```

## 6. Pre-checkpoint DB baseline

Read-only baseline before checkpoint:

```text
alembic_version=00201_mvp_service_model
dialog_sessions=0
kaiten_connections=0
max_chats=0
notification_history=0
notification_settings=0
pending_commands=0
users=0
```

No cleanup or DML was performed.

## 7. `003-02` secret/diff audit

Checked accepted `003-02` source, tests, prompt, and report by searching only filenames for secret markers, without printing matched lines.

Findings:

```text
No real MAX identity.
No real Kaiten token.
No Authorization or Bearer header value.
No real database password.
No encryption key.
No private workspace/card data.
```

Matches were limited to field names, normative security text, and synthetic test values.

## 8. Exact staged `003-02` inventory

Staged explicitly, without `git add .`:

```text
A codex/prompts/003_02_identity_onboarding_service_implementation_prompt.md
A codex/reports/003_02_identity_onboarding_service_implementation_report.md
M src/kvc_application/__init__.py
A src/kvc_application/services/__init__.py
A src/kvc_application/services/identity.py
M src/kvc_persistence/repositories/max_chats.py
A tests/integration/test_identity_service_postgresql.py
M tests/integration/test_repositories_postgresql.py
A tests/unit/test_identity_service.py
M tests/unit/test_imports.py
M tests/unit/test_repository_contracts.py
```

Staged checks:

```text
git diff --cached --check
<no output, exit code 0>

git diff --cached --stat
11 files changed, 4057 insertions(+)
```

The current `003-03` prompt was not staged.

## 9. `003-02` checkpoint SHA/message

Created checkpoint commit:

```text
e577ed9 feat: add identity onboarding service
```

Post-checkpoint log:

```text
e577ed9 (HEAD -> 003-application-service-user-onboarding) feat: add identity onboarding service
f99b2c8 feat: add application service contracts
568a0bb (002-mvp-service-data-model) docs: close MVP service data model branch
4abdb91 feat: add persistence repository contracts
9cd4f91 feat: add MVP service persistence model
0501ca3 (main) feat: add PostgreSQL persistence foundation
```

## 10. Post-checkpoint worktree state

After checkpoint:

```text
?? codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md
```

`git diff --check` had no output.

## 11. `003-03` baseline gate

Before `003-03` source changes:

```text
git branch --show-current
003-application-service-user-onboarding

git log --oneline --decorate -6
e577ed9 (HEAD -> 003-application-service-user-onboarding) feat: add identity onboarding service
f99b2c8 feat: add application service contracts
568a0bb (002-mvp-service-data-model) docs: close MVP service data model branch
4abdb91 feat: add persistence repository contracts
9cd4f91 feat: add MVP service persistence model
0501ca3 (main) feat: add PostgreSQL persistence foundation

git status --short
?? codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md

.venv\Scripts\python.exe -m pytest
110 passed in 5.76s

.venv\Scripts\python.exe -m pytest -W error
110 passed in 6.29s

.venv\Scripts\python.exe -m ruff format --check .
92 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 38 source files

.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

## 12. Cryptography dependency audit

`pyproject.toml` already declared `cryptography` as a direct dependency.

Installed version:

```text
.venv\Scripts\python.exe -c "import cryptography; print(cryptography.__version__)"
50.0.0
```

No dependency file was changed. No unrelated dependency was upgraded.

## 13. Final package layout

New security integration package:

```text
src/kvc_integrations/security/__init__.py
src/kvc_integrations/security/token_cipher.py
```

The concrete adapter is not in `kvc_application`, `kvc_persistence`, an ORM model, or a repository.

## 14. `VersionedFernetTokenCipher` constructor/API

Implemented:

```text
VersionedFernetTokenCipher(keys: Mapping[int, str | bytes], active_version: int)
encrypt(plaintext: str) -> EncryptedToken
decrypt(ciphertext: bytes, version: int) -> str
```

The class structurally satisfies the existing `TokenCipher` protocol. It does not inherit from `Protocol` or an abstract base class.

## 15. Fernet authenticated-encryption contract

The adapter uses `cryptography.fernet.Fernet` for authenticated encryption.

Flow:

```text
encrypt: plaintext str -> UTF-8 bytes -> Fernet token bytes -> EncryptedToken
decrypt: Fernet token bytes + explicit version -> exact Fernet decrypt -> UTF-8 str
```

No custom cipher or token hashing/fingerprinting was added.

## 16. Key-version validation

Constructor validation rejects:

```text
empty key ring
version 0
negative versions
boolean versions
non-integer versions
missing active version
empty key values
invalid Fernet keys
```

Version values are positive integers only.

## 17. Active write-version behavior

`encrypt()` always uses the configured active version and returns:

```text
EncryptedToken.version == active_version
```

Changing the active version is a configuration deployment action, not a credential revision.

## 18. Exact-version decrypt behavior

`decrypt(ciphertext, version)`:

```text
validates the supplied version
selects exactly that Fernet instance
does not try active version first
does not try every key
does not rotate or rewrite ciphertext
```

Unknown or invalid versions map to `CredentialDecryptionFailed`.

## 19. Explicit no-MultiFernet-fallback statement

`MultiFernet` is not used.

The implementation never attempts fallback trial-decrypt across unrelated versions. This preserves the persisted `token_encryption_version` contract and future stale-credential snapshot semantics.

## 20. UTF-8 handling

`encrypt()` encodes plaintext with UTF-8.

`decrypt()` decodes decrypted bytes with UTF-8. Authenticated payloads that cannot decode as UTF-8 map to:

```text
CredentialDecryptionFailed("Decrypted credential is not valid UTF-8")
```

Tests cover ASCII, Cyrillic, and Unicode round-trips.

## 21. Encryption error mapping

Unexpected encryption failures are mapped to:

```text
CredentialEncryptionFailed("Failed to encrypt credential")
```

Exception chaining is preserved. Error messages do not contain plaintext, ciphertext, keys, or environment values.

## 22. Decryption error mapping

Mapped to `CredentialDecryptionFailed`:

```text
unknown version
invalid version
tampered Fernet token
wrong key for stored version
invalid decrypted UTF-8
```

Messages are generic and do not include ciphertext, key material, plaintext fragments, or raw key JSON.

## 23. Adapter immutability/repr security

The constructor copies and normalizes the caller key mapping into private Fernet instances.

Future mutation of the input mapping does not change adapter behavior. No public key map or Fernet instance is exposed.

The default object repr/str does not reveal synthetic Fernet keys; tests assert this.

## 24. Environment-variable contract

Frozen MVP env names:

```text
KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION
KVC_TOKEN_ENCRYPTION_KEYS
```

The key map is one secret-bearing JSON object value. No per-version env discovery such as `KVC_KEY_1` was added.

## 25. Settings/config changes

Added optional `AppSettings` fields:

```text
token_encryption_active_version: int | None = None
token_encryption_keys: SecretStr | None = None
```

The existing `KVC_` prefix yields exactly:

```text
KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION
KVC_TOKEN_ENCRYPTION_KEYS
```

Blank env values normalize to `None`.

## 26. Key JSON parsing/validation

Implemented:

```text
parse_token_encryption_key_ring(...)
build_token_cipher(settings)
```

Parser behavior:

```text
JSON object only
string version keys parsed to positive ints
string Fernet key values only
empty map rejected
invalid JSON/list/scalar rejected
normalized duplicate versions such as "1" and "01" rejected
Fernet keys validated through Fernet construction
```

Parser returns a validated `dict[int, str]`. Parsed raw key strings are not stored as a public settings field.

## 27. Missing-config startup compatibility

Generic settings load still works without crypto config:

```text
AppSettings(_env_file=None).token_encryption_active_version is None
AppSettings(_env_file=None).token_encryption_keys is None
```

Existing health/app import tests still pass. API/worker startup was not changed to require crypto keys.

## 28. Cipher construction fail-fast behavior

`build_token_cipher(settings)` fails fast if:

```text
active version is missing
key JSON is missing
key JSON is invalid
active version is absent from parsed key ring
any Fernet key is invalid
```

Chosen error mechanism: concise `ValueError` at config/composition boundary, with safe messages.

## 29. Key rotation proof

Tests prove:

```text
deployment with active version 1 can encrypt old token
deployment with keys {1, 2} and active version 2 encrypts new token as version 2
the same rotated cipher decrypts old version-1 ciphertext with key 1
no automatic re-encryption occurs
```

## 30. Unit tests

Added:

```text
tests/unit/test_token_cipher_adapter.py
```

Coverage:

```text
EncryptedToken return
active write version
ASCII/Cyrillic/Unicode round-trip
old-version decrypt after rotation
unknown version failure
wrong key failure
tampered ciphertext failure
invalid UTF-8 failure
mapping immutability
repr/str key redaction
plaintext/ciphertext absence from errors
constructor validation
structural TokenCipher usability
```

## 31. Configuration tests

Added:

```text
tests/unit/test_token_cipher_config.py
```

Coverage:

```text
settings load without crypto values
exact frozen env names
SecretStr redaction
single-version build
multi-version rotation build
missing active/key config failure
invalid JSON/list/scalar failure
empty map failure
non-integer/0/negative versions failure
normalized duplicate version failure
invalid Fernet key failure
active version absent failure
safe configuration error messages
```

## 32. Error-redaction/security tests

Tests use synthetic markers only:

```text
SYNTHETIC-PLAINTEXT-MUST-NOT-LEAK
SYNTHETIC-KEY-MUST-NOT-LEAK
SYNTHETIC-CIPHERTEXT-MUST-NOT-LEAK
```

Assertions verify those markers are absent from adapter repr/str and relevant exception string/repr output.

## 33. Protocol/type conformance

The adapter exposes synchronous `encrypt`/`decrypt`, returns the existing `EncryptedToken` DTO, and raises existing application credential errors.

Mypy source check passes:

```text
Success: no issues found in 40 source files
```

No `@runtime_checkable` or port signature change was introduced.

## 34. Confirmation no persistence/schema changes

Confirmed:

```text
src/kvc_persistence/models.py unchanged
src/kvc_persistence/repositories/ unchanged
no Alembic revision
no DDL
no new model field
no crypto table
no key material in PostgreSQL
```

`EncryptedToken.version` equals `kaiten_connections.token_encryption_version` equals crypto/key version. It is not a credential snapshot revision.

## 35. Confirmation no service/provider wiring

Confirmed:

```text
no KaitenConnectionService
no concrete KaitenCredentialVerifier
no Kaiten HTTP calls
no MAX transport calls
no TokenCipher injection into API/worker/IdentityService
no ciphertext persistence orchestration
```

## 36. Alembic current/check

Final Alembic diagnostics:

```text
.venv\Scripts\python.exe -m alembic -c alembic.ini current
00201_mvp_service_model (head)

.venv\Scripts\python.exe -m alembic -c alembic.ini check
No new upgrade operations detected.
```

## 37. Business DB baseline unchanged

Final read-only DB state:

```text
alembic_version=00201_mvp_service_model
dialog_sessions=0
kaiten_connections=0
max_chats=0
notification_history=0
notification_settings=0
pending_commands=0
users=0
```

`003-03` did not require business-table DML.

## 38. Dependency/config audit

Results:

```text
Was cryptography already a direct dependency? yes
Was pyproject.toml changed? no
Were any unrelated dependencies changed? no
Were crypto config fields added? yes
Were env names exactly frozen names? yes
Was .env untouched? yes
Was .env.example changed only with safe placeholders/comments? yes
Does generic startup/settings load still work without keys? yes
Does cipher construction fail when required crypto config is absent? yes
```

`.env.example` no longer advertises the obsolete single-key variable and contains only blank placeholders for the frozen versioned key-ring contract.

## 39. Secret audit

Checked new integration source, config source, tests, `.env.example`, current prompt, report content, and Git diff scope.

Findings:

```text
No real Fernet key.
No real Kaiten token.
No Authorization header value.
No Bearer token value.
No database password.
No private data.
```

Matches were limited to env variable names, `SecretStr`, normative prompt/report text, and synthetic test markers/ephemeral runtime-generated test keys.

## 40. Targeted test gate

Targeted command:

```text
.venv\Scripts\python.exe -m pytest tests\unit\test_token_cipher_adapter.py tests\unit\test_token_cipher_config.py tests\unit\test_settings.py tests\unit\test_imports.py -v
```

Result:

```text
collected 58 items
58 passed in 2.41s
```

No warnings survived the later full `-W error` gate.

## 41. Full quality gate

Final full gate before this report:

```text
.venv\Scripts\python.exe --version
Python 3.12.9

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m pytest
154 passed in 6.17s

.venv\Scripts\python.exe -m pytest -W error
154 passed in 5.90s

.venv\Scripts\python.exe -m ruff format --check .
96 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

.venv\Scripts\python.exe -m mypy src
Success: no issues found in 40 source files

git diff --check
<no output, exit code 0>
```

Post-report verification:

```text
.venv\Scripts\python.exe -m ruff format --check .
97 files already formatted

.venv\Scripts\python.exe -m ruff check .
All checks passed!

git diff --check
<no output, exit code 0>
```

## 42. Changed-file classification

Integration production code:

```text
src/kvc_integrations/security/__init__.py
src/kvc_integrations/security/token_cipher.py
```

Configuration production code:

```text
src/kvc_config/settings.py
```

Application contracts:

```text
unchanged
```

Application services:

```text
unchanged
```

Persistence:

```text
unchanged
```

Tests:

```text
tests/unit/test_imports.py
tests/unit/test_token_cipher_adapter.py
tests/unit/test_token_cipher_config.py
```

Alembic/schema:

```text
none
```

Dependencies:

```text
none
```

Environment/example:

```text
.env.example
```

Prompts:

```text
codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md
```

Reports:

```text
codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
```

Database final state:

```text
alembic_version=00201_mvp_service_model
all seven business tables contain 0 rows
```

Other:

```text
none
```

## 43. Explicit deferred work

Deferred to `003-04`:

```text
KaitenConnectionService
KaitenCredentialVerifier concrete HTTP adapter
credential verification-before-persist orchestration
bind_or_replace_connection
disable_connection
get_active_connection_secret
TokenCipher injection into service
ciphertext persistence
last_verified_at
user row locking
connection row locking
credential snapshot capture
mark_needs_reauth
stale credential compare-and-mark
provider error mapping
```

Still outside this branch stage:

```text
MAX transport/bot
GigaChat
STT
dialog orchestration
pending commands
notification worker
```

## 44. Final Git status/diff

Before this report was created:

```text
 M .env.example
 M src/kvc_config/settings.py
 M tests/unit/test_imports.py
?? codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md
?? src/kvc_integrations/security/
?? tests/unit/test_token_cipher_adapter.py
?? tests/unit/test_token_cipher_config.py
```

Tracked diff:

```text
.env.example               |  6 +++++-
src/kvc_config/settings.py | 13 +++++++++++--
tests/unit/test_imports.py |  1 +
3 files changed, 17 insertions(+), 3 deletions(-)
```

Tracked name-status:

```text
M .env.example
M src/kvc_config/settings.py
M tests/unit/test_imports.py
```

Untracked source/test/report/prompt files are listed in `git status --short`.

## 45. Final status

```text
IMPLEMENTED - READY FOR 003-04 KAITEN CONNECTION SERVICE
```
