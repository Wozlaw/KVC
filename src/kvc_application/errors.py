"""Application-layer error taxonomy."""


class ApplicationError(Exception):
    """Base application-layer error."""


class IdentityConflict(ApplicationError):
    """Raised when MAX identity data maps to conflicting KVC users."""


class UserDisabled(ApplicationError):
    """Raised when a disabled user attempts a blocked operation."""


class KaitenConnectionMissing(ApplicationError):
    """Raised when a user has no Kaiten connection."""


class KaitenConnectionDisabled(ApplicationError):
    """Raised when a user's Kaiten connection is disabled."""


class KaitenConnectionNeedsReauth(ApplicationError):
    """Raised when a user's Kaiten connection requires reauthorization."""


class KaitenAuthenticationFailed(ApplicationError):
    """Raised when Kaiten rejects a credential."""


class KaitenTemporarilyUnavailable(ApplicationError):
    """Raised when Kaiten verification is temporarily unavailable."""


class KaitenVerificationFailed(ApplicationError):
    """Raised when Kaiten verification cannot be interpreted safely."""


class CredentialEncryptionFailed(ApplicationError):
    """Raised when credential encryption fails."""


class CredentialDecryptionFailed(ApplicationError):
    """Raised when credential decryption fails."""


class PersistenceConflict(ApplicationError):
    """Raised when persistence invariants or retryable races cannot be resolved."""


__all__ = [
    "ApplicationError",
    "CredentialDecryptionFailed",
    "CredentialEncryptionFailed",
    "IdentityConflict",
    "KaitenAuthenticationFailed",
    "KaitenConnectionDisabled",
    "KaitenConnectionMissing",
    "KaitenConnectionNeedsReauth",
    "KaitenTemporarilyUnavailable",
    "KaitenVerificationFailed",
    "PersistenceConflict",
    "UserDisabled",
]
