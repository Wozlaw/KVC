"""Kaiten credential verification adapter."""

from __future__ import annotations

from typing import Any

import httpx

from kvc_application.dto import KaitenCredentialVerification
from kvc_application.errors import (
    KaitenAuthenticationFailed,
    KaitenTemporarilyUnavailable,
    KaitenVerificationFailed,
)


class KaitenHttpCredentialVerifier:
    """Verify Kaiten credentials through the current-user REST endpoint."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def verify(
        self,
        *,
        api_base_url: str,
        plaintext_token: str,
    ) -> KaitenCredentialVerification:
        url = api_base_url.rstrip("/") + "/users/current"
        try:
            response = await self._client.get(
                url,
                headers={"Authorization": f"Bearer {plaintext_token}"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise KaitenTemporarilyUnavailable(
                "Kaiten credential verification unavailable"
            ) from exc

        if response.status_code in {401, 403}:
            raise KaitenAuthenticationFailed("Kaiten credential rejected")
        if response.status_code in {408, 429} or response.status_code >= 500:
            raise KaitenTemporarilyUnavailable("Kaiten credential verification unavailable")
        if response.status_code != 200:
            raise KaitenVerificationFailed("Unexpected Kaiten verification status")

        try:
            payload: object = response.json()
        except ValueError as exc:
            raise KaitenVerificationFailed("Unexpected Kaiten verification response") from exc

        if not isinstance(payload, dict):
            raise KaitenVerificationFailed("Unexpected Kaiten verification response")

        kaiten_user_id = self._parse_user_id(payload.get("id"))
        return KaitenCredentialVerification(
            kaiten_user_id=kaiten_user_id,
            workspace_id=None,
        )

    def _parse_user_id(self, value: Any) -> str:
        if isinstance(value, bool):
            raise KaitenVerificationFailed("Unexpected Kaiten verification response")
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str) and value != "":
            return value
        raise KaitenVerificationFailed("Unexpected Kaiten verification response")
