"""Signed short-lived MAX Mini App context tokens."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import SecretStr

from kvc_integrations.max.errors import (
    MaxMiniAppContextBindingError,
    MaxMiniAppContextExpiredError,
    MaxMiniAppContextPayloadError,
    MaxMiniAppContextPurposeError,
    MaxMiniAppContextSignatureError,
)

MINI_APP_CONTEXT_VERSION = 1
DEFAULT_MAX_TTL_SECONDS = 3600
_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class MiniAppContextPurpose(StrEnum):
    """Stable branch-004 Mini App context purposes."""

    CONNECT_KAITEN = "connect_kaiten"
    RECONNECT_KAITEN = "reconnect_kaiten"
    NOTIFICATION_SETTINGS = "notification_settings"
    SYNTHETIC_CONTEXT = "synthetic_context"


@dataclass(frozen=True)
class MiniAppContextClaims:
    """Trusted claims from a verified Mini App context token."""

    version: int
    purpose: MiniAppContextPurpose
    issued_at: int
    expires_at: int
    nonce: str
    identity_binding: str = field(repr=False)
    workflow_ref: str | None = None


class MiniAppContextSigner:
    """Create and verify short-lived URL-safe Mini App context tokens."""

    def __init__(
        self,
        secret: str | SecretStr,
        *,
        max_ttl_seconds: int = DEFAULT_MAX_TTL_SECONDS,
        future_skew_seconds: int = 60,
    ) -> None:
        if max_ttl_seconds <= 0:
            raise ValueError("max_ttl_seconds must be positive")
        if future_skew_seconds < 0:
            raise ValueError("future_skew_seconds must be non-negative")
        self._secret = _secret_bytes(secret)
        self._max_ttl_seconds = max_ttl_seconds
        self._future_skew_seconds = future_skew_seconds

    def make_identity_binding(self, *, max_user_id: str, chat_id: str) -> str:
        """Create a deterministic opaque binding for a validated MAX identity."""

        material = f"max_user_id={len(max_user_id)}:{max_user_id}\nchat_id={len(chat_id)}:{chat_id}"
        return hmac.new(self._secret, material.encode("utf-8"), hashlib.sha256).hexdigest()

    def issue(
        self,
        *,
        purpose: MiniAppContextPurpose,
        identity_binding: str,
        ttl_seconds: int,
        now: int | None = None,
        nonce: str | None = None,
        workflow_ref: str | None = None,
    ) -> str:
        """Issue a signed context token."""

        issued_at = int(time.time()) if now is None else now
        expires_at = issued_at + ttl_seconds
        claims = MiniAppContextClaims(
            version=MINI_APP_CONTEXT_VERSION,
            purpose=purpose,
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce or secrets.token_urlsafe(16),
            identity_binding=identity_binding,
            workflow_ref=workflow_ref,
        )
        self._validate_claims_shape(claims)
        payload = _canonical_payload(claims)
        encoded_payload = _b64url_encode(payload)
        signature = hmac.new(self._secret, encoded_payload.encode("ascii"), hashlib.sha256).digest()
        return f"{encoded_payload}.{_b64url_encode(signature)}"

    def verify(
        self,
        token: str,
        *,
        expected_purpose: MiniAppContextPurpose,
        expected_identity_binding: str,
        now: int | None = None,
        expected_workflow_ref: str | None = None,
    ) -> MiniAppContextClaims:
        """Verify a context token and return trusted claims."""

        segments = token.split(".")
        if len(segments) != 2 or not segments[0] or not segments[1]:
            raise MaxMiniAppContextPayloadError("invalid Mini App context token")

        encoded_payload, encoded_signature = segments
        if not _B64URL_RE.fullmatch(encoded_payload):
            raise MaxMiniAppContextPayloadError("invalid Mini App context token")
        try:
            supplied_signature = _b64url_decode(encoded_signature)
        except ValueError as error:
            raise MaxMiniAppContextPayloadError("invalid Mini App context token") from error

        expected_signature = hmac.new(
            self._secret,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise MaxMiniAppContextSignatureError("invalid Mini App context signature")

        try:
            payload = json.loads(_b64url_decode(encoded_payload))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            raise MaxMiniAppContextPayloadError("invalid Mini App context payload") from error
        claims = _claims_from_payload(payload)
        self._validate_claims_shape(claims)

        if claims.purpose is not expected_purpose:
            raise MaxMiniAppContextPurposeError("unexpected Mini App context purpose")
        if not hmac.compare_digest(claims.identity_binding, expected_identity_binding):
            raise MaxMiniAppContextBindingError("unexpected Mini App context binding")
        if expected_workflow_ref is not None and claims.workflow_ref != expected_workflow_ref:
            raise MaxMiniAppContextPayloadError("unexpected Mini App context workflow")

        current_time = int(time.time()) if now is None else now
        if claims.issued_at > current_time + self._future_skew_seconds:
            raise MaxMiniAppContextExpiredError("Mini App context is from the future")
        if current_time >= claims.expires_at:
            raise MaxMiniAppContextExpiredError("Mini App context is expired")
        return claims

    def _validate_claims_shape(self, claims: MiniAppContextClaims) -> None:
        if claims.version != MINI_APP_CONTEXT_VERSION:
            raise MaxMiniAppContextPayloadError("unsupported Mini App context version")
        if claims.issued_at < 0 or claims.expires_at < 0:
            raise MaxMiniAppContextPayloadError("invalid Mini App context timestamp")
        if claims.expires_at <= claims.issued_at:
            raise MaxMiniAppContextPayloadError("invalid Mini App context lifetime")
        if claims.expires_at - claims.issued_at > self._max_ttl_seconds:
            raise MaxMiniAppContextPayloadError("Mini App context lifetime is too long")
        if not claims.nonce:
            raise MaxMiniAppContextPayloadError("invalid Mini App context nonce")
        if not claims.identity_binding:
            raise MaxMiniAppContextPayloadError("invalid Mini App context binding")
        if claims.workflow_ref == "":
            raise MaxMiniAppContextPayloadError("invalid Mini App context workflow")


def _secret_bytes(secret: str | SecretStr) -> bytes:
    if isinstance(secret, SecretStr):
        return secret.get_secret_value().encode("utf-8")
    return secret.encode("utf-8")


def _canonical_payload(claims: MiniAppContextClaims) -> bytes:
    payload: dict[str, object] = {
        "binding": claims.identity_binding,
        "exp": claims.expires_at,
        "iat": claims.issued_at,
        "nonce": claims.nonce,
        "purpose": claims.purpose.value,
        "v": claims.version,
    }
    if claims.workflow_ref is not None:
        payload["workflow_ref"] = claims.workflow_ref
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _claims_from_payload(payload: object) -> MiniAppContextClaims:
    if not isinstance(payload, dict):
        raise MaxMiniAppContextPayloadError("invalid Mini App context payload")
    try:
        purpose = MiniAppContextPurpose(_required_str(payload, "purpose"))
    except ValueError as error:
        raise MaxMiniAppContextPurposeError("unexpected Mini App context purpose") from error
    return MiniAppContextClaims(
        version=_required_int(payload, "v"),
        purpose=purpose,
        issued_at=_required_int(payload, "iat"),
        expires_at=_required_int(payload, "exp"),
        nonce=_required_str(payload, "nonce"),
        identity_binding=_required_str(payload, "binding"),
        workflow_ref=_optional_str(payload, "workflow_ref"),
    )


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise MaxMiniAppContextPayloadError("invalid Mini App context payload")
    return value


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise MaxMiniAppContextPayloadError("invalid Mini App context payload")
    return value


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise MaxMiniAppContextPayloadError("invalid Mini App context payload")
    return value


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    if not _B64URL_RE.fullmatch(value):
        raise ValueError("invalid base64url")
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (binascii.Error, ValueError) as error:
        raise ValueError("invalid base64url") from error


__all__ = [
    "DEFAULT_MAX_TTL_SECONDS",
    "MINI_APP_CONTEXT_VERSION",
    "MiniAppContextClaims",
    "MiniAppContextPurpose",
    "MiniAppContextSigner",
]
