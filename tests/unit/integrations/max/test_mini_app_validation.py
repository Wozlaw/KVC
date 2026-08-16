"""MAX Mini App initData validation tests."""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest
from pydantic import SecretStr

from kvc_integrations.max.errors import (
    MaxMiniAppFreshnessError,
    MaxMiniAppPayloadError,
    MaxMiniAppSignatureError,
)
from kvc_integrations.max.mini_app_validation import validate_init_data

BOT_TOKEN = "synthetic-bot-token"
AUTH_DATE = 1_700_000_000
FIXED_HASH = "6e77c7ed6fbf92b48bcda4106c648e02fa7f853f01e71c37b3f69886a5cdb944"
FIXED_INIT_DATA = (
    "auth_date=1700000000&"
    "chat=%7B%22id%22%3A456%2C%22type%22%3A%22dialog%22%7D&"
    "start_param=connect_ctx&"
    "user=%7B%22id%22%3A123%7D&"
    f"hash={FIXED_HASH}"
)


def _signed_init_data(params: dict[str, str], *, bot_token: str) -> str:
    data_check_string = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(params) + f"&hash={signature}"


def test_validate_init_data_accepts_fixed_synthetic_regression_vector() -> None:
    result = validate_init_data(
        FIXED_INIT_DATA,
        bot_token=SecretStr(BOT_TOKEN),
        max_age_seconds=900,
        now=AUTH_DATE + 10,
    )

    assert result.auth_date == AUTH_DATE
    assert result.max_user_id == "123"
    assert result.chat_id == "456"
    assert result.chat_type == "PRIVATE"
    assert result.start_param == "connect_ctx"
    assert "hash" not in result.__dataclass_fields__


def test_validate_init_data_uses_decoded_values_for_signature() -> None:
    raw = _signed_init_data(
        {
            "auth_date": str(AUTH_DATE),
            "user": json.dumps({"id": "user with space"}, separators=(",", ":")),
            "chat": json.dumps({"id": "chat+plus", "type": "dialog"}, separators=(",", ":")),
            "start_param": "ctx with space",
        },
        bot_token=BOT_TOKEN,
    )

    result = validate_init_data(raw, bot_token=BOT_TOKEN, max_age_seconds=900, now=AUTH_DATE)

    assert result.max_user_id == "user with space"
    assert result.chat_id == "chat+plus"
    assert result.start_param == "ctx with space"


@pytest.mark.parametrize(
    ("raw", "error_type"),
    [
        ("auth_date=1700000000&user=%7B%22id%22%3A123%7D", MaxMiniAppPayloadError),
        (
            "auth_date=1700000000&user=%7B%22id%22%3A123%7D&hash=a&hash=b",
            MaxMiniAppPayloadError,
        ),
        (
            "auth_date=1700000000&auth_date=1700000001&user=%7B%22id%22%3A123%7D&hash="
            + FIXED_HASH,
            MaxMiniAppPayloadError,
        ),
        ("auth_date=bad&user=%7B%22id%22%3A123%7D&hash=" + FIXED_HASH, MaxMiniAppSignatureError),
        (_signed_init_data({"user": '{"id":123}'}, bot_token=BOT_TOKEN), MaxMiniAppPayloadError),
        (
            _signed_init_data({"auth_date": str(AUTH_DATE), "user": "{bad"}, bot_token=BOT_TOKEN),
            MaxMiniAppPayloadError,
        ),
        (
            _signed_init_data(
                {
                    "auth_date": str(AUTH_DATE),
                    "user": '{"id":123}',
                    "chat": "{bad",
                },
                bot_token=BOT_TOKEN,
            ),
            MaxMiniAppPayloadError,
        ),
    ],
)
def test_validate_init_data_rejects_invalid_payloads(
    raw: str,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        validate_init_data(raw, bot_token=BOT_TOKEN, max_age_seconds=900, now=AUTH_DATE)


def test_validate_init_data_rejects_signature_mismatch() -> None:
    raw = FIXED_INIT_DATA.replace(FIXED_HASH, "0" * 64)

    with pytest.raises(MaxMiniAppSignatureError, match="signature") as caught:
        validate_init_data(raw, bot_token=BOT_TOKEN, max_age_seconds=900, now=AUTH_DATE)

    assert FIXED_INIT_DATA not in str(caught.value)


def test_validate_init_data_rejects_wrong_bot_token() -> None:
    with pytest.raises(MaxMiniAppSignatureError):
        validate_init_data(
            FIXED_INIT_DATA, bot_token="wrong-token", max_age_seconds=900, now=AUTH_DATE
        )


def test_validate_init_data_rejects_expired_auth_date() -> None:
    with pytest.raises(MaxMiniAppFreshnessError):
        validate_init_data(
            FIXED_INIT_DATA,
            bot_token=BOT_TOKEN,
            max_age_seconds=900,
            now=AUTH_DATE + 901,
        )


def test_validate_init_data_rejects_future_auth_date_beyond_skew() -> None:
    with pytest.raises(MaxMiniAppFreshnessError):
        validate_init_data(
            FIXED_INIT_DATA,
            bot_token=BOT_TOKEN,
            max_age_seconds=900,
            now=AUTH_DATE - 61,
        )


def test_validate_init_data_rejects_malformed_percent_encoding() -> None:
    with pytest.raises(MaxMiniAppPayloadError):
        validate_init_data(
            "auth_date=1700000000&user=%ZZ&hash=" + FIXED_HASH,
            bot_token=BOT_TOKEN,
            max_age_seconds=900,
            now=AUTH_DATE,
        )


def test_validate_init_data_exception_does_not_include_raw_init_data() -> None:
    with pytest.raises(MaxMiniAppSignatureError) as caught:
        validate_init_data(
            FIXED_INIT_DATA, bot_token="wrong-token", max_age_seconds=900, now=AUTH_DATE
        )

    assert FIXED_INIT_DATA not in str(caught.value)
    assert FIXED_HASH not in str(caught.value)
