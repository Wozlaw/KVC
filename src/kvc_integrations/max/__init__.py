"""MAX adapter package."""

from kvc_integrations.max.context_signing import (
    MiniAppContextClaims,
    MiniAppContextPurpose,
    MiniAppContextSigner,
)
from kvc_integrations.max.dto import (
    MaxAttachmentMetadata,
    MaxIncomingUpdate,
    ValidatedMaxMiniAppChat,
    ValidatedMaxMiniAppInitData,
    ValidatedMaxMiniAppUser,
)
from kvc_integrations.max.errors import (
    MaxIntegrationError,
    MaxMiniAppContextError,
    MaxMiniAppValidationError,
)
from kvc_integrations.max.mini_app_validation import validate_init_data

__all__ = [
    "MaxAttachmentMetadata",
    "MaxIncomingUpdate",
    "MaxIntegrationError",
    "MaxMiniAppContextError",
    "MaxMiniAppValidationError",
    "MiniAppContextClaims",
    "MiniAppContextPurpose",
    "MiniAppContextSigner",
    "ValidatedMaxMiniAppChat",
    "ValidatedMaxMiniAppInitData",
    "ValidatedMaxMiniAppUser",
    "validate_init_data",
]
