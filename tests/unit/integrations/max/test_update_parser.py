"""MAX raw update parser tests."""

from __future__ import annotations

import pytest

from kvc_integrations.max import MaxUpdateParseError, parse_max_update

BODY_MARKER = "SYNTHETIC-RAW-BODY-MUST-NOT-LEAK"


def message_created_update(*, chat_type: str = "dialog") -> dict[str, object]:
    return {
        "update_type": "message_created",
        "timestamp": 1_700_000_000_000,
        "message": {
            "sender": {"user_id": 123, "name": "Synthetic User"},
            "recipient": {"chat_id": 456, "chat_type": chat_type},
            "timestamp": 1_700_000_000_001,
            "body": {
                "mid": "mid-1",
                "text": "/start",
                "attachments": [
                    {
                        "type": "file",
                        "payload": {"token": "synthetic-attachment-token"},
                        "filename": "report.txt",
                        "size": 42,
                    }
                ],
            },
        },
        "irrelevant": {"ignored": True},
    }


def test_parse_message_created_private_with_attachment_metadata() -> None:
    parsed = parse_max_update(message_created_update())

    assert parsed.source == "webhook"
    assert parsed.update_type == "message_created"
    assert parsed.raw_event_type == "message_created"
    assert parsed.timestamp == 1_700_000_000_000
    assert parsed.chat_id == "456"
    assert parsed.chat_type == "PRIVATE"
    assert parsed.max_user_id == "123"
    assert parsed.message_id == "mid-1"
    assert parsed.message_text == "/start"
    assert parsed.message_timestamp == 1_700_000_000_001
    assert parsed.callback_payload is None
    assert parsed.attachments[0].attachment_type == "file"
    assert parsed.attachments[0].attachment_id == "synthetic-attachment-token"
    assert parsed.attachments[0].name == "report.txt"
    assert parsed.attachments[0].size == 42
    assert "message" not in parsed.__dataclass_fields__


def test_parse_message_created_reuses_same_contract_for_long_polling_source() -> None:
    raw_update = message_created_update()

    webhook = parse_max_update(raw_update, source="webhook")
    long_polling = parse_max_update(raw_update, source="long_polling")

    assert webhook.source == "webhook"
    assert long_polling.source == "long_polling"
    assert {
        **webhook.__dict__,
        "source": "long_polling",
    } == long_polling.__dict__


@pytest.mark.parametrize(
    ("raw_chat_type", "normalized"),
    [
        ("dialog", "PRIVATE"),
        ("chat", "GROUP"),
        ("channel", "CHANNEL"),
        ("other", "UNKNOWN"),
    ],
)
def test_parse_message_created_chat_type_normalization(
    raw_chat_type: str,
    normalized: str,
) -> None:
    parsed = parse_max_update(message_created_update(chat_type=raw_chat_type))

    assert parsed.chat_type == normalized


def test_parse_message_callback_payload_and_message_context() -> None:
    parsed = parse_max_update(
        {
            "update_type": "message_callback",
            "timestamp": 1_700_000_000_000,
            "callback": {
                "callback_id": "callback-1",
                "payload": "connect",
                "sender": {"user_id": 123},
                "message": {
                    "recipient": {"chat_id": 456, "chat_type": "dialog"},
                    "timestamp": 1_700_000_000_001,
                    "body": {"mid": "mid-1"},
                },
            },
        }
    )

    assert parsed.update_type == "message_callback"
    assert parsed.chat_id == "456"
    assert parsed.chat_type == "PRIVATE"
    assert parsed.max_user_id == "123"
    assert parsed.message_id == "mid-1"
    assert parsed.callback_payload == "connect"
    assert parsed.message_timestamp == 1_700_000_000_001


def test_parse_message_callback_falls_back_to_callback_id() -> None:
    parsed = parse_max_update(
        {
            "update_type": "message_callback",
            "callback": {
                "callback_id": "callback-1",
                "sender": {"user_id": 123},
                "message": {"recipient": {"chat_id": 456, "chat_type": "dialog"}},
            },
        }
    )

    assert parsed.callback_payload == "callback-1"


def test_parse_bot_started_as_private_start_event() -> None:
    parsed = parse_max_update(
        {
            "update_type": "bot_started",
            "timestamp": 1_700_000_000_000,
            "chat_id": 456,
            "user": {"user_id": 123},
            "payload": "promo_2026",
        }
    )

    assert parsed.update_type == "bot_started"
    assert parsed.chat_id == "456"
    assert parsed.chat_type == "PRIVATE"
    assert parsed.max_user_id == "123"
    assert parsed.message_text is None
    assert parsed.callback_payload is None
    assert parsed.start_payload == "promo_2026"


def test_parse_unknown_update_type_minimally() -> None:
    parsed = parse_max_update(
        {
            "update_type": "bot_stopped",
            "timestamp": 1_700_000_000_000,
            "chat_id": 456,
            "user": {"user_id": 123},
            "is_channel": True,
        }
    )

    assert parsed.update_type == "bot_stopped"
    assert parsed.chat_id == "456"
    assert parsed.chat_type == "CHANNEL"
    assert parsed.max_user_id == "123"
    assert parsed.message_text is None


@pytest.mark.parametrize(
    "raw_update",
    [
        [],
        {"timestamp": 1_700_000_000_000},
        {"update_type": True},
        {"update_type": "message_created", "message": []},
        {"update_type": "message_created", "message": {"sender": [], "recipient": {}, "body": {}}},
        {
            "update_type": "message_created",
            "message": {"sender": {"user_id": 1}, "recipient": [], "body": {}},
        },
        {
            "update_type": "message_created",
            "message": {"sender": {"user_id": 1}, "recipient": {"chat_id": 1}, "body": []},
        },
        {
            "update_type": "message_callback",
            "callback": {"sender": {"user_id": 1}, "message": []},
        },
        {"update_type": "bot_started", "chat_id": 1, "user": []},
    ],
)
def test_parse_rejects_malformed_payloads_without_raw_body(raw_update: object) -> None:
    with pytest.raises(MaxUpdateParseError) as caught:
        parse_max_update(raw_update)

    assert BODY_MARKER not in f"{caught.value!s} {caught.value!r}"


def test_parse_error_does_not_include_raw_message_text() -> None:
    raw_update = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": 1},
            "recipient": {"chat_id": 2, "chat_type": "dialog"},
            "body": {"text": BODY_MARKER, "attachments": "bad"},
        },
    }

    with pytest.raises(MaxUpdateParseError) as caught:
        parse_max_update(raw_update)

    assert BODY_MARKER not in f"{caught.value!s} {caught.value!r}"
