"""Application error contract tests."""

from __future__ import annotations

from kvc_application.errors import (
    ApplicationError,
    CredentialDecryptionFailed,
    CredentialEncryptionFailed,
    IdentityConflict,
    KaitenAuthenticationFailed,
    KaitenConnectionDisabled,
    KaitenConnectionMissing,
    KaitenConnectionNeedsReauth,
    KaitenTemporarilyUnavailable,
    KaitenVerificationFailed,
    PersistenceConflict,
    UserDisabled,
)

ERROR_TYPES = [
    IdentityConflict,
    UserDisabled,
    KaitenConnectionMissing,
    KaitenConnectionDisabled,
    KaitenConnectionNeedsReauth,
    KaitenAuthenticationFailed,
    KaitenTemporarilyUnavailable,
    KaitenVerificationFailed,
    CredentialEncryptionFailed,
    CredentialDecryptionFailed,
    PersistenceConflict,
]


def test_application_error_is_exception() -> None:
    assert issubclass(ApplicationError, Exception)


def test_error_inventory_subclasses_application_error() -> None:
    for error_type in ERROR_TYPES:
        assert issubclass(error_type, ApplicationError)


def test_error_inventory_contains_distinct_classes() -> None:
    assert len(set(ERROR_TYPES)) == len(ERROR_TYPES)


def test_errors_do_not_require_provider_specific_arguments() -> None:
    for error_type in ERROR_TYPES:
        error = error_type()
        assert isinstance(error, ApplicationError)
