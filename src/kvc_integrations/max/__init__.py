"""MAX adapter package."""

from kvc_integrations.max.client import (
    MAX_MESSAGE_TEXT_LIMIT,
    MAX_UPDATES_LIMIT_MAX,
    MAX_UPDATES_LIMIT_MIN,
    MAX_UPDATES_TIMEOUT_MAX,
    MAX_UPDATES_TIMEOUT_MIN,
    MaxBotApiClient,
)
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
    MaxUpdatesBatch,
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
from kvc_integrations.max.long_polling import (
    MaxLongPollingRunner,
    MaxLongPollingRunResult,
    MaxLongPollingSource,
    SleepCallable,
)
from kvc_integrations.max.message_sender import MaxMessageSender
from kvc_integrations.max.mini_app_validation import validate_init_data
from kvc_integrations.max.update_parser import SUPPORTED_UPDATE_TYPES, parse_max_update

__all__ = [
    "MAX_MESSAGE_TEXT_LIMIT",
    "MAX_UPDATES_LIMIT_MAX",
    "MAX_UPDATES_LIMIT_MIN",
    "MAX_UPDATES_TIMEOUT_MAX",
    "MAX_UPDATES_TIMEOUT_MIN",
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
    "MaxLongPollingRunResult",
    "MaxLongPollingRunner",
    "MaxLongPollingSource",
    "MaxUpdatesBatch",
    "MiniAppContextClaims",
    "MiniAppContextPurpose",
    "MiniAppContextSigner",
    "SUPPORTED_UPDATE_TYPES",
    "SleepCallable",
    "ValidatedMaxMiniAppChat",
    "ValidatedMaxMiniAppInitData",
    "ValidatedMaxMiniAppUser",
    "parse_max_update",
    "validate_init_data",
]
