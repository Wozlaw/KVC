"""MAX Mini App context signing tests."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re

import pytest
from pydantic import SecretStr

from kvc_integrations.max.context_signing import (
    MINI_APP_CONTEXT_VERSION,
    MiniAppContextPurpose,
    MiniAppContextSigner,
)
from kvc_integrations.max.errors import (
    MaxMiniAppContextBindingError,
    MaxMiniAppContextExpiredError,
    MaxMiniAppContextPayloadError,
    MaxMiniAppContextPurposeError,
    MaxMiniAppContextSignatureError,
)

SECRET = "synthetic-context-secret"
NOW = 1_700_000_000
MAX_STARTAPP_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def test_context_signer_valid_round_trip_and_token_size() -> None:
    signer = MiniAppContextSigner(SecretStr(SECRET))
    binding = signer.make_identity_binding(max_user_id="123", chat_id="456")

    token = signer.issue(
        purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        identity_binding=binding,
        ttl_seconds=900,
        now=NOW,
        nonce="deterministic_nonce",
    )
    claims = signer.verify(
        token,
        expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        expected_identity_binding=binding,
        now=NOW + 1,
    )

    assert claims.purpose is MiniAppContextPurpose.CONNECT_KAITEN
    assert claims.issued_at == NOW
    assert claims.expires_at == NOW + 900
    assert claims.nonce == "deterministic_nonce"
    assert claims.identity_binding == binding
    assert MAX_STARTAPP_RE.fullmatch(token)
    assert 1 <= len(token) <= 512
    for forbidden in ".=+/%":
        assert forbidden not in token
    assert SECRET not in repr(signer)
    assert binding not in repr(claims)


@pytest.mark.parametrize(
    "purpose",
    [MiniAppContextPurpose.CONNECT_KAITEN, MiniAppContextPurpose.RECONNECT_KAITEN],
)
def test_representative_connect_context_fits_max_startapp(purpose: MiniAppContextPurpose) -> None:
    signer = MiniAppContextSigner(SecretStr(SECRET))
    binding = signer.make_identity_binding(max_user_id="123456789", chat_id="987654321")

    token = signer.issue(
        purpose=purpose,
        identity_binding=binding,
        ttl_seconds=900,
        now=NOW,
        nonce="representative_nonce",
    )

    assert MAX_STARTAPP_RE.fullmatch(token)
    assert len(token) <= 512


def test_context_signer_rejects_payload_tamper() -> None:
    signer = MiniAppContextSigner(SECRET)
    binding = signer.make_identity_binding(max_user_id="123", chat_id="456")
    token = signer.issue(
        purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        identity_binding=binding,
        ttl_seconds=900,
        now=NOW,
        nonce="nonce",
    )
    tampered_token = token[:-1] + ("A" if token[-1] != "A" else "B")

    with pytest.raises(MaxMiniAppContextSignatureError):
        signer.verify(
            tampered_token,
            expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            expected_identity_binding=binding,
            now=NOW,
        )


def test_context_signer_rejects_signature_tamper() -> None:
    signer = MiniAppContextSigner(SECRET)
    binding = signer.make_identity_binding(max_user_id="123", chat_id="456")
    token = signer.issue(
        purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        identity_binding=binding,
        ttl_seconds=900,
        now=NOW,
        nonce="nonce",
    )

    with pytest.raises(MaxMiniAppContextSignatureError):
        signer.verify(
            token[:-1] + ("A" if token[-1] != "A" else "B"),
            expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            expected_identity_binding=binding,
            now=NOW,
        )


def test_context_signer_rejects_wrong_secret() -> None:
    signer = MiniAppContextSigner(SECRET)
    other_signer = MiniAppContextSigner("other-synthetic-secret")
    binding = signer.make_identity_binding(max_user_id="123", chat_id="456")
    token = signer.issue(
        purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        identity_binding=binding,
        ttl_seconds=900,
        now=NOW,
        nonce="nonce",
    )

    with pytest.raises(MaxMiniAppContextSignatureError):
        other_signer.verify(
            token,
            expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            expected_identity_binding=binding,
            now=NOW,
        )


def test_context_signer_rejects_expired_context() -> None:
    signer = MiniAppContextSigner(SECRET)
    binding = signer.make_identity_binding(max_user_id="123", chat_id="456")
    token = signer.issue(
        purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        identity_binding=binding,
        ttl_seconds=900,
        now=NOW,
        nonce="nonce",
    )

    with pytest.raises(MaxMiniAppContextExpiredError):
        signer.verify(
            token,
            expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            expected_identity_binding=binding,
            now=NOW + 900,
        )


def test_context_signer_rejects_future_issued_context() -> None:
    signer = MiniAppContextSigner(SECRET)
    binding = signer.make_identity_binding(max_user_id="123", chat_id="456")
    token = signer.issue(
        purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        identity_binding=binding,
        ttl_seconds=900,
        now=NOW,
        nonce="nonce",
    )

    with pytest.raises(MaxMiniAppContextExpiredError):
        signer.verify(
            token,
            expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            expected_identity_binding=binding,
            now=NOW - 61,
        )


def test_context_signer_rejects_wrong_purpose() -> None:
    signer = MiniAppContextSigner(SECRET)
    binding = signer.make_identity_binding(max_user_id="123", chat_id="456")
    token = signer.issue(
        purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        identity_binding=binding,
        ttl_seconds=900,
        now=NOW,
        nonce="nonce",
    )

    with pytest.raises(MaxMiniAppContextPurposeError):
        signer.verify(
            token,
            expected_purpose=MiniAppContextPurpose.RECONNECT_KAITEN,
            expected_identity_binding=binding,
            now=NOW,
        )


def test_context_signer_rejects_wrong_identity_binding() -> None:
    signer = MiniAppContextSigner(SECRET)
    binding = signer.make_identity_binding(max_user_id="123", chat_id="456")
    other_binding = signer.make_identity_binding(max_user_id="789", chat_id="999")
    token = signer.issue(
        purpose=MiniAppContextPurpose.CONNECT_KAITEN,
        identity_binding=binding,
        ttl_seconds=900,
        now=NOW,
        nonce="nonce",
    )

    with pytest.raises(MaxMiniAppContextBindingError):
        signer.verify(
            token,
            expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            expected_identity_binding=other_binding,
            now=NOW,
        )


def test_context_binding_changes_for_same_user_different_chat() -> None:
    signer = MiniAppContextSigner(SECRET)

    first = signer.make_identity_binding(max_user_id="123", chat_id="456")
    second = signer.make_identity_binding(max_user_id="123", chat_id="999")

    assert first != second


@pytest.mark.parametrize(
    "token",
    ["one", "one.two", "one.two.three", "!!!!", "abcd=", "abcd+", "abcd/", "abcd%"],
)
def test_context_signer_rejects_malformed_or_legacy_tokens(token: str) -> None:
    signer = MiniAppContextSigner(SECRET)

    with pytest.raises(MaxMiniAppContextPayloadError):
        signer.verify(
            token,
            expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            expected_identity_binding="binding",
            now=NOW,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "v": 2,
            "purpose": "connect_kaiten",
            "iat": NOW,
            "exp": NOW + 1,
            "nonce": "n",
            "binding": "b",
        },
        {"purpose": "connect_kaiten", "iat": NOW, "exp": NOW + 1, "nonce": "n", "binding": "b"},
        {
            "v": 1,
            "purpose": "connect_kaiten",
            "iat": "bad",
            "exp": NOW + 1,
            "nonce": "n",
            "binding": "b",
        },
        {"v": 1, "purpose": "connect_kaiten", "iat": NOW, "exp": NOW, "nonce": "n", "binding": "b"},
        {
            "v": 1,
            "purpose": "connect_kaiten",
            "iat": NOW,
            "exp": NOW + 1,
            "nonce": "",
            "binding": "b",
        },
        {"v": 1, "purpose": "unknown", "iat": NOW, "exp": NOW + 1, "nonce": "n", "binding": "b"},
    ],
)
def test_context_signer_rejects_invalid_signed_payload_shapes(payload: dict[str, object]) -> None:
    signer = MiniAppContextSigner(SECRET)
    token = _signed_context_token(payload, SECRET)

    with pytest.raises(
        (
            MaxMiniAppContextPayloadError,
            MaxMiniAppContextPurposeError,
            MaxMiniAppContextExpiredError,
        )
    ):
        signer.verify(
            token,
            expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            expected_identity_binding="b",
            now=NOW,
        )


def test_context_signer_rejects_ttl_above_maximum_on_issue_and_verify() -> None:
    signer = MiniAppContextSigner(SECRET, max_ttl_seconds=900)
    binding = signer.make_identity_binding(max_user_id="123", chat_id="456")

    with pytest.raises(MaxMiniAppContextPayloadError):
        signer.issue(
            purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            identity_binding=binding,
            ttl_seconds=901,
            now=NOW,
            nonce="nonce",
        )

    token = _signed_context_token(
        {
            "v": MINI_APP_CONTEXT_VERSION,
            "purpose": "connect_kaiten",
            "iat": NOW,
            "exp": NOW + 901,
            "nonce": "nonce",
            "binding": binding,
        },
        SECRET,
    )
    with pytest.raises(MaxMiniAppContextPayloadError):
        signer.verify(
            token,
            expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            expected_identity_binding=binding,
            now=NOW,
        )


def test_context_signer_validates_workflow_ref_when_expected() -> None:
    signer = MiniAppContextSigner(SECRET)
    binding = signer.make_identity_binding(max_user_id="123", chat_id="456")
    token = signer.issue(
        purpose=MiniAppContextPurpose.SYNTHETIC_CONTEXT,
        identity_binding=binding,
        ttl_seconds=900,
        now=NOW,
        nonce="nonce",
        workflow_ref="workflow-1",
    )

    assert (
        signer.verify(
            token,
            expected_purpose=MiniAppContextPurpose.SYNTHETIC_CONTEXT,
            expected_identity_binding=binding,
            expected_workflow_ref="workflow-1",
            now=NOW,
        ).workflow_ref
        == "workflow-1"
    )
    with pytest.raises(MaxMiniAppContextPayloadError):
        signer.verify(
            token,
            expected_purpose=MiniAppContextPurpose.SYNTHETIC_CONTEXT,
            expected_identity_binding=binding,
            expected_workflow_ref="workflow-2",
            now=NOW,
        )


def test_context_signer_rejects_invalid_json_payload() -> None:
    signer = MiniAppContextSigner(SECRET)
    payload = b"{bad-json"
    signature = hmac.new(SECRET.encode(), payload, hashlib.sha256).digest()

    with pytest.raises(MaxMiniAppContextPayloadError):
        signer.verify(
            _b64url_encode(payload + signature),
            expected_purpose=MiniAppContextPurpose.CONNECT_KAITEN,
            expected_identity_binding="binding",
            now=NOW,
        )


def _signed_context_token(payload: dict[str, object], secret: str) -> str:
    payload_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return _b64url_encode(payload_bytes + signature)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
