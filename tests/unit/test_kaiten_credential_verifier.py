"""Kaiten HTTP credential verifier tests."""

from __future__ import annotations

import httpx
import pytest

from kvc_application.errors import (
    KaitenAuthenticationFailed,
    KaitenTemporarilyUnavailable,
    KaitenVerificationFailed,
)
from kvc_integrations.kaiten import KaitenHttpCredentialVerifier

TOKEN_MARKER = "SYNTHETIC-KAITEN-TOKEN-MUST-NOT-LEAK"
BODY_MARKER = "SYNTHETIC-BODY-MUST-NOT-LEAK"


@pytest.mark.asyncio
async def test_verifier_success_uses_current_user_endpoint_and_request_scoped_auth() -> None:
    captured = {"auth_ok": False, "token_in_url": False, "path": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["token_in_url"] = TOKEN_MARKER in str(request.url)
        captured["auth_ok"] = request.headers.get("Authorization") == f"Bearer {TOKEN_MARKER}"
        return httpx.Response(200, json={"id": 123})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"X-Shared": "safe"},
    )
    async with client:
        verifier = KaitenHttpCredentialVerifier(client)

        result = await verifier.verify(
            api_base_url="https://example.kaiten.ru/api/latest/",
            plaintext_token=TOKEN_MARKER,
        )

        assert result.kaiten_user_id == "123"
        assert result.workspace_id is None
        assert captured == {
            "auth_ok": True,
            "token_in_url": False,
            "path": "/api/latest/users/current",
        }
        assert "Authorization" not in client.headers


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "user-1"},
        {"id": 1},
    ],
)
@pytest.mark.asyncio
async def test_verifier_accepts_stable_scalar_ids(payload: dict[str, object]) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        result = await KaitenHttpCredentialVerifier(client).verify(
            api_base_url="https://example.kaiten.ru/api/latest",
            plaintext_token=TOKEN_MARKER,
        )

    assert result.kaiten_user_id == str(payload["id"])


@pytest.mark.parametrize("status_code", [401, 403])
@pytest.mark.asyncio
async def test_verifier_maps_authentication_failures(status_code: int) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status_code))
    ) as client:
        with pytest.raises(KaitenAuthenticationFailed) as error:
            await KaitenHttpCredentialVerifier(client).verify(
                api_base_url="https://example.kaiten.ru/api/latest",
                plaintext_token=TOKEN_MARKER,
            )

    assert TOKEN_MARKER not in f"{error.value!s} {error.value!r}"


@pytest.mark.parametrize("status_code", [408, 429, 500, 503])
@pytest.mark.asyncio
async def test_verifier_maps_temporary_http_failures(status_code: int) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status_code))
    ) as client:
        with pytest.raises(KaitenTemporarilyUnavailable) as error:
            await KaitenHttpCredentialVerifier(client).verify(
                api_base_url="https://example.kaiten.ru/api/latest",
                plaintext_token=TOKEN_MARKER,
            )

    assert TOKEN_MARKER not in f"{error.value!s} {error.value!r}"


@pytest.mark.parametrize(
    "exception",
    [
        httpx.TimeoutException("synthetic timeout"),
        httpx.TransportError("synthetic transport error"),
    ],
)
@pytest.mark.asyncio
async def test_verifier_maps_transport_failures(exception: httpx.TransportError) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exception

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(KaitenTemporarilyUnavailable) as error:
            await KaitenHttpCredentialVerifier(client).verify(
                api_base_url="https://example.kaiten.ru/api/latest",
                plaintext_token=TOKEN_MARKER,
            )

    assert TOKEN_MARKER not in f"{error.value!s} {error.value!r}"


@pytest.mark.parametrize("status_code", [400, 404, 409])
@pytest.mark.asyncio
async def test_verifier_maps_unexpected_http_contract_failures(status_code: int) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status_code))
    ) as client:
        with pytest.raises(KaitenVerificationFailed) as error:
            await KaitenHttpCredentialVerifier(client).verify(
                api_base_url="https://example.kaiten.ru/api/latest",
                plaintext_token=TOKEN_MARKER,
            )

    assert TOKEN_MARKER not in f"{error.value!s} {error.value!r}"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text=f"not-json-{BODY_MARKER}"),
        httpx.Response(200, json=[]),
        httpx.Response(200, json="scalar"),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"id": None}),
        httpx.Response(200, json={"id": True}),
        httpx.Response(200, json={"id": ""}),
        httpx.Response(200, json={"id": []}),
        httpx.Response(200, json={"id": {}}),
    ],
)
@pytest.mark.asyncio
async def test_verifier_maps_malformed_success_payload_safely(
    response: httpx.Response,
) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response)) as client:
        with pytest.raises(KaitenVerificationFailed) as error:
            await KaitenHttpCredentialVerifier(client).verify(
                api_base_url="https://example.kaiten.ru/api/latest",
                plaintext_token=TOKEN_MARKER,
            )

    rendered = f"{error.value!s} {error.value!r}"
    assert TOKEN_MARKER not in rendered
    assert BODY_MARKER not in rendered
