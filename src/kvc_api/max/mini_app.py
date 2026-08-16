"""MAX Mini App routes for Kaiten credential onboarding."""

from __future__ import annotations

import ipaddress
import time
from collections.abc import MutableMapping
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.staticfiles import StaticFiles

from kvc_api.max.response_text import NOTIFICATIONS_SAVED_TEXT
from kvc_api.max.runtime import MaxMiniAppRuntime
from kvc_application.dto import (
    CONTEXT_INTERACTION_MAX_OPTION_ID_LENGTH,
    CONTEXT_INTERACTION_MAX_RESULT_MESSAGE_LENGTH,
    BindKaitenConnectionInput,
    ContextInteractionOption,
    ContextInteractionResult,
    ContextInteractionView,
    NotificationSettingsResult,
    ResolveMaxIdentityInput,
    UpdateNotificationSettingsInput,
    validate_context_interaction_workflow_ref,
)
from kvc_application.errors import (
    ContextInteractionAlreadyCompleted,
    ContextInteractionExpired,
    ContextInteractionInvalidSelection,
    ContextInteractionMissing,
    CredentialEncryptionFailed,
    IdentityConflict,
    InvalidNotificationSettings,
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
MAX_MINI_APP_NOTIFICATIONS_PATH = "/max/app/notifications"
MAX_MINI_APP_NOTIFICATIONS_API_PATH = "/max/app/api/notifications"
MAX_MINI_APP_CONTEXT_PATH = "/max/app/context"
MAX_MINI_APP_CONTEXT_API_PATH = "/max/app/api/context"
MAX_MINI_APP_CONTEXT_CANCEL_API_PATH = "/max/app/api/context/cancel"
MAX_MINI_APP_INIT_DATA_MAX_AGE_SECONDS = 900
MAX_MINI_APP_NOTIFICATIONS_INIT_DATA_MAX_AGE_SECONDS = 3600
MAX_MINI_APP_CONTEXT_INIT_DATA_MAX_AGE_SECONDS = 3600
MAX_KAITEN_TOKEN_MAX_LENGTH = 8192
MAX_KAITEN_API_BASE_URL_LENGTH = 2048
MAX_CONTEXT_REF_MAX_LENGTH = 512
MAX_INIT_DATA_HEADER = "X-KVC-Max-Init-Data"
MAX_MINI_APP_CONTEXT_HEADER = "X-KVC-Mini-App-Context"
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

    @router.get(MAX_MINI_APP_NOTIFICATIONS_PATH)
    async def notifications_page() -> Response:
        return _html_response(_notifications_html())

    @router.get(MAX_MINI_APP_CONTEXT_PATH)
    async def context_page() -> Response:
        return _html_response(_context_html())

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

    @router.get(MAX_MINI_APP_NOTIFICATIONS_API_PATH)
    async def get_notifications_api(request: Request) -> Response:
        trust = await _validated_notification_trust(
            request=request,
            settings=settings,
            runtime=runtime,
        )
        if isinstance(trust, Response):
            return trust

        assert runtime is not None
        assert runtime.notification_settings_service_factory is not None
        settings_service = runtime.notification_settings_service_factory()
        try:
            result = await settings_service.get_settings(trust.user_id)
        except UserDisabled:
            return _json_response({"status": "user_disabled"}, status_code=403)
        except PersistenceConflict:
            return _json_response({"status": "temporary_failure"}, status_code=503)
        return _json_response(_settings_payload(result), status_code=200)

    @router.post(MAX_MINI_APP_NOTIFICATIONS_API_PATH)
    async def post_notifications_api(request: Request) -> Response:
        trust = await _validated_notification_trust(
            request=request,
            settings=settings,
            runtime=runtime,
        )
        if isinstance(trust, Response):
            return trust

        assert runtime is not None
        assert runtime.notification_settings_service_factory is not None
        settings_service = runtime.notification_settings_service_factory()
        try:
            payload = await request.json()
        except JSONDecodeError:
            return _json_response({"status": "invalid_json"}, status_code=400)
        if not isinstance(payload, dict) or set(payload) != {
            "enabled",
            "due_soon_days",
            "timezone",
        }:
            return _json_response({"status": "invalid_settings"}, status_code=400)

        try:
            result = await settings_service.update_settings(
                UpdateNotificationSettingsInput(
                    user_id=trust.user_id,
                    enabled=payload["enabled"],
                    due_soon_days=payload["due_soon_days"],
                    timezone=payload["timezone"],
                )
            )
        except InvalidNotificationSettings:
            return _json_response({"status": "invalid_settings"}, status_code=400)
        except UserDisabled:
            return _json_response({"status": "user_disabled"}, status_code=403)
        except PersistenceConflict:
            return _json_response({"status": "temporary_failure"}, status_code=503)

        confirmation_status = "sent"
        try:
            await runtime.message_sender.send_text_to_chat(
                chat_id=trust.chat_id,
                text=_notification_confirmation_text(result),
                notify=True,
            )
        except MaxApiError:
            confirmation_status = "failed"

        return _json_response(
            {
                "status": "saved",
                "settings": _settings_payload(result),
                "confirmation_status": confirmation_status,
            },
            status_code=200,
        )

    @router.get(MAX_MINI_APP_CONTEXT_API_PATH)
    async def get_context_api(request: Request) -> Response:
        trust = await _validated_context_interaction_trust(
            request=request,
            settings=settings,
            runtime=runtime,
        )
        if isinstance(trust, Response):
            return trust

        assert runtime is not None
        assert runtime.context_interaction_resolver_factory is not None
        resolver = runtime.context_interaction_resolver_factory()
        try:
            view = await resolver.get_interaction(
                user_id=trust.user_id,
                workflow_ref=trust.workflow_ref,
            )
            payload = _context_interaction_view_payload(
                view,
                expected_workflow_ref=trust.workflow_ref,
            )
        except ContextInteractionMissing:
            return _json_response({"status": "interaction_missing"}, status_code=404)
        except ContextInteractionExpired:
            return _json_response({"status": "interaction_expired"}, status_code=409)
        except ContextInteractionAlreadyCompleted:
            return _json_response({"status": "interaction_completed"}, status_code=409)
        except PersistenceConflict:
            return _json_response({"status": "temporary_failure"}, status_code=503)
        except ValueError:
            return _json_response({"status": "invalid_interaction"}, status_code=503)
        return _json_response(payload, status_code=200)

    @router.post(MAX_MINI_APP_CONTEXT_API_PATH)
    async def post_context_api(request: Request) -> Response:
        trust = await _validated_context_interaction_trust(
            request=request,
            settings=settings,
            runtime=runtime,
        )
        if isinstance(trust, Response):
            return trust

        try:
            payload = await request.json()
        except JSONDecodeError:
            return _json_response({"status": "invalid_json"}, status_code=400)
        if not isinstance(payload, dict) or set(payload) != {"selected_option_id"}:
            return _json_response({"status": "invalid_selection"}, status_code=400)
        try:
            option_id = _required_string(
                payload,
                "selected_option_id",
                max_length=CONTEXT_INTERACTION_MAX_OPTION_ID_LENGTH,
            )
        except ValueError:
            return _json_response({"status": "invalid_selection"}, status_code=400)

        assert runtime is not None
        assert runtime.context_interaction_resolver_factory is not None
        resolver = runtime.context_interaction_resolver_factory()
        try:
            result = await resolver.submit_selection(
                user_id=trust.user_id,
                workflow_ref=trust.workflow_ref,
                option_id=option_id,
            )
            response_payload = await _context_interaction_result_payload(
                result,
                chat_id=trust.chat_id,
                runtime=runtime,
            )
        except ContextInteractionInvalidSelection:
            return _json_response({"status": "invalid_selection"}, status_code=400)
        except ContextInteractionMissing:
            return _json_response({"status": "interaction_missing"}, status_code=404)
        except ContextInteractionExpired:
            return _json_response({"status": "interaction_expired"}, status_code=409)
        except ContextInteractionAlreadyCompleted:
            return _json_response({"status": "interaction_completed"}, status_code=409)
        except UserDisabled:
            return _json_response({"status": "user_disabled"}, status_code=403)
        except PersistenceConflict:
            return _json_response({"status": "temporary_failure"}, status_code=503)
        except ValueError:
            return _json_response({"status": "invalid_interaction"}, status_code=503)
        return _json_response(response_payload, status_code=200)

    @router.post(MAX_MINI_APP_CONTEXT_CANCEL_API_PATH)
    async def cancel_context_api(request: Request) -> Response:
        trust = await _validated_context_interaction_trust(
            request=request,
            settings=settings,
            runtime=runtime,
        )
        if isinstance(trust, Response):
            return trust

        assert runtime is not None
        assert runtime.context_interaction_resolver_factory is not None
        resolver = runtime.context_interaction_resolver_factory()
        try:
            result = await resolver.cancel_interaction(
                user_id=trust.user_id,
                workflow_ref=trust.workflow_ref,
            )
            response_payload = await _context_interaction_result_payload(
                result,
                chat_id=trust.chat_id,
                runtime=runtime,
            )
        except ContextInteractionInvalidSelection:
            return _json_response({"status": "invalid_selection"}, status_code=400)
        except ContextInteractionMissing:
            return _json_response({"status": "interaction_missing"}, status_code=404)
        except ContextInteractionExpired:
            return _json_response({"status": "interaction_expired"}, status_code=409)
        except ContextInteractionAlreadyCompleted:
            return _json_response({"status": "interaction_completed"}, status_code=409)
        except UserDisabled:
            return _json_response({"status": "user_disabled"}, status_code=403)
        except PersistenceConflict:
            return _json_response({"status": "temporary_failure"}, status_code=503)
        except ValueError:
            return _json_response({"status": "invalid_interaction"}, status_code=503)
        return _json_response(response_payload, status_code=200)

    return router


@dataclass(frozen=True)
class _NotificationTrust:
    user_id: UUID
    chat_id: str


@dataclass(frozen=True)
class _ContextInteractionTrust:
    user_id: UUID
    chat_id: str
    workflow_ref: str


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


async def _validated_notification_trust(
    *,
    request: Request,
    settings: AppSettings,
    runtime: MaxMiniAppRuntime | None,
) -> _NotificationTrust | Response:
    if settings.max_bot_token is None or settings.max_mini_app_context_secret is None:
        return _json_response({"status": "configuration_error"}, status_code=503)
    if runtime is None or runtime.notification_settings_service_factory is None:
        return _json_response({"status": "unavailable"}, status_code=503)

    try:
        init_data = _required_header(
            request,
            MAX_INIT_DATA_HEADER,
            max_length=8192,
        )
        context_ref = _required_header(
            request,
            MAX_MINI_APP_CONTEXT_HEADER,
            max_length=MAX_CONTEXT_REF_MAX_LENGTH,
        )
    except ValueError:
        return _json_response({"status": "invalid_launch"}, status_code=403)

    try:
        launch = validate_init_data(
            init_data,
            bot_token=settings.max_bot_token,
            max_age_seconds=MAX_MINI_APP_NOTIFICATIONS_INIT_DATA_MAX_AGE_SECONDS,
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
        runtime.context_signer.verify(
            context_ref,
            expected_purpose=MiniAppContextPurpose.NOTIFICATION_SETTINGS,
            expected_identity_binding=identity_binding,
            now=int(time.time()),
        )
    except MaxMiniAppContextExpiredError:
        return _json_response({"status": "expired_context"}, status_code=409)
    except MaxMiniAppContextError:
        return _json_response({"status": "invalid_context"}, status_code=403)

    try:
        identity = await runtime.identity_resolver_factory().resolve_or_onboard_private_max_user(
            ResolveMaxIdentityInput(
                max_user_id=launch.max_user_id,
                max_chat_id=launch.chat_id,
                chat_type="PRIVATE",
            )
        )
    except IdentityConflict:
        return _json_response({"status": "identity_conflict"}, status_code=409)
    except PersistenceConflict:
        return _json_response({"status": "temporary_failure"}, status_code=503)

    if identity.user_status == "DISABLED":
        return _json_response({"status": "user_disabled"}, status_code=403)
    return _NotificationTrust(user_id=identity.user_id, chat_id=launch.chat_id)


async def _validated_context_interaction_trust(
    *,
    request: Request,
    settings: AppSettings,
    runtime: MaxMiniAppRuntime | None,
) -> _ContextInteractionTrust | Response:
    if settings.max_bot_token is None or settings.max_mini_app_context_secret is None:
        return _json_response({"status": "configuration_error"}, status_code=503)
    if runtime is None or runtime.context_interaction_resolver_factory is None:
        return _json_response({"status": "interaction_unavailable"}, status_code=503)

    try:
        init_data = _required_header(
            request,
            MAX_INIT_DATA_HEADER,
            max_length=8192,
        )
        context_ref = _required_header(
            request,
            MAX_MINI_APP_CONTEXT_HEADER,
            max_length=MAX_CONTEXT_REF_MAX_LENGTH,
        )
    except ValueError:
        return _json_response({"status": "invalid_launch"}, status_code=403)

    try:
        launch = validate_init_data(
            init_data,
            bot_token=settings.max_bot_token,
            max_age_seconds=MAX_MINI_APP_CONTEXT_INIT_DATA_MAX_AGE_SECONDS,
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
        claims = runtime.context_signer.verify(
            context_ref,
            expected_purpose=MiniAppContextPurpose.SYNTHETIC_CONTEXT,
            expected_identity_binding=identity_binding,
            now=int(time.time()),
        )
        if claims.workflow_ref is None:
            raise MaxMiniAppContextError("missing Mini App context workflow")
        workflow_ref = validate_context_interaction_workflow_ref(claims.workflow_ref)
    except MaxMiniAppContextExpiredError:
        return _json_response({"status": "expired_context"}, status_code=409)
    except (MaxMiniAppContextError, ValueError):
        return _json_response({"status": "invalid_context"}, status_code=403)

    try:
        identity = await runtime.identity_resolver_factory().resolve_or_onboard_private_max_user(
            ResolveMaxIdentityInput(
                max_user_id=launch.max_user_id,
                max_chat_id=launch.chat_id,
                chat_type="PRIVATE",
            )
        )
    except IdentityConflict:
        return _json_response({"status": "identity_conflict"}, status_code=409)
    except PersistenceConflict:
        return _json_response({"status": "temporary_failure"}, status_code=503)

    if identity.user_status == "DISABLED":
        return _json_response({"status": "user_disabled"}, status_code=403)
    return _ContextInteractionTrust(
        user_id=identity.user_id,
        chat_id=launch.chat_id,
        workflow_ref=workflow_ref,
    )


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


def _required_header(request: Request, field_name: str, *, max_length: int) -> str:
    value = request.headers.get(field_name)
    if value is None:
        raise ValueError("missing header")
    value = value.strip()
    if value == "" or len(value) > max_length:
        raise ValueError("invalid header")
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


def _json_response(content: dict[str, object], *, status_code: int) -> JSONResponse:
    response = JSONResponse(content, status_code=status_code)
    _apply_security_headers(response)
    return response


def _settings_payload(result: NotificationSettingsResult) -> dict[str, object]:
    return {
        "enabled": result.enabled,
        "due_soon_days": result.due_soon_days,
        "timezone": result.timezone,
    }


def _context_interaction_view_payload(
    view: ContextInteractionView,
    *,
    expected_workflow_ref: str,
) -> dict[str, object]:
    if not isinstance(view, ContextInteractionView):
        raise ValueError("invalid context interaction view")
    if view.workflow_ref != expected_workflow_ref:
        raise ValueError("context interaction workflow mismatch")
    return {
        "title": view.title,
        "prompt": view.prompt,
        "options": [_context_interaction_option_payload(option) for option in view.options],
        "allow_cancel": view.allow_cancel,
    }


def _context_interaction_option_payload(
    option: ContextInteractionOption,
) -> dict[str, object]:
    return {
        "id": option.option_id,
        "label": option.label,
        "description": option.description,
    }


async def _context_interaction_result_payload(
    result: ContextInteractionResult,
    *,
    chat_id: str,
    runtime: MaxMiniAppRuntime,
) -> dict[str, object]:
    if not isinstance(result, ContextInteractionResult):
        raise ValueError("invalid context interaction result")
    confirmation_status = "not_required"
    if result.message is not None:
        if len(result.message) > CONTEXT_INTERACTION_MAX_RESULT_MESSAGE_LENGTH:
            raise ValueError("context interaction message is too long")
        confirmation_status = "sent"
        try:
            await runtime.message_sender.send_text_to_chat(
                chat_id=chat_id,
                text=result.message,
                notify=True,
            )
        except MaxApiError:
            confirmation_status = "failed"
    return {
        "status": result.status,
        "confirmation_status": confirmation_status,
    }


def _notification_confirmation_text(result: NotificationSettingsResult) -> str:
    if not result.enabled:
        return "Настройки уведомлений сохранены. Уведомления выключены."
    return f"{NOTIFICATIONS_SAVED_TEXT} Напоминать за {result.due_soon_days} дн."


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


def _notifications_html() -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Уведомления KVC</title>
  <link rel="stylesheet" href="{MAX_MINI_APP_STATIC_PATH}/app.css">
  <script src="{MAX_BRIDGE_SCRIPT_URL}" defer></script>
  <script src="{MAX_MINI_APP_STATIC_PATH}/notifications.js" defer></script>
</head>
<body>
  <main class="shell">
    <section class="panel" aria-labelledby="notifications-title">
      <div class="mark" aria-hidden="true">K</div>
      <h1 id="notifications-title">Уведомления</h1>
      <p class="summary">Настройте напоминания о сроках Kaiten.</p>
      <form id="notifications-form" autocomplete="off" novalidate>
        <label class="switch-row" for="enabled">
          <span>Включить уведомления</span>
          <input id="enabled" name="enabled" type="checkbox">
        </label>
        <label for="due-soon-days">Напоминать за дней</label>
        <input
          id="due-soon-days"
          name="due_soon_days"
          type="number"
          inputmode="numeric"
          min="0"
          max="30"
          step="1"
          required
        >
        <label for="timezone">Часовой пояс</label>
        <input
          id="timezone"
          name="timezone"
          type="text"
          autocomplete="off"
          spellcheck="false"
          placeholder="Europe/Warsaw"
          required
        >
        <button id="save-button" type="submit">Сохранить</button>
      </form>
      <p id="status" class="status" role="status" aria-live="polite">Загрузка...</p>
      <button id="return-button" class="secondary" type="button">Вернуться</button>
    </section>
  </main>
</body>
</html>
"""


def _context_html() -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KVC</title>
  <link rel="stylesheet" href="{MAX_MINI_APP_STATIC_PATH}/app.css">
  <script src="{MAX_BRIDGE_SCRIPT_URL}" defer></script>
  <script src="{MAX_MINI_APP_STATIC_PATH}/context.js" defer></script>
</head>
<body>
  <main class="shell">
    <section class="panel" aria-labelledby="context-title">
      <div class="mark" aria-hidden="true">K</div>
      <h1 id="context-title">Выбор действия</h1>
      <p id="context-prompt" class="summary">Загрузка...</p>
      <form id="context-form" autocomplete="off" novalidate>
        <fieldset id="context-options" class="option-list" disabled></fieldset>
        <button id="continue-button" type="submit" disabled>Продолжить</button>
      </form>
      <p id="status" class="status" role="status" aria-live="polite"></p>
      <button id="cancel-button" class="secondary" type="button" hidden>Отменить</button>
      <button id="return-button" class="secondary" type="button">Вернуться</button>
    </section>
  </main>
</body>
</html>
"""


__all__ = [
    "MAX_MINI_APP_CONNECT_API_PATH",
    "MAX_MINI_APP_CONNECT_PATH",
    "MAX_MINI_APP_CONTEXT_API_PATH",
    "MAX_MINI_APP_CONTEXT_CANCEL_API_PATH",
    "MAX_MINI_APP_CONTEXT_HEADER",
    "MAX_MINI_APP_CONTEXT_PATH",
    "MAX_MINI_APP_NOTIFICATIONS_API_PATH",
    "MAX_MINI_APP_NOTIFICATIONS_PATH",
    "MAX_INIT_DATA_HEADER",
    "MAX_MINI_APP_STATIC_PATH",
    "KaitenApiBaseUrlValidationError",
    "MaxMiniAppStaticFiles",
    "create_max_mini_app_router",
    "create_max_mini_app_static_files",
]
