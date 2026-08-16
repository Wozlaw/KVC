"""MAX Mini App routes for Kaiten credential onboarding."""

from __future__ import annotations

import ipaddress
import time
from collections.abc import MutableMapping
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.staticfiles import StaticFiles

from kvc_api.max.runtime import MaxMiniAppRuntime
from kvc_application.dto import BindKaitenConnectionInput, ResolveMaxIdentityInput
from kvc_application.errors import (
    CredentialEncryptionFailed,
    IdentityConflict,
    KaitenAuthenticationFailed,
    KaitenTemporarilyUnavailable,
    KaitenVerificationFailed,
    PersistenceConflict,
    UserDisabled,
)
from kvc_config import AppSettings
from kvc_integrations.max.context_signing import MiniAppContextClaims, MiniAppContextPurpose
from kvc_integrations.max.errors import (
    MaxApiError,
    MaxMiniAppContextError,
    MaxMiniAppContextExpiredError,
    MaxMiniAppContextPurposeError,
    MaxMiniAppFreshnessError,
    MaxMiniAppPayloadError,
    MaxMiniAppSignatureError,
)
from kvc_integrations.max.mini_app_validation import validate_init_data

MAX_MINI_APP_STATIC_PATH = "/max/app/static"
MAX_MINI_APP_CONNECT_PATH = "/max/app/connect"
MAX_MINI_APP_CONNECT_API_PATH = "/max/app/api/connect"
MAX_MINI_APP_INIT_DATA_MAX_AGE_SECONDS = 900
MAX_KAITEN_TOKEN_MAX_LENGTH = 8192
MAX_KAITEN_API_BASE_URL_LENGTH = 2048
MAX_CONTEXT_REF_MAX_LENGTH = 512
MAX_BRIDGE_SCRIPT_URL = "https://st.max.ru/js/max-web-app.js"

_STATIC_DIRECTORY = Path(__file__).with_name("static")
_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    f"script-src 'self' {MAX_BRIDGE_SCRIPT_URL}; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "base-uri 'none'; "
    "form-action 'self'"
)
_ALLOWED_CONNECT_PURPOSES = (
    MiniAppContextPurpose.CONNECT_KAITEN,
    MiniAppContextPurpose.RECONNECT_KAITEN,
)
_SUCCESS_TEXT = "Kaiten подключен. Можно вернуться в чат."


class KaitenApiBaseUrlValidationError(ValueError):
    """Raised when a submitted Kaiten API base URL is not safe to verify."""


class MaxMiniAppStaticFiles(StaticFiles):
    """Static files with conservative browser headers for Mini App assets."""

    async def get_response(self, path: str, scope: MutableMapping[str, Any]) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def create_max_mini_app_static_files() -> MaxMiniAppStaticFiles:
    """Create the bounded static files app for MAX Mini App local assets."""

    return MaxMiniAppStaticFiles(directory=_STATIC_DIRECTORY, html=False)


def create_max_mini_app_router(
    *,
    settings: AppSettings,
    runtime: MaxMiniAppRuntime | None,
) -> APIRouter:
    """Create MAX Mini App HTML and credential onboarding API routes."""

    router = APIRouter()

    @router.get(MAX_MINI_APP_CONNECT_PATH)
    async def connect_page() -> Response:
        return _html_response(_connect_html())

    @router.post(MAX_MINI_APP_CONNECT_API_PATH)
    async def connect_api(request: Request) -> Response:
        if settings.max_bot_token is None or settings.max_mini_app_context_secret is None:
            return _json_response({"status": "configuration_error"}, status_code=503)
        if runtime is None:
            return _json_response({"status": "unavailable"}, status_code=503)

        try:
            payload = await request.json()
        except JSONDecodeError:
            return _json_response({"status": "invalid_json"}, status_code=400)
        if not isinstance(payload, dict):
            return _json_response({"status": "invalid_input"}, status_code=400)

        try:
            init_data = _required_string(payload, "init_data", max_length=8192)
            context_ref = _required_string(
                payload,
                "context_ref",
                max_length=MAX_CONTEXT_REF_MAX_LENGTH,
            )
            api_base_url = _validate_kaiten_api_base_url(
                _required_string(
                    payload,
                    "api_base_url",
                    max_length=MAX_KAITEN_API_BASE_URL_LENGTH,
                )
            )
            plaintext_token = _required_string(
                payload,
                "token",
                max_length=MAX_KAITEN_TOKEN_MAX_LENGTH,
            )
        except (KaitenApiBaseUrlValidationError, ValueError):
            return _json_response({"status": "invalid_input"}, status_code=400)

        try:
            launch = validate_init_data(
                init_data,
                bot_token=settings.max_bot_token,
                max_age_seconds=MAX_MINI_APP_INIT_DATA_MAX_AGE_SECONDS,
            )
        except MaxMiniAppFreshnessError:
            return _json_response({"status": "expired_launch"}, status_code=409)
        except (MaxMiniAppPayloadError, MaxMiniAppSignatureError):
            return _json_response({"status": "invalid_launch"}, status_code=403)

        if launch.chat_type != "PRIVATE" or launch.chat_id is None:
            return _json_response({"status": "private_chat_required"}, status_code=403)
        if launch.start_param is not None and launch.start_param != context_ref:
            return _json_response({"status": "invalid_context"}, status_code=403)

        identity_binding = runtime.context_signer.make_identity_binding(
            max_user_id=launch.max_user_id,
            chat_id=launch.chat_id,
        )
        try:
            claims = _verify_allowed_context(
                runtime=runtime,
                context_ref=context_ref,
                identity_binding=identity_binding,
            )
        except MaxMiniAppContextExpiredError:
            return _json_response({"status": "expired_context"}, status_code=409)
        except MaxMiniAppContextError:
            return _json_response({"status": "invalid_context"}, status_code=403)

        try:
            identity = (
                await runtime.identity_resolver_factory().resolve_or_onboard_private_max_user(
                    ResolveMaxIdentityInput(
                        max_user_id=launch.max_user_id,
                        max_chat_id=launch.chat_id,
                        chat_type="PRIVATE",
                    )
                )
            )
        except IdentityConflict:
            return _json_response({"status": "identity_conflict"}, status_code=409)
        except PersistenceConflict:
            return _json_response({"status": "temporary_failure"}, status_code=503)

        if identity.user_status == "DISABLED":
            _clear_secret(payload)
            return _json_response({"status": "user_disabled"}, status_code=403)

        try:
            result = await runtime.kaiten_connection_binder_factory().bind_or_replace_connection(
                BindKaitenConnectionInput(
                    user_id=identity.user_id,
                    api_base_url=api_base_url,
                    plaintext_token=plaintext_token,
                )
            )
        except UserDisabled:
            return _json_response({"status": "user_disabled"}, status_code=403)
        except KaitenAuthenticationFailed:
            return _json_response({"status": "kaiten_auth_failed"}, status_code=400)
        except KaitenTemporarilyUnavailable:
            return _json_response({"status": "kaiten_unavailable"}, status_code=503)
        except KaitenVerificationFailed:
            return _json_response({"status": "kaiten_verification_failed"}, status_code=502)
        except CredentialEncryptionFailed:
            return _json_response({"status": "secure_store_failed"}, status_code=500)
        except PersistenceConflict:
            return _json_response({"status": "temporary_failure"}, status_code=503)
        finally:
            plaintext_token = ""
            _clear_secret(payload)

        confirmation_status = "sent"
        try:
            await runtime.message_sender.send_text_to_chat(
                chat_id=launch.chat_id,
                text=_SUCCESS_TEXT,
                notify=True,
            )
        except MaxApiError:
            confirmation_status = "failed"

        return _json_response(
            {
                "status": "connected",
                "mode": _mode_for_purpose(claims.purpose),
                "connection_status": result.status,
                "confirmation_status": confirmation_status,
            },
            status_code=200,
        )

    return router


def _verify_allowed_context(
    *,
    runtime: MaxMiniAppRuntime,
    context_ref: str,
    identity_binding: str,
) -> MiniAppContextClaims:
    purpose_error: MaxMiniAppContextPurposeError | None = None
    for purpose in _ALLOWED_CONNECT_PURPOSES:
        try:
            return runtime.context_signer.verify(
                context_ref,
                expected_purpose=purpose,
                expected_identity_binding=identity_binding,
                now=int(time.time()),
            )
        except MaxMiniAppContextPurposeError as exc:
            purpose_error = exc
    if purpose_error is not None:
        raise purpose_error
    raise MaxMiniAppContextError("invalid Mini App context")


def _mode_for_purpose(purpose: MiniAppContextPurpose) -> str:
    if purpose is MiniAppContextPurpose.RECONNECT_KAITEN:
        return "reconnected"
    return "connected"


def _required_string(payload: dict[Any, Any], field_name: str, *, max_length: int) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise ValueError("invalid input")
    value = value.strip()
    if value == "" or len(value) > max_length:
        raise ValueError("invalid input")
    return value


def _validate_kaiten_api_base_url(raw_value: str) -> str:
    try:
        url = httpx.URL(raw_value)
    except httpx.InvalidURL as exc:
        raise KaitenApiBaseUrlValidationError("invalid Kaiten API base URL") from exc

    if url.scheme != "https" or url.host is None:
        raise KaitenApiBaseUrlValidationError("invalid Kaiten API base URL")
    if url.userinfo or url.query or url.fragment:
        raise KaitenApiBaseUrlValidationError("invalid Kaiten API base URL")
    if _is_disallowed_host(url.host):
        raise KaitenApiBaseUrlValidationError("invalid Kaiten API base URL")
    normalized = str(url).rstrip("/")
    if normalized == "https:":
        raise KaitenApiBaseUrlValidationError("invalid Kaiten API base URL")
    return normalized


def _is_disallowed_host(host: str) -> bool:
    normalized = host.strip("[]").lower().rstrip(".")
    if normalized in {"localhost", "metadata.google.internal"}:
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _clear_secret(payload: dict[Any, Any]) -> None:
    if "token" in payload:
        payload["token"] = ""


def _html_response(content: str) -> HTMLResponse:
    response = HTMLResponse(content)
    _apply_security_headers(response)
    response.headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
    return response


def _json_response(content: dict[str, str], *, status_code: int) -> JSONResponse:
    response = JSONResponse(content, status_code=status_code)
    _apply_security_headers(response)
    return response


def _apply_security_headers(response: Response) -> None:
    for name, value in _SECURITY_HEADERS.items():
        response.headers[name] = value


def _connect_html() -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kaiten</title>
  <link rel="stylesheet" href="{MAX_MINI_APP_STATIC_PATH}/app.css">
  <script src="{MAX_BRIDGE_SCRIPT_URL}" defer></script>
  <script src="{MAX_MINI_APP_STATIC_PATH}/app.js" defer></script>
</head>
<body>
  <main class="shell">
    <section class="panel" aria-labelledby="connect-title">
      <div class="mark" aria-hidden="true">K</div>
      <h1 id="connect-title">Подключение Kaiten</h1>
      <p class="summary">Введите адрес API и токен доступа Kaiten.</p>
      <form id="connect-form" autocomplete="off" novalidate>
        <label for="api-base-url">Адрес API Kaiten</label>
        <input
          id="api-base-url"
          name="api_base_url"
          type="url"
          inputmode="url"
          autocomplete="off"
          spellcheck="false"
          placeholder="https://example.kaiten.ru/api/latest"
          required
        >
        <label for="kaiten-token">Токен Kaiten</label>
        <input
          id="kaiten-token"
          name="token"
          type="password"
          autocomplete="off"
          spellcheck="false"
          required
        >
        <button id="submit-button" type="submit">Подключить</button>
      </form>
      <p id="status" class="status" role="status" aria-live="polite"></p>
      <button id="return-button" class="secondary" type="button" hidden>Вернуться</button>
    </section>
  </main>
</body>
</html>
"""


__all__ = [
    "MAX_MINI_APP_CONNECT_API_PATH",
    "MAX_MINI_APP_CONNECT_PATH",
    "MAX_MINI_APP_STATIC_PATH",
    "KaitenApiBaseUrlValidationError",
    "MaxMiniAppStaticFiles",
    "create_max_mini_app_router",
    "create_max_mini_app_static_files",
]
