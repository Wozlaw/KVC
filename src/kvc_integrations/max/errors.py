"""MAX integration error hierarchy."""


class MaxIntegrationError(Exception):
    """Base MAX integration error."""


class MaxUpdateParseError(MaxIntegrationError):
    """Raised when a raw MAX update cannot be normalized safely."""


class MaxApiError(MaxIntegrationError):
    """Base safe MAX Bot API error."""

    retryable = False

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after_seconds: int | None = None,
        operation: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.operation = operation


class MaxApiAuthenticationError(MaxApiError):
    """Raised when MAX Bot API authentication or permission fails."""


class MaxApiRequestError(MaxApiError):
    """Raised when MAX Bot API rejects a non-retryable request."""


class MaxApiRecipientError(MaxApiRequestError):
    """Raised when MAX Bot API reports a stale or unknown recipient/resource."""


class MaxApiRateLimitError(MaxApiError):
    """Raised when MAX Bot API reports rate limiting."""

    retryable = True


class MaxApiTemporaryError(MaxApiError):
    """Raised when MAX Bot API is temporarily unavailable."""

    retryable = True


class MaxApiResponseError(MaxApiError):
    """Raised when MAX Bot API returns an unexpected success payload."""


class MaxTransportError(MaxApiError):
    """Raised when MAX Bot API cannot be reached."""

    retryable = True


class MaxTransportTimeoutError(MaxTransportError):
    """Raised when MAX Bot API request times out."""


class MaxMiniAppValidationError(MaxIntegrationError):
    """Raised when MAX Mini App launch data cannot be trusted."""


class MaxMiniAppSignatureError(MaxMiniAppValidationError):
    """Raised when MAX Mini App launch data signature is invalid."""


class MaxMiniAppFreshnessError(MaxMiniAppValidationError):
    """Raised when MAX Mini App launch data is stale or from the future."""


class MaxMiniAppPayloadError(MaxMiniAppValidationError):
    """Raised when MAX Mini App launch data has invalid shape."""


class MaxMiniAppContextError(MaxIntegrationError):
    """Raised when a signed MAX Mini App context cannot be trusted."""


class MaxMiniAppContextSignatureError(MaxMiniAppContextError):
    """Raised when a Mini App context token signature is invalid."""


class MaxMiniAppContextExpiredError(MaxMiniAppContextError):
    """Raised when a Mini App context token is expired or not yet valid."""


class MaxMiniAppContextPurposeError(MaxMiniAppContextError):
    """Raised when a Mini App context token has an unexpected purpose."""


class MaxMiniAppContextBindingError(MaxMiniAppContextError):
    """Raised when a Mini App context token has an unexpected identity binding."""


class MaxMiniAppContextPayloadError(MaxMiniAppContextError):
    """Raised when a Mini App context token payload has invalid shape."""


__all__ = [
    "MaxApiAuthenticationError",
    "MaxApiError",
    "MaxApiRateLimitError",
    "MaxApiRecipientError",
    "MaxApiRequestError",
    "MaxApiResponseError",
    "MaxApiTemporaryError",
    "MaxIntegrationError",
    "MaxMiniAppContextBindingError",
    "MaxMiniAppContextError",
    "MaxMiniAppContextExpiredError",
    "MaxMiniAppContextPayloadError",
    "MaxMiniAppContextPurposeError",
    "MaxMiniAppContextSignatureError",
    "MaxMiniAppFreshnessError",
    "MaxMiniAppPayloadError",
    "MaxMiniAppSignatureError",
    "MaxMiniAppValidationError",
    "MaxTransportError",
    "MaxTransportTimeoutError",
    "MaxUpdateParseError",
]
