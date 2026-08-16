"""MAX adapter package."""

from kvc_integrations.max.client import MAX_MESSAGE_TEXT_LIMIT, MaxBotApiClient
from kvc_integrations.max.context_signing import (
    MiniAppContextClaims,
    MiniAppContextPurpose,
    MiniAppContextSigner,
)
from kvc_integrations.max.dto import (
    MaxAttachmentMetadata,
    MaxIncomingUpdate,
    MaxSentMessage,
    MaxTextFormat,
    ValidatedMaxMiniAppChat,
    ValidatedMaxMiniAppInitData,
    ValidatedMaxMiniAppUser,
)
from kvc_integrations.max.errors import (
    MaxApiAuthenticationError,
    MaxApiError,
    MaxApiRateLimitError,
    MaxApiRecipientError,
    MaxApiRequestError,
    MaxApiResponseError,
    MaxApiTemporaryError,
    MaxIntegrationError,
    MaxMiniAppContextError,
    MaxMiniAppValidationError,
    MaxTransportError,
    MaxTransportTimeoutError,
    MaxUpdateParseError,
)
from kvc_integrations.max.message_sender import MaxMessageSender
from kvc_integrations.max.mini_app_validation import validate_init_data
from kvc_integrations.max.update_parser import SUPPORTED_UPDATE_TYPES, parse_max_update

__all__ = [
    "MAX_MESSAGE_TEXT_LIMIT",
    "MaxApiAuthenticationError",
    "MaxApiError",
    "MaxApiRateLimitError",
    "MaxApiRecipientError",
    "MaxApiRequestError",
    "MaxApiResponseError",
    "MaxApiTemporaryError",
    "MaxAttachmentMetadata",
    "MaxBotApiClient",
    "MaxIncomingUpdate",
    "MaxIntegrationError",
    "MaxMessageSender",
    "MaxMiniAppContextError",
    "MaxMiniAppValidationError",
    "MaxSentMessage",
    "MaxTextFormat",
    "MaxTransportError",
    "MaxTransportTimeoutError",
    "MaxUpdateParseError",
    "MiniAppContextClaims",
    "MiniAppContextPurpose",
    "MiniAppContextSigner",
    "SUPPORTED_UPDATE_TYPES",
    "ValidatedMaxMiniAppChat",
    "ValidatedMaxMiniAppInitData",
    "ValidatedMaxMiniAppUser",
    "parse_max_update",
    "validate_init_data",
]
