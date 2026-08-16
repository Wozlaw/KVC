"""MAX integration error hierarchy."""


class MaxIntegrationError(Exception):
    """Base MAX integration error."""


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
]
