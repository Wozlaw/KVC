"""Raw MAX update parser."""

from __future__ import annotations

from collections.abc import Mapping

from kvc_integrations.max.dto import (
    MaxAttachmentMetadata,
    MaxChatType,
    MaxIncomingUpdate,
    MaxUpdateSource,
)
from kvc_integrations.max.errors import MaxUpdateParseError

SUPPORTED_UPDATE_TYPES = ("message_created", "message_callback", "bot_started")


def parse_max_update(
    raw_update: object,
    *,
    source: MaxUpdateSource = "webhook",
) -> MaxIncomingUpdate:
    """Normalize a raw MAX Update object into the provider-boundary DTO."""

    update = _mapping(raw_update, "invalid MAX update payload")
    update_type = _required_str(update, "update_type", "missing MAX update type")
    timestamp = _optional_int(update.get("timestamp"), "invalid MAX update timestamp")

    if update_type == "message_created":
        return _parse_message_created(update, source=source, timestamp=timestamp)
    if update_type == "message_callback":
        return _parse_message_callback(update, source=source, timestamp=timestamp)
    if update_type == "bot_started":
        return _parse_bot_started(update, source=source, timestamp=timestamp)

    return MaxIncomingUpdate(
        source=source,
        update_type=update_type,
        timestamp=timestamp,
        raw_event_type=update_type,
        chat_id=_optional_str(update.get("chat_id"), "invalid MAX update chat id"),
        chat_type=_chat_type_from_update(update),
        max_user_id=_optional_user_id(update.get("user")),
        message_id=None,
        message_text=None,
        message_timestamp=None,
        callback_payload=None,
        attachments=(),
    )


def _parse_message_created(
    update: Mapping[str, object],
    *,
    source: MaxUpdateSource,
    timestamp: int | None,
) -> MaxIncomingUpdate:
    message = _mapping(update.get("message"), "invalid MAX message payload")
    sender = _mapping(message.get("sender"), "invalid MAX message sender")
    recipient = _mapping(message.get("recipient"), "invalid MAX message recipient")
    body = _mapping(message.get("body"), "invalid MAX message body")

    return MaxIncomingUpdate(
        source=source,
        update_type="message_created",
        timestamp=timestamp,
        raw_event_type="message_created",
        chat_id=_required_str(recipient, "chat_id", "invalid MAX message recipient"),
        chat_type=_chat_type_from_recipient(recipient),
        max_user_id=_required_str(sender, "user_id", "invalid MAX message sender"),
        message_id=_optional_str(body.get("mid"), "invalid MAX message id"),
        message_text=_optional_str(body.get("text"), "invalid MAX message text"),
        message_timestamp=_optional_int(message.get("timestamp"), "invalid MAX message timestamp"),
        callback_payload=None,
        attachments=_parse_attachments(body.get("attachments")),
    )


def _parse_message_callback(
    update: Mapping[str, object],
    *,
    source: MaxUpdateSource,
    timestamp: int | None,
) -> MaxIncomingUpdate:
    callback = _mapping(update.get("callback"), "invalid MAX callback payload")
    sender = _mapping(callback.get("sender"), "invalid MAX callback sender")
    message = _mapping(callback.get("message"), "invalid MAX callback message")
    recipient = _mapping(message.get("recipient"), "invalid MAX callback recipient")
    body = _optional_mapping(message.get("body"), "invalid MAX callback message body")

    callback_payload = _optional_str(callback.get("payload"), "invalid MAX callback payload")
    if callback_payload is None:
        callback_payload = _optional_str(callback.get("callback_id"), "invalid MAX callback id")

    return MaxIncomingUpdate(
        source=source,
        update_type="message_callback",
        timestamp=timestamp,
        raw_event_type="message_callback",
        chat_id=_required_str(recipient, "chat_id", "invalid MAX callback recipient"),
        chat_type=_chat_type_from_recipient(recipient),
        max_user_id=_required_str(sender, "user_id", "invalid MAX callback sender"),
        message_id=_optional_str(
            body.get("mid") if body is not None else None,
            "invalid MAX message id",
        ),
        message_text=None,
        message_timestamp=_optional_int(message.get("timestamp"), "invalid MAX message timestamp"),
        callback_payload=callback_payload,
        attachments=(),
    )


def _parse_bot_started(
    update: Mapping[str, object],
    *,
    source: MaxUpdateSource,
    timestamp: int | None,
) -> MaxIncomingUpdate:
    user = _mapping(update.get("user"), "invalid MAX bot_started user")
    start_payload = _optional_str(update.get("payload"), "invalid MAX bot_started payload")

    return MaxIncomingUpdate(
        source=source,
        update_type="bot_started",
        timestamp=timestamp,
        raw_event_type="bot_started",
        chat_id=_required_str(update, "chat_id", "invalid MAX bot_started chat id"),
        chat_type="PRIVATE",
        max_user_id=_required_str(user, "user_id", "invalid MAX bot_started user"),
        message_id=None,
        message_text=None,
        message_timestamp=None,
        callback_payload=None,
        start_payload=start_payload,
        attachments=(),
    )


def _parse_attachments(value: object) -> tuple[MaxAttachmentMetadata, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise MaxUpdateParseError("invalid MAX message attachments")

    attachments: list[MaxAttachmentMetadata] = []
    for item in value:
        attachment = _mapping(item, "invalid MAX message attachment")
        attachment_type = _required_str(
            attachment,
            "type",
            "invalid MAX message attachment",
        )
        payload = _optional_mapping(attachment.get("payload"), "invalid MAX message attachment")
        attachment_id = None
        if payload is not None:
            attachment_id = _first_optional_str(payload, ("token", "photo_id", "id", "code"))
        name = _first_optional_str(attachment, ("filename", "name"))
        size = _optional_int(attachment.get("size"), "invalid MAX message attachment")
        attachments.append(
            MaxAttachmentMetadata(
                attachment_type=attachment_type,
                attachment_id=attachment_id,
                name=name,
                size=size,
            )
        )
    return tuple(attachments)


def _chat_type_from_update(update: Mapping[str, object]) -> MaxChatType:
    if update.get("is_channel") is True:
        return "CHANNEL"
    return "UNKNOWN"


def _chat_type_from_recipient(recipient: Mapping[str, object]) -> MaxChatType:
    raw_type = recipient.get("chat_type", recipient.get("type"))
    if raw_type == "dialog":
        return "PRIVATE"
    if raw_type == "chat":
        return "GROUP"
    if raw_type == "channel":
        return "CHANNEL"
    return "UNKNOWN"


def _mapping(value: object, message: str) -> Mapping[str, object]:
    if isinstance(value, dict):
        return value
    raise MaxUpdateParseError(message)


def _optional_mapping(value: object, message: str) -> Mapping[str, object] | None:
    if value is None:
        return None
    return _mapping(value, message)


def _required_str(data: Mapping[str, object], key: str, message: str) -> str:
    value = data.get(key)
    parsed = _optional_str(value, message)
    if parsed is None or parsed == "":
        raise MaxUpdateParseError(message)
    return parsed


def _optional_str(value: object, message: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise MaxUpdateParseError(message)
    if isinstance(value, int | str):
        return str(value)
    raise MaxUpdateParseError(message)


def _optional_int(value: object, message: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise MaxUpdateParseError(message)
    return value


def _optional_user_id(value: object) -> str | None:
    if value is None:
        return None
    user = _mapping(value, "invalid MAX update user")
    return _optional_str(user.get("user_id"), "invalid MAX update user")


def _first_optional_str(data: Mapping[str, object], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        parsed = _optional_str(data.get(key), "invalid MAX message attachment")
        if parsed:
            return parsed
    return None


__all__ = ["SUPPORTED_UPDATE_TYPES", "parse_max_update"]
