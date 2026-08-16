"""MAX provider DTO tests."""

from kvc_integrations.max.dto import (
    MaxAttachmentMetadata,
    MaxIncomingUpdate,
    ValidatedMaxMiniAppChat,
    ValidatedMaxMiniAppInitData,
    ValidatedMaxMiniAppUser,
)


def test_max_incoming_update_is_small_immutable_provider_dto() -> None:
    attachment = MaxAttachmentMetadata(
        attachment_type="image",
        attachment_id="synthetic-attachment-id",
        name="image.png",
        size=123,
    )
    update = MaxIncomingUpdate(
        source="webhook",
        update_type="message_created",
        timestamp=1_700_000_000,
        raw_event_type="message_created",
        chat_id="456",
        chat_type="PRIVATE",
        max_user_id="123",
        message_id="mid.1",
        message_text="/start",
        message_timestamp=1_700_000_001,
        callback_payload=None,
        attachments=(attachment,),
    )

    assert update.attachments == (attachment,)
    assert "raw" not in update.__dataclass_fields__
    assert "authorization" not in update.__dataclass_fields__


def test_validated_init_data_exposes_minimal_identity_helpers() -> None:
    dto = ValidatedMaxMiniAppInitData(
        auth_date=1_700_000_000,
        user=ValidatedMaxMiniAppUser(max_user_id="123"),
        chat=ValidatedMaxMiniAppChat(chat_id="456", chat_type="PRIVATE"),
        start_param="connect",
    )

    assert dto.max_user_id == "123"
    assert dto.chat_id == "456"
    assert dto.chat_type == "PRIVATE"
