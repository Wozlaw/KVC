"""MAX Mini App initData validation."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl

from pydantic import SecretStr

from kvc_integrations.max.dto import (
    MaxChatType,
    ValidatedMaxMiniAppChat,
    ValidatedMaxMiniAppInitData,
    ValidatedMaxMiniAppUser,
)
from kvc_integrations.max.errors import (
    MaxMiniAppFreshnessError,
    MaxMiniAppPayloadError,
    MaxMiniAppSignatureError,
)

_MALFORMED_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def validate_init_data(
    raw_init_data: str,
    *,
    bot_token: str | SecretStr,
    max_age_seconds: int,
    now: int | None = None,
    future_skew_seconds: int = 60,
    require_user: bool = True,
) -> ValidatedMaxMiniAppInitData:
    """Validate MAX Mini App initData and return a safe normalized DTO."""

    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be non-negative")
    if future_skew_seconds < 0:
        raise ValueError("future_skew_seconds must be non-negative")

    params = _parse_unique_params(raw_init_data)
    supplied_hash = params.pop("hash", None)
    if supplied_hash is None:
        raise MaxMiniAppPayloadError("missing Mini App signature")
    if not _HASH_RE.fullmatch(supplied_hash):
        raise MaxMiniAppSignatureError("invalid Mini App signature")

    data_check_string = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    secret_key = hmac.new(
        b"WebAppData",
        _secret_value(bot_token).encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, supplied_hash.lower()):
        raise MaxMiniAppSignatureError("invalid Mini App signature")

    auth_date = _parse_auth_date(params.get("auth_date"))
    current_time = int(time.time()) if now is None else now
    if auth_date > current_time + future_skew_seconds:
        raise MaxMiniAppFreshnessError("Mini App initData is from the future")
    if current_time - auth_date > max_age_seconds:
        raise MaxMiniAppFreshnessError("Mini App initData is expired")

    user = _parse_user(params.get("user"))
    if user is None and require_user:
        raise MaxMiniAppPayloadError("missing Mini App user payload")
    if user is None:
        raise MaxMiniAppPayloadError("missing Mini App user payload")

    chat = _parse_chat(params.get("chat"))
    return ValidatedMaxMiniAppInitData(
        auth_date=auth_date,
        user=user,
        chat=chat,
        start_param=_blank_to_none(params.get("start_param")),
    )


def _secret_value(secret: str | SecretStr) -> str:
    if isinstance(secret, SecretStr):
        return secret.get_secret_value()
    return secret


def _parse_unique_params(raw_init_data: str) -> dict[str, str]:
    if not raw_init_data:
        raise MaxMiniAppPayloadError("empty Mini App initData")
    if _MALFORMED_PERCENT.search(raw_init_data):
        raise MaxMiniAppPayloadError("invalid Mini App launch parameter encoding")

    try:
        pairs = parse_qsl(
            raw_init_data,
            keep_blank_values=True,
            strict_parsing=True,
            encoding="utf-8",
            errors="strict",
            separator="&",
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise MaxMiniAppPayloadError("invalid Mini App launch parameter encoding") from error

    params: dict[str, str] = {}
    for key, value in pairs:
        if key in params:
            raise MaxMiniAppPayloadError("duplicate Mini App launch parameter")
        params[key] = value
    return params


def _parse_auth_date(value: str | None) -> int:
    if value is None:
        raise MaxMiniAppPayloadError("missing Mini App auth_date")
    try:
        auth_date = int(value)
    except ValueError as error:
        raise MaxMiniAppPayloadError("invalid Mini App auth_date") from error
    if auth_date < 0:
        raise MaxMiniAppPayloadError("invalid Mini App auth_date")
    return auth_date


def _parse_user(value: str | None) -> ValidatedMaxMiniAppUser | None:
    if value is None:
        return None
    payload = _json_object(value, "invalid Mini App user payload")
    user_id = _required_identifier(payload, "id", "invalid Mini App user payload")
    return ValidatedMaxMiniAppUser(max_user_id=user_id)


def _parse_chat(value: str | None) -> ValidatedMaxMiniAppChat | None:
    if value is None:
        return None
    payload = _json_object(value, "invalid Mini App chat payload")
    chat_id = _required_identifier(payload, "id", "invalid Mini App chat payload")
    chat_type = _normalize_chat_type(payload.get("type"))
    return ValidatedMaxMiniAppChat(chat_id=chat_id, chat_type=chat_type)


def _json_object(value: str, error_message: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise MaxMiniAppPayloadError(error_message) from error
    if not isinstance(payload, dict):
        raise MaxMiniAppPayloadError(error_message)
    return payload


def _required_identifier(
    payload: Mapping[str, Any],
    field_name: str,
    error_message: str,
) -> str:
    value = payload.get(field_name)
    if isinstance(value, bool) or value is None:
        raise MaxMiniAppPayloadError(error_message)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value:
        return value
    raise MaxMiniAppPayloadError(error_message)


def _normalize_chat_type(value: object) -> MaxChatType:
    if isinstance(value, str):
        normalized = value.lower()
        if normalized in {"dialog", "private"}:
            return "PRIVATE"
        if normalized == "chat":
            return "GROUP"
        if normalized == "channel":
            return "CHANNEL"
    return "UNKNOWN"


def _blank_to_none(value: str | None) -> str | None:
    if value == "":
        return None
    return value


__all__ = ["validate_init_data"]
