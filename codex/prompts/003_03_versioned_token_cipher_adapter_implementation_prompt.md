# 003-03 — Versioned TokenCipher and cryptography adapter implementation

## Роль

Ты работаешь в репозитории проекта **Kaiten Voice Control (KVC)**.

Функциональная ветка:

```text
003 — Application service layer and user onboarding
```

Текущая рабочая ветка:

```text
003-application-service-user-onboarding
```

Принятые этапы:

```text
003-00   Application service/user onboarding audit
003-00a  Final application service/user onboarding specification
003-01   Application DTO/port/error contracts implementation
003-02   IdentityService + MAX onboarding/rotation implementation
```

Основные нормативные документы:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
```

Финальный статус `003-02`:

```text
IMPLEMENTED - READY FOR 003-03 TOKEN CIPHER ADAPTER
```

На этом этапе необходимо:

1. сначала привести артефакт prompt `003-02` к правильному пути;
2. повторить acceptance gate `003-02`;
3. создать checkpoint commit принятого `003-02`;
4. затем реализовать только:
   - concrete versioned `TokenCipher` adapter;
   - authenticated encryption на базе `cryptography.fernet.Fernet`;
   - versioned key ring;
   - active write key/version;
   - exact-version decrypt;
   - безопасную конфигурацию ключей;
   - encryption/decryption error mapping;
   - unit/security/configuration tests;
5. создать report `003-03`.

Не реализовывать `KaitenConnectionService`, Kaiten credential verifier/network adapter, bind/replace/disable/reauth workflows или transport wiring.

---

# 1. Главная цель

После `003-03` application port:

```python
class TokenCipher(Protocol):
    def encrypt(self, plaintext: str) -> EncryptedToken: ...
    def decrypt(self, ciphertext: bytes, version: int) -> str: ...
```

должен иметь production-ready MVP implementation:

```text
VersionedFernetTokenCipher
```

с contract:

```text
plaintext str
    ↓ UTF-8
Fernet authenticated encryption
    ↓
ciphertext bytes
+
crypto/key version int
```

и:

```text
ciphertext bytes
+
persisted crypto/key version
    ↓
select exactly that version's key
    ↓
Fernet authenticated decrypt
    ↓ UTF-8
plaintext str
```

Ключевой invariant:

```text
token_encryption_version == crypto/key version
```

и **никогда**:

```text
logical credential revision
token generation number
connection revision
```

---

# 2. Источники истины и приоритет

Перед изменением кода изучи:

```text
codex/reports/003_00a_application_service_user_onboarding_final_specification.md
codex/reports/003_01_application_service_contracts_implementation_report.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
```

Также изучи фактический код:

```text
src/kvc_application/dto.py
src/kvc_application/errors.py
src/kvc_application/ports.py
src/kvc_application/services/identity.py

src/kvc_config/
src/kvc_integrations/
src/kvc_api/
src/kvc_worker/

pyproject.toml
.env.example
tests/
```

Приоритет:

```text
003-00a frozen specification
    >
003-01 frozen TokenCipher DTO/port/error contracts
    >
003-02 accepted branch state
```

Не переоткрывать application port.

Не менять сигнатуры:

```text
EncryptedToken
TokenCipher.encrypt
TokenCipher.decrypt
CredentialEncryptionFailed
CredentialDecryptionFailed
```

без реального frozen-contract blocker.

---

# 3. Frozen application crypto contracts

Уже реализованы и считаются frozen:

```python
@dataclass(frozen=True)
class EncryptedToken:
    ciphertext: bytes = field(repr=False)
    version: int


class TokenCipher(Protocol):
    def encrypt(self, plaintext: str) -> EncryptedToken: ...

    def decrypt(self, ciphertext: bytes, version: int) -> str: ...
```

Application errors:

```text
CredentialEncryptionFailed
CredentialDecryptionFailed
```

`EncryptedToken.ciphertext` уже должен быть:

```text
repr=False
```

Не создавать второй crypto DTO.

Не создавать новый application crypto interface.

---

# 4. Frozen security decisions

`003-00a` требует:

```text
authenticated encryption
cryptography-based adapter
versioned key support
one active write version
read support for old versions during rotation
key material outside PostgreSQL
key material outside Git
no custom cipher
no plaintext/ciphertext/key logging
```

На `003-03` конкретный MVP механизм фиксируется как:

```text
cryptography.fernet.Fernet
```

Concrete class:

```text
VersionedFernetTokenCipher
```

Не использовать `MultiFernet` как primary version-resolution mechanism.

Причина:

```text
database already stores token_encryption_version;
decrypt must deterministically select the exact persisted key version;
silent trial-decrypt across unrelated versions weakens the version contract.
```

`MultiFernet` не нужен для выполнения frozen MVP semantics.

---

# 5. Git checkpoint — mandatory before crypto implementation

`003-02` принят пользователем, но его implementation/report находятся в worktree.

Сначала зафиксируй именно принятый `003-02`.

## 5.1. Inspect current Git state

Выполни:

```powershell
git branch --show-current
git status --short
git status --ignored --short
git log --oneline --decorate --graph -10
git diff --check
git diff --stat
git diff --name-status
```

Expected branch:

```text
003-application-service-user-onboarding
```

Expected previous checkpoint:

```text
f99b2c8 feat: add application service contracts
```

Не считать SHA абсолютным источником истины, если repository state объективно уже был дополнительно принят/изменён пользователем; report должен показать фактический HEAD.

---

# 6. Correct misplaced `003-02` prompt artifact

`003-02` report зафиксировал организационный дефект:

```text
codex/reports/003_02_identity_onboarding_service_implementation_prompt.md
```

Prompt должен находиться:

```text
codex/prompts/003_02_identity_onboarding_service_implementation_prompt.md
```

До checkpoint:

```text
move/rename the untracked prompt artifact to the correct codex/prompts path
```

Не копировать его с сохранением второй дублирующей версии в `codex/reports`.

После исправления должно быть:

```text
codex/prompts/003_02_identity_onboarding_service_implementation_prompt.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
```

и не должно быть:

```text
codex/reports/003_02_identity_onboarding_service_implementation_prompt.md
```

Если prompt уже исправлен вручную пользователем, не делать вторую копию.

Current `003-03` prompt:

```text
codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md
```

может быть untracked input artifact и не должен входить в checkpoint `003-02`.

---

# 7. Pre-checkpoint `003-02` acceptance gate

До staging выполнить:

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

Accepted `003-02` reference:

```text
Python 3.12.9
pytest = 110 passed
pytest -W error = 110 passed
ruff PASS
mypy PASS
Alembic current = 00201_mvp_service_model
Alembic check = no new upgrade operations detected
```

If test count differs only due to harmless additional tests already accepted by the user, record actual result.

Do not checkpoint failing source.

---

# 8. Database baseline before checkpoint

`003-02` final development DB state was:

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

Do not assume zeros blindly if the user has added development data since then.

Record current baseline safely.

Do not delete user-created rows to match the old report.

`003-03` itself should not need business-table DML.

---

# 9. Pre-checkpoint secret and diff audit

Inspect all `003-02` source/tests/prompt/report before staging.

Confirm no real:

```text
MAX identity
Kaiten token
Authorization header
Bearer token
database password
encryption key
private workspace/card data
```

Never print a discovered secret.

If a real secret is found:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

---

# 10. Stage accepted `003-02` explicitly

Do not use:

```text
git add .
```

Stage only accepted `003-02` artifacts, expected approximately:

```text
src/kvc_application/__init__.py
src/kvc_application/services/__init__.py
src/kvc_application/services/identity.py

src/kvc_persistence/repositories/max_chats.py

tests/unit/test_identity_service.py
tests/unit/test_imports.py
tests/unit/test_repository_contracts.py
tests/integration/test_identity_service_postgresql.py
tests/integration/test_repositories_postgresql.py

codex/prompts/003_02_identity_onboarding_service_implementation_prompt.md
codex/reports/003_02_identity_onboarding_service_implementation_report.md
```

Do not stage current `003-03` prompt.

Then:

```powershell
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
git status --short
```

Review exact staged inventory.

---

# 11. Create accepted `003-02` checkpoint

If gate, diff, and secret audit pass:

```powershell
git commit -m "feat: add identity onboarding service"
```

Do not amend:

```text
f99b2c8
```

Do not squash.

Do not push.

Do not merge.

After commit:

```powershell
git log --oneline --decorate -6
git status --short
git diff --check
```

Record checkpoint SHA.

Expected dirty artifact after checkpoint may be only:

```text
codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md
```

plus unrelated user work, if any.

---

# 12. `003-03` production package boundary

Preferred new package:

```text
src/kvc_integrations/security/
    __init__.py
    token_cipher.py
```

Concrete production class:

```text
VersionedFernetTokenCipher
```

Rationale:

```text
crypto is an external/security adapter concern,
not application business logic,
and not Kaiten-specific provider behavior.
```

Do not place concrete Fernet implementation in:

```text
kvc_application
kvc_persistence
ORM model
repository
```

If the existing integration package has an established equivalent structure, follow it while preserving this boundary.

---

# 13. Concrete class contract

Implement structurally compatible:

```python
class VersionedFernetTokenCipher:
    def __init__(
        self,
        *,
        keys: Mapping[int, str | bytes],
        active_version: int,
    ) -> None: ...

    def encrypt(self, plaintext: str) -> EncryptedToken: ...

    def decrypt(self, ciphertext: bytes, version: int) -> str: ...
```

Type shape may use a narrower internal alias if helpful.

The object satisfies `TokenCipher` structurally.

Do not make it inherit from `Protocol`.

Do not use abstract base classes.

---

# 14. Key-version domain

Encryption key versions are:

```text
positive integers
```

Valid examples:

```text
1
2
3
```

Invalid:

```text
0
negative values
booleans
non-integer labels
duplicate logical versions
```

`active_version` must exist in the supplied key ring.

Key-version validation happens at adapter/configuration construction time.

Runtime `decrypt(version=...)` with an unknown version maps to:

```text
CredentialDecryptionFailed
```

not to a configuration leak.

---

# 15. Fernet key contract

Each version maps to exactly one valid Fernet key:

```text
URL-safe base64-encoded 32-byte Fernet key
```

Use `cryptography.fernet.Fernet` validation.

Do not:

```text
derive Fernet keys from user passwords
hash arbitrary strings into keys
truncate/pad user values
invent a KDF
auto-generate production keys at application startup
```

Key generation is an operational action, not runtime application behavior.

Tests may use:

```python
Fernet.generate_key()
```

with synthetic ephemeral keys.

---

# 16. Active write version

`encrypt()` must always use:

```text
active_version
```

and return:

```python
EncryptedToken(
    ciphertext=<fernet token bytes>,
    version=active_version,
)
```

The ciphertext itself must not encode application-level version logic.

Persistence later stores:

```text
encrypted_api_token = ciphertext
token_encryption_version = version
```

but persistence is not touched on this stage.

---

# 17. Exact-version decrypt

`decrypt(ciphertext, version)` must:

```text
1. lookup exactly keys[version]
2. if version absent:
       CredentialDecryptionFailed
3. decrypt ciphertext only with that Fernet instance
4. authenticate token
5. decode UTF-8
6. return plaintext str
```

Forbidden behavior:

```text
try active key first
try every key until one works
fall back to another version
rewrite/rotate ciphertext during decrypt
mutate active_version
```

Exact-version behavior is essential to the frozen persistence contract.

---

# 18. UTF-8 contract

`TokenCipher` works on:

```text
plaintext: str
```

Concrete adapter:

```text
encrypt:
    plaintext.encode("utf-8")

decrypt:
    decrypted_bytes.decode("utf-8")
```

Must correctly round-trip:

```text
ASCII
Cyrillic
Unicode
```

A successfully authenticated ciphertext whose plaintext bytes cannot decode as UTF-8 must map to:

```text
CredentialDecryptionFailed
```

with no plaintext/ciphertext data in the message.

---

# 19. Encryption error mapping

`encrypt()` must not leak raw cryptography exceptions across the application boundary.

Unexpected encryption failure:

```text
CredentialEncryptionFailed
```

Use safe message such as:

```text
Failed to encrypt credential
```

with exception chaining:

```python
raise CredentialEncryptionFailed("...") from exc
```

No error string may include:

```text
plaintext
key
ciphertext
environment value
```

Do not catch `BaseException`.

Do not hide programming errors unrelated to the crypto operation if the adapter can avoid doing so.

---

# 20. Decryption error mapping

Map at minimum:

```text
unknown version
invalid/tampered Fernet token
wrong key for stored version
invalid decrypted UTF-8
```

to:

```text
CredentialDecryptionFailed
```

Messages must be safe and generic.

Examples:

```text
Unsupported credential encryption version
Failed to decrypt credential
Decrypted credential is not valid UTF-8
```

Do not include:

```text
ciphertext repr
key/version map
key bytes
plaintext fragment
raw InvalidToken details
```

Including the numeric non-secret version in a diagnostic message is acceptable but not required.

---

# 21. Key-ring immutability

The adapter must not retain a caller-mutable mapping in a way that allows key replacement after construction.

At construction:

```text
copy/normalize key mapping
create private Fernet instances
```

Future mutations of the original input mapping must not alter cipher behavior.

Do not expose the internal key map through a public property.

Do not expose Fernet instances.

---

# 22. Adapter repr/security

Default/object repr must not reveal key material.

Do not implement a repr that prints:

```text
keys
Fernet key bytes
environment configuration
```

If using dataclasses for any config helper containing secrets:

```text
repr=False
```

must protect secret fields.

Prefer a normal class with private attributes for the cipher.

Tests must assert synthetic key strings are absent from:

```text
repr(cipher)
str(cipher)
```

if `str()` differs.

---

# 23. Configuration contract — exact environment surface

Freeze MVP environment variables:

```text
KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION
KVC_TOKEN_ENCRYPTION_KEYS
```

Semantics:

## `KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION`

```text
positive integer
```

Example conceptually:

```text
2
```

## `KVC_TOKEN_ENCRYPTION_KEYS`

JSON object:

```json
{
  "1": "<fernet-key-v1>",
  "2": "<fernet-key-v2>"
}
```

Environment variable remains a single secret-bearing string.

Do not store this JSON in PostgreSQL.

Do not commit real values.

Do not invent per-version environment variable discovery such as:

```text
KVC_KEY_1
KVC_KEY_2
...
```

for MVP.

---

# 24. Configuration placement

Inspect existing:

```text
src/kvc_config/
```

and integrate with current `AppSettings` / Pydantic-settings convention.

Preferred settings fields:

```text
token_encryption_active_version
token_encryption_keys
```

with environment names generated by existing `KVC_` prefix convention if that convention already exists.

If current settings naming/prefix mechanism would yield the exact required env names above, use it.

If not, configure explicit aliases so the external environment contract remains exactly:

```text
KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION
KVC_TOKEN_ENCRYPTION_KEYS
```

Do not load `.env` inside the adapter.

---

# 25. Secret type for key JSON

The raw `KVC_TOKEN_ENCRYPTION_KEYS` configuration value must be represented using the project's secret-aware settings type, preferably:

```python
SecretStr
```

if Pydantic settings are already used.

Security expectations:

```text
repr(settings)
does not reveal key JSON

str(secret field)
does not reveal key JSON

normal validation error
does not echo the raw key JSON
```

Do not store parsed raw key strings in a public settings field if avoidable.

---

# 26. Settings optionality / startup compatibility

Branch `003` does not yet wire `TokenCipher` into API/worker startup.

Therefore adding crypto configuration must **not break unrelated existing application startup/tests when the cipher is not constructed**.

Preferred contract:

```text
settings fields may be absent/None at generic application settings load
```

and the crypto adapter/config factory validates presence when `TokenCipher` is actually requested.

Do not make every unrelated health-check/startup path require production crypto keys before `003-04` composition wiring exists.

However:

```text
constructing a production TokenCipher without complete crypto configuration must fail fast.
```

This distinction must be tested and documented.

---

# 27. Configuration parser/factory boundary

Implement one small provider-neutral helper in an appropriate integration/config composition location, for example:

```text
build_token_cipher(...)
```

or:

```text
parse_token_encryption_key_ring(...)
```

The exact module may follow repository conventions.

Required behavior:

```text
input:
    active version
    secret JSON key map

parse:
    JSON object only
    string version keys -> positive int versions
    string Fernet keys
    active version must exist
    each Fernet key must validate

output:
    VersionedFernetTokenCipher
```

Do not put JSON parsing inside `kvc_application`.

Do not create a dependency-injection framework.

Do not wire the cipher into `IdentityService`.

---

# 28. Configuration failure behavior

Configuration errors occur during composition/construction, before user credential operations.

Do not add a new application error class merely for config.

Use the project's existing configuration validation/error mechanism if present.

If no specific configuration error exists, a concise:

```text
ValueError
```

or Pydantic validation error at construction/config boundary is acceptable.

Critical requirement:

```text
configuration error messages must not include raw key material
```

Report the chosen mechanism.

---

# 29. JSON key-ring validation

Reject:

```text
non-JSON input
JSON list
JSON scalar
empty object
version key that is not an integer string
version <= 0
empty key string
non-string key value
invalid Fernet key
active version missing from map
```

Accept:

```text
one-key ring
multiple-key ring
old read keys + one active write key
```

JSON object cannot contain duplicate textual keys reliably after parsing; do not build elaborate duplicate detection unless existing parser supports it naturally.

Do ensure aliases such as:

```text
"1"
"01"
```

cannot silently normalize into the same integer version without detection.

If two distinct JSON keys normalize to the same integer:

```text
configuration error
```

---

# 30. Rotation semantics

Key rotation is configuration-driven.

Example:

Initial deployment:

```text
keys = {1: key_v1}
active_version = 1
```

New deployment:

```text
keys = {
    1: key_v1,
    2: key_v2,
}
active_version = 2
```

Then:

```text
new encryptions -> version 2
existing ciphertext version 1 -> decrypt with key 1
```

Do not automatically re-encrypt version-1 rows on read.

Do not delete old keys while rows with that version may still exist.

Background re-encryption is out of scope.

---

# 31. No MultiFernet fallback rotation

Do not implement:

```text
decrypt ciphertext with all keys until success
```

even though MultiFernet supports such behavior.

Why:

```text
KVC persists an explicit crypto version;
that version is part of the stale-credential snapshot;
exact key selection must remain deterministic.
```

A wrong key under the claimed version is a decryption failure, not a reason to search other versions.

---

# 32. Cryptography dependency audit

Inspect:

```text
pyproject.toml
installed packages
```

Run:

```powershell
.venv\Scripts\python.exe -c "import cryptography; print(cryptography.__version__)"
```

If `cryptography` is already a direct declared dependency:

```text
do not change dependencies
```

If it is importable only transitively but not declared directly, add **only** the minimal direct project dependency required for this production adapter, following the existing version-pin style.

If `cryptography` is not available at all, adding it is allowed because `003-00a` explicitly froze a cryptography-based adapter.

Do not add another crypto library.

Any dependency change must be called out explicitly in the report.

---

# 33. Dependency version policy

Do not arbitrarily upgrade unrelated packages.

If adding/directly declaring `cryptography`:

```text
follow current pyproject dependency syntax and compatible version policy
```

Do not run blanket:

```text
pip install -U
pip freeze > requirements.txt
```

Do not change Python version.

After dependency modification:

```text
pip check
```

must pass.

---

# 34. `.env` and `.env.example`

Never modify tracked/untracked real:

```text
.env
```

Do not read/report its secret contents.

If `.env.example` exists, add only safe placeholders/comments for:

```text
KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION
KVC_TOKEN_ENCRYPTION_KEYS
```

No valid production-like Fernet key should be committed as an example.

Preferred example concept:

```text
KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION=
KVC_TOKEN_ENCRYPTION_KEYS=
```

with nearby comments describing format.

If empty integer values would create confusion, comments may show non-secret syntax while actual assignment remains blank.

Do not commit a real-looking reusable key.

---

# 35. No automatic key generation in production config

Forbidden:

```text
if key missing -> Fernet.generate_key()
```

at:

```text
settings load
API startup
worker startup
adapter construction
encrypt()
```

Missing production configuration must fail explicitly when the cipher is requested.

Ephemeral key generation is test-only.

---

# 36. Unit tests — adapter core

Add focused tests, e.g.:

```text
tests/unit/test_token_cipher_adapter.py
```

Cover at minimum:

```text
encrypt returns EncryptedToken
encrypt uses active version
round-trip ASCII
round-trip Cyrillic
round-trip Unicode
same logical cipher with old key decrypts old version
new active version encrypts with new version
unknown version -> CredentialDecryptionFailed
wrong key for same version -> CredentialDecryptionFailed
tampered ciphertext -> CredentialDecryptionFailed
invalid UTF-8 decrypted bytes -> CredentialDecryptionFailed
input key mapping mutation does not change adapter
adapter repr does not reveal synthetic keys
plaintext/ciphertext absent from error messages
```

Use only synthetic ephemeral keys.

---

# 37. Testing invalid UTF-8 safely

Fernet normally encrypts arbitrary bytes, while public `encrypt()` accepts `str`.

To test invalid decrypted UTF-8:

```text
construct a valid Fernet token directly in test using the same synthetic key,
encrypt arbitrary non-UTF-8 bytes,
call adapter.decrypt(...)
```

Expected:

```text
CredentialDecryptionFailed
```

Do not add a production bytes-encrypt API.

---

# 38. Unit tests — key-ring construction

Test direct constructor validation:

```text
empty key ring rejected
active version <= 0 rejected
active version absent rejected
invalid version key rejected if constructor accepts runtime mapping
invalid Fernet key rejected
bool version rejected
```

Because:

```python
isinstance(True, int)
```

is true in Python, explicitly ensure booleans are not silently accepted as key versions.

Do not over-test cryptography internals.

---

# 39. Configuration tests

Extend existing settings/config tests or add:

```text
tests/unit/test_token_cipher_config.py
```

Cover:

```text
generic settings can load without crypto values before wiring
valid active version + valid JSON key ring builds cipher
single version works
multi-version rotation config works
missing active version when building cipher fails
missing key JSON when building cipher fails
invalid JSON fails safely
JSON non-object fails
empty map fails
non-integer version key fails
version 0/negative fails
"1" + "01" normalization collision fails
invalid Fernet key fails
active version absent from map fails
settings repr does not expose key JSON
validation errors do not echo key material
```

Use environment monkeypatching consistent with current settings test style.

Clean environment after each test.

---

# 40. Error-redaction tests

Use distinctive synthetic markers, e.g.:

```text
SYNTHETIC-PLAINTEXT-MUST-NOT-LEAK
SYNTHETIC-KEY-MUST-NOT-LEAK
SYNTHETIC-CIPHERTEXT-MUST-NOT-LEAK
```

Assert they are absent from:

```text
repr(adapter)
exception string
exception repr
settings repr
configuration error string
```

Do not snapshot entire objects unnecessarily.

---

# 41. Protocol conformance test

Without adding `@runtime_checkable`, prove structural usability through typing/tests.

At minimum:

```text
VersionedFernetTokenCipher exposes sync encrypt/decrypt
signatures satisfy existing TokenCipher contract
returns existing EncryptedToken DTO
raises existing application credential errors
```

Mypy should validate normal assignment/use if practical.

Do not modify the port just to make runtime isinstance checks possible.

---

# 42. No persistence tests required for ciphertext storage

`003-03` is a pure adapter/config stage.

Do not create database rows merely to prove encryption.

Persistence already owns:

```text
encrypted_api_token BYTEA
token_encryption_version
```

Actual service persistence wiring belongs to:

```text
003-04
```

No new PostgreSQL business-row mutation is required.

Alembic remains unchanged.

---

# 43. Optional non-DB integration test

A small integration-style test may exercise:

```text
settings/environment
    -> parser/factory
    -> VersionedFernetTokenCipher
    -> round-trip
```

without PostgreSQL or network.

This is useful if config wiring crosses modules.

Do not call external providers.

---

# 44. No `KaitenConnectionService`

Do not implement:

```text
KaitenConnectionService
bind_or_replace_connection
disable_connection
get_active_connection_secret
mark_needs_reauth
```

Do not touch:

```text
kaiten_connections rows
```

except read-only inspection if absolutely required for audit, which should not be necessary.

`003-04` owns this.

---

# 45. No Kaiten verifier/network adapter

Do not implement:

```text
KaitenCredentialVerifier concrete adapter
Kaiten HTTP requests
authentication probe
workspace/user discovery
401 mapping from live network
```

Even though the verifier port already exists, its implementation belongs to `003-04`.

No live Kaiten call.

---

# 46. No service composition wiring yet

Do not inject concrete TokenCipher into:

```text
API startup
worker startup
IdentityService
future KaitenConnectionService
```

unless a minimal factory test requires a non-startup helper.

Production composition into actual workflows belongs to `003-04`.

Goal of `003-03`:

```text
adapter is constructible and accepted,
but unused by current runtime business flow.
```

This is why generic startup must not require keys yet.

---

# 47. No logging of crypto material

Do not add logging of:

```text
plaintext
ciphertext
key
raw key JSON
Fernet token
```

If adapter logs at all, only non-secret metadata such as:

```text
operation type
numeric key version
```

could be acceptable, but logging is not required and should normally be omitted.

---

# 48. No token hashing/fingerprinting

Do not add:

```text
token SHA
ciphertext hash
credential fingerprint
logical version
revision id
```

Stale credential handling frozen in `003-00a` uses:

```text
connection_id + encrypted_api_token + token_encryption_version
```

and will be implemented in `003-04`.

Do not redesign it in crypto adapter.

---

# 49. Key version and stale snapshot separation

Report must explicitly confirm:

```text
EncryptedToken.version
=
kaiten_connections.token_encryption_version
=
crypto key version
```

and:

```text
not a credential snapshot revision
```

Changing active key version does not imply a user changed their Kaiten token.

Changing a token can still produce the same crypto version.

This conceptual separation is mandatory.

---

# 50. Baseline gate after `003-02` checkpoint

Before `003-03` source changes record:

```powershell
git branch --show-current
git log --oneline --decorate -6
git status --short

.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m pytest -W error
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src
.venv\Scripts\python.exe -m alembic -c alembic.ini current
.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

Only current prompt/unrelated known user work may remain dirty.

---

# 51. Targeted test gate

After implementation run targeted tests first.

Example:

```powershell
.venv\Scripts\python.exe -m pytest `
  tests/unit/test_token_cipher_adapter.py `
  tests/unit/test_token_cipher_config.py `
  -v
```

plus any existing settings tests affected by configuration fields.

Report:

```text
collected
passed
skipped
warnings
```

No warning should survive final `-W error`.

---

# 52. Full quality gate

After targeted tests:

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
git status --short
git diff --stat
git diff --name-status
```

Expected:

```text
test count > 110
pytest PASS
pytest -W error PASS
Ruff PASS
mypy PASS
Alembic current = 00201_mvp_service_model
Alembic check = no drift
```

---

# 53. Dependency/configuration audit

Final report must explicitly state:

```text
Was cryptography already a direct dependency?
Was pyproject.toml changed?
Were any unrelated dependencies changed?
Were crypto config fields added?
Were env names exactly frozen names?
Was .env untouched?
Was .env.example changed only with safe placeholders/comments?
Does generic startup/settings load still work without keys?
Does cipher construction fail when required crypto config is absent?
```

No ambiguity.

---

# 54. Secret audit — mandatory

Before report inspect:

```text
new integration source
config source
tests
.env.example
current prompt
report
Git diff
untracked files in stage scope
```

Look for real:

```text
Fernet keys
Kaiten tokens
Authorization values
database passwords
private data
```

Synthetic test keys generated at runtime are preferred over hard-coded valid keys.

Never copy a real key into report.

If a real secret is found:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

---

# 55. Git diff scope audit

Expected production changes after checkpoint approximately:

```text
src/kvc_integrations/security/__init__.py
src/kvc_integrations/security/token_cipher.py

src/kvc_config/... existing settings/config module
possibly .env.example
```

Tests:

```text
tests/unit/test_token_cipher_adapter.py
tests/unit/test_token_cipher_config.py
possibly existing settings/import tests
```

Prompt/report:

```text
codex/prompts/003_03_versioned_token_cipher_adapter_implementation_prompt.md
codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
```

Possible dependency file:

```text
pyproject.toml
```

only if direct `cryptography` declaration was objectively missing.

Unexpected changes to:

```text
models.py
Alembic
repositories
IdentityService
kvc_api runtime wiring
kvc_worker runtime wiring
Kaiten provider adapter
```

must be investigated and normally not introduced.

---

# 56. No schema/database change

Forbidden:

```text
Alembic revision
DDL
new model field
new token version column
new crypto table
key table
key material in PostgreSQL
```

Alembic:

```text
00201_mvp_service_model
```

must remain head/current.

`003-03` should leave business-table row counts unchanged from its starting baseline.

---

# 57. Git discipline after checkpoint

The initial accepted `003-02` checkpoint commit is required and authorized.

After that:

```text
do not commit 003-03 implementation automatically
```

Leave crypto implementation/report in worktree for user review.

Do not:

```text
push
merge
rebase
amend checkpoint
git reset --hard
git clean -fd
```

Do not stage all work blindly.

---

# 58. Implementation report

Create:

```text
codex/reports/003_03_versioned_token_cipher_adapter_implementation_report.md
```

Report must contain at minimum:

1. Executive summary.
2. Frozen sources and precedence.
3. Initial Git/worktree state.
4. `003-02` prompt-path correction.
5. Pre-checkpoint acceptance gate.
6. Pre-checkpoint DB baseline.
7. `003-02` secret/diff audit.
8. Exact staged `003-02` inventory.
9. `003-02` checkpoint SHA/message.
10. Post-checkpoint worktree state.
11. `003-03` baseline gate.
12. Cryptography dependency audit.
13. Final package layout.
14. `VersionedFernetTokenCipher` constructor/API.
15. Fernet authenticated-encryption contract.
16. Key-version validation.
17. Active write-version behavior.
18. Exact-version decrypt behavior.
19. Explicit no-MultiFernet-fallback statement.
20. UTF-8 handling.
21. Encryption error mapping.
22. Decryption error mapping.
23. Adapter immutability/repr security.
24. Environment-variable contract.
25. Settings/config changes.
26. Key JSON parsing/validation.
27. Missing-config startup compatibility.
28. Cipher construction fail-fast behavior.
29. Key rotation proof.
30. Unit tests.
31. Configuration tests.
32. Error-redaction/security tests.
33. Protocol/type conformance.
34. Confirmation no persistence/schema changes.
35. Confirmation no service/provider wiring.
36. Alembic current/check.
37. Business DB baseline unchanged.
38. Dependency/config audit.
39. Secret audit.
40. Targeted test gate.
41. Full quality gate.
42. Changed-file classification.
43. Explicit deferred work.
44. Final Git status/diff.
45. Final status.

---

# 59. Changed-file classification

Use:

```text
Integration production code:
Configuration production code:
Application contracts:
Application services:
Persistence:
Tests:
Alembic/schema:
Dependencies:
Environment/example:
Prompts:
Reports:
Database final state:
Other:
```

Expected:

```text
Application contracts:
unchanged

Application services:
unchanged

Persistence:
unchanged

Alembic/schema:
none
```

---

# 60. Explicit deferred work

Leave for `003-04`:

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

Still outside branch stage:

```text
MAX transport/bot
GigaChat
STT
dialog orchestration
pending commands
notification worker
```

Do not implement any of this in `003-03`.

---

# 61. Acceptance criteria

`003-03` is complete only if:

## Checkpoint

- `003-02` prompt is under `codex/prompts`, not `codex/reports`;
- accepted `003-02` gate passes before commit;
- accepted `003-02` diff contains no real secrets;
- accepted `003-02` checkpoint commit exists;
- checkpoint does not include current `003-03` implementation.

## Adapter

- concrete `VersionedFernetTokenCipher` exists;
- uses `cryptography.fernet.Fernet`;
- structurally implements existing `TokenCipher`;
- no application port signature changed;
- no custom cryptography introduced;
- no MultiFernet/fallback trial-decrypt behavior;
- input mapping is copied/normalized;
- keys are not publicly exposed;
- adapter repr does not leak keys.

## Versions

- versions are positive ints;
- booleans rejected as versions;
- active version must exist;
- encrypt always returns active version;
- decrypt selects exact persisted version;
- unknown version -> `CredentialDecryptionFailed`;
- `EncryptedToken.version` remains crypto/key version only.

## Encryption/decryption

- ASCII round-trip PASS;
- Cyrillic round-trip PASS;
- Unicode round-trip PASS;
- tampered ciphertext fails;
- wrong key for same version fails;
- invalid UTF-8 fails safely;
- old-version ciphertext remains decryptable after active version advances;
- no automatic re-encryption.

## Errors/security

- encryption failures map to `CredentialEncryptionFailed`;
- decryption failures map to `CredentialDecryptionFailed`;
- plaintext absent from repr/errors;
- ciphertext absent from repr/errors;
- key material absent from repr/errors;
- no crypto material logging.

## Configuration

- env contract is exactly:
  - `KVC_TOKEN_ENCRYPTION_ACTIVE_VERSION`
  - `KVC_TOKEN_ENCRYPTION_KEYS`;
- key map is JSON object;
- raw key JSON uses secret-aware settings representation;
- invalid JSON/config fails safely without echoing key values;
- missing config does not break unrelated startup before `003-04`;
- constructing cipher without required config fails fast;
- active version missing from key ring fails;
- invalid Fernet key fails;
- normalized duplicate versions fail;
- `.env` untouched;
- `.env.example`, if changed, contains no real/reusable key.

## Boundaries

- no `KaitenConnectionService`;
- no concrete Kaiten verifier;
- no provider network calls;
- no token persistence wiring;
- no repository change;
- no model/schema change;
- no migration;
- no business DB mutation;
- no runtime startup composition requiring keys yet.

## Gate

- targeted tests PASS;
- full pytest PASS;
- `pytest -W error` PASS;
- Ruff PASS;
- mypy PASS;
- `pip check` PASS;
- Alembic remains `00201_mvp_service_model`;
- Alembic check reports no drift;
- `git diff --check` PASS;
- report created.

---

# 62. Final status

If all acceptance criteria pass:

```text
IMPLEMENTED - READY FOR 003-04 KAITEN CONNECTION SERVICE
```

If the existing config/dependency architecture makes the frozen crypto contract impossible without a broader redesign:

```text
BLOCKED - FROZEN CONTRACT CONFLICT
```

If accepted `003-02` cannot be safely checkpointed:

```text
BLOCKED - CHECKPOINT WORKTREE CONFLICT
```

If a real secret is found:

```text
BLOCKED - SECRET HYGIENE CORRECTION REQUIRED
```

Do not start `003-04` in this prompt.

---

## Главное правило этапа

`003-03` реализует ровно одну техническую границу:

```text
plaintext application credential
    ⇄
authenticated encrypted bytes + explicit crypto key version
```

Конкретный MVP contract:

```text
VersionedFernetTokenCipher
+
exact version -> exact Fernet key
+
one active write version
+
old-version decrypt support
+
external versioned secret key ring
```

Без persistence orchestration, Kaiten verification, connection lifecycle, transport или background workflows.
