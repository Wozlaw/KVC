"""MAX webhook security helpers."""

from __future__ import annotations

import hmac

from pydantic import SecretStr

MAX_WEBHOOK_SECRET_HEADER = "X-Max-Bot-Api-Secret"


def validate_webhook_secret(
    *,
    configured_secret: SecretStr | None,
    supplied_secret: str | None,
) -> bool:
    """Validate the optional MAX webhook secret using constant-time comparison."""

    if configured_secret is None:
        return True
    if supplied_secret is None:
        return False
    expected = configured_secret.get_secret_value()
    return hmac.compare_digest(supplied_secret, expected)


__all__ = ["MAX_WEBHOOK_SECRET_HEADER", "validate_webhook_secret"]
