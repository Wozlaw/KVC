"""MAX Mini App contextual interaction route tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from kvc_api.main import create_app
from kvc_api.max.mini_app import (
    MAX_INIT_DATA_HEADER,
    MAX_MINI_APP_CONTEXT_HEADER,
)
from kvc_api.max.runtime import MaxMiniAppRuntime
from kvc_application.dto import (
    ContextInteractionOption,
    ContextInteractionResult,
    ContextInteractionView,
    IdentityResolution,
)
from kvc_application.errors import (
    ContextInteractionAlreadyCompleted,
    ContextInteractionExpired,
    ContextInteractionInvalidSelection,
    ContextInteractionMissing,
    IdentityConflict,
    PersistenceConflict,
    UserDisabled,
)
from kvc_config import AppSettings
from kvc_integrations.max.context_signing import MiniAppContextPurpose, MiniAppContextSigner
from kvc_integrations.max.errors import MaxApiTemporaryError

BOT_TOKEN = "synthetic-bot-token"
CONTEXT_SECRET = "synthetic-context-secret"
MAX_USER_ID = "max-user-888"
MAX_CHAT_ID = "max-chat-888"
USER_ID = UUID("00000000-0000-0000-0000-000000000881")
BINDING_ID = UUID("00000000-0000-0000-0000-000000000882")
WORKFLOW_REF = "synthetic-choice-001"
INIT_MARKER = "SYNTHETIC_INIT_MARKER_DO_NOT_LEAK"
CONTEXT_MARKER = "SYNTHETIC_CONTEXT_MARKER_DO_NOT_LEAK"


class FakeIdentityResolver:
    def __init__(
        self,
        *,
        user_status: str = "ACTIVE",
        exc: Exception | None = None,
    ) -> None:
        self.user_status = user_status
        self.exc = exc
        self.calls: list[object] = []

    async def resolve_or_onboard_private_max_user(self, input: object) -> IdentityResolution:
        self.calls.append(input)
        if self.exc is not None:
            raise self.exc
        return IdentityResolution(
            user_id=USER_ID,
            max_chat_binding_id=BINDING_ID,
            user_status="DISABLED" if self.user_status == "DISABLED" else "ACTIVE",
            is_new_user=False,
            kaiten_connection_status="ACTIVE",
        )


class FakeContextResolver:
    def __init__(
        self,
        *,
        view: ContextInteractionView | object | None = None,
        exc: Exception | None = None,
        result_message: str | None = "Выбор принят.",
    ) -> None:
        self.view = view or _view()
        self.exc = exc
        self.result_message = result_message
        self.completed = False
        self.get_calls: list[tuple[UUID, str]] = []
        self.submit_calls: list[tuple[UUID, str, str]] = []
        self.cancel_calls: list[tuple[UUID, str]] = []

    async def get_interaction(
        self,
        *,
        user_id: UUID,
        workflow_ref: str,
    ) -> ContextInteractionView:
        self.get_calls.append((user_id, workflow_ref))
        if self.exc is not None:
            raise self.exc
        if self.completed:
            raise ContextInteractionAlreadyCompleted("synthetic")
        return self.view  # type: ignore[return-value]

    async def submit_selection(
        self,
        *,
        user_id: UUID,
        workflow_ref: str,
        option_id: str,
    ) -> ContextInteractionResult:
        self.submit_calls.append((user_id, workflow_ref, option_id))
        if self.exc is not None:
            raise self.exc
        if self.completed:
            raise ContextInteractionAlreadyCompleted("synthetic")
        valid_ids = {option.option_id for option in self.view.options}  # type: ignore[attr-defined]
        if option_id not in valid_ids:
            raise ContextInteractionInvalidSelection("synthetic")
        self.completed = True
        return ContextInteractionResult("completed", self.result_message)

    async def cancel_interaction(
        self,
        *,
        user_id: UUID,
        workflow_ref: str,
    ) -> ContextInteractionResult:
        self.cancel_calls.append((user_id, workflow_ref))
        if self.exc is not None:
            raise self.exc
        if self.completed:
            raise ContextInteractionAlreadyCompleted("synthetic")
        if not self.view.allow_cancel:  # type: ignore[attr-defined]
            raise ContextInteractionInvalidSelection("synthetic")
        self.completed = True
        return ContextInteractionResult("cancelled", self.result_message)


class FakeSender:
    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc
        self.calls: list[dict[str, object]] = []

    async def send_text_to_chat(
        self,
        *,
        chat_id: str,
        text: str,
        notify: bool = True,
    ) -> object:
        self.calls.append({"chat_id": chat_id, "text": text, "notify": notify})
        if self.exc is not None:
            raise self.exc
        return object()


def test_context_page_serves_mobile_shell_bridge_assets_and_safe_headers() -> None:
    client = TestClient(create_app(_settings()))

    response = client.get("/max/app/context")

    assert response.status_code == 200
    assert '<meta name="viewport"' in response.text
    assert "https://st.max.ru/js/max-web-app.js" in response.text
    assert "/max/app/static/app.css" in response.text
    assert "/max/app/static/context.js" in response.text
    assert 'id="context-options"' in response.text
    assert 'id="continue-button"' in response.text
    assert 'id="cancel-button"' in response.text
    assert 'aria-live="polite"' in response.text
    assert str(USER_ID) not in response.text
    assert WORKFLOW_REF not in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors" not in response.headers["Content-Security-Policy"]
    assert "X-Frame-Options" not in response.headers


def test_context_script_uses_safe_dom_headers_and_no_storage_logs_or_kaiten() -> None:
    script = Path("src/kvc_api/max/static/context.js").read_text(encoding="utf-8")

    assert "/max/app/api/context" in script
    assert "/max/app/api/context/cancel" in script
    assert "X-KVC-Max-Init-Data" in script
    assert "X-KVC-Mini-App-Context" in script
    assert 'credentials: "same-origin"' in script
    assert "initData" in script
    assert "start_param" in script
    assert "textContent" in script
    assert "createElement" in script
    for forbidden in (
        "innerHTML",
        "insertAdjacentHTML",
        "eval(",
        "initDataUnsafe",
        "localStorage",
        "sessionStorage",
        "IndexedDB",
        "console.",
        "kaiten",
    ):
        assert forbidden not in script


def test_context_token_with_workflow_ref_is_max_safe_and_bounded() -> None:
    context_ref = _context_ref()

    assert len(context_ref) <= 512
    assert re.fullmatch(r"^[A-Za-z0-9_-]+$", context_ref)

    signer = MiniAppContextSigner(CONTEXT_SECRET)
    binding = signer.make_identity_binding(max_user_id=MAX_USER_ID, chat_id=MAX_CHAT_ID)
    claims = signer.verify(
        context_ref,
        expected_purpose=MiniAppContextPurpose.SYNTHETIC_CONTEXT,
        expected_identity_binding=binding,
        now=int(time.time()),
    )
    assert claims.workflow_ref == WORKFLOW_REF


def test_get_context_returns_only_bounded_visual_fields() -> None:
    resolver = FakeContextResolver()
    client = _client(context_resolver=resolver)
    context_ref = _context_ref()

    response = client.get("/max/app/api/context", headers=_headers(context_ref))

    assert response.status_code == 200
    assert response.json() == {
        "title": "Выберите карточку",
        "prompt": "Найдены несколько вариантов.",
        "options": [
            {"id": "one", "label": "Первый вариант", "description": "Описание"},
            {"id": "two", "label": "Второй вариант", "description": None},
        ],
        "allow_cancel": True,
    }
    assert resolver.get_calls == [(USER_ID, WORKFLOW_REF)]
    assert set(response.json()) == {"title", "prompt", "options", "allow_cancel"}
    assert str(USER_ID) not in response.text
    assert MAX_USER_ID not in response.text
    assert MAX_CHAT_ID not in response.text
    assert WORKFLOW_REF not in response.text
    assert context_ref not in response.text


def test_get_context_serializes_untrusted_text_only_as_json_values() -> None:
    resolver = FakeContextResolver(
        view=ContextInteractionView(
            WORKFLOW_REF,
            "<script>alert(1)</script>",
            "Выберите <b>не HTML</b>",
            [ContextInteractionOption("one", "<img src=x>", "Описание <svg>")],
        )
    )
    client = _client(context_resolver=resolver)
    context_ref = _context_ref()

    response = client.get("/max/app/api/context", headers=_headers(context_ref))

    assert response.status_code == 200
    assert response.json()["title"] == "<script>alert(1)</script>"
    assert "&lt;script" not in response.text


def test_post_context_submits_selection_and_confirms_once() -> None:
    resolver = FakeContextResolver()
    sender = FakeSender()
    client = _client(context_resolver=resolver, sender=sender)
    context_ref = _context_ref()

    response = client.post(
        "/max/app/api/context",
        headers=_headers(context_ref),
        json={"selected_option_id": "two"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "completed", "confirmation_status": "sent"}
    assert resolver.submit_calls == [(USER_ID, WORKFLOW_REF, "two")]
    assert sender.calls == [{"chat_id": MAX_CHAT_ID, "text": "Выбор принят.", "notify": True}]

    duplicate = client.post(
        "/max/app/api/context",
        headers=_headers(context_ref),
        json={"selected_option_id": "two"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"status": "interaction_completed"}


def test_post_context_without_message_does_not_send_confirmation() -> None:
    resolver = FakeContextResolver(result_message=None)
    sender = FakeSender()
    client = _client(context_resolver=resolver, sender=sender)
    context_ref = _context_ref()

    response = client.post(
        "/max/app/api/context",
        headers=_headers(context_ref),
        json={"selected_option_id": "one"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "completed", "confirmation_status": "not_required"}
    assert sender.calls == []


def test_confirmation_failure_does_not_retry_or_expose_message() -> None:
    resolver = FakeContextResolver()
    sender = FakeSender(exc=MaxApiTemporaryError("synthetic"))
    client = _client(context_resolver=resolver, sender=sender)
    context_ref = _context_ref()

    response = client.post(
        "/max/app/api/context",
        headers=_headers(context_ref),
        json={"selected_option_id": "one"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "completed", "confirmation_status": "failed"}
    assert len(sender.calls) == 1
    assert "Выбор принят." not in response.text


def test_cancel_context_uses_explicit_endpoint() -> None:
    resolver = FakeContextResolver()
    sender = FakeSender()
    client = _client(context_resolver=resolver, sender=sender)
    context_ref = _context_ref()

    response = client.post("/max/app/api/context/cancel", headers=_headers(context_ref))

    assert response.status_code == 200
    assert response.json() == {"status": "cancelled", "confirmation_status": "sent"}
    assert resolver.cancel_calls == [(USER_ID, WORKFLOW_REF)]
    assert sender.calls == [{"chat_id": MAX_CHAT_ID, "text": "Выбор принят.", "notify": True}]


def test_invalid_selection_and_unknown_body_are_rejected() -> None:
    resolver = FakeContextResolver()
    client = _client(context_resolver=resolver)
    context_ref = _context_ref()

    wrong_option = client.post(
        "/max/app/api/context",
        headers=_headers(context_ref),
        json={"selected_option_id": "missing"},
    )
    unknown_field = client.post(
        "/max/app/api/context",
        headers=_headers(context_ref),
        json={"selected_option_id": "one", "workflow_ref": WORKFLOW_REF},
    )

    assert wrong_option.status_code == 400
    assert wrong_option.json() == {"status": "invalid_selection"}
    assert unknown_field.status_code == 400
    assert unknown_field.json() == {"status": "invalid_selection"}


def test_resolver_terminal_errors_map_safely() -> None:
    for exc, expected_status, expected_body in [
        (ContextInteractionMissing("synthetic"), 404, {"status": "interaction_missing"}),
        (ContextInteractionExpired("synthetic"), 409, {"status": "interaction_expired"}),
        (
            ContextInteractionAlreadyCompleted("synthetic"),
            409,
            {"status": "interaction_completed"},
        ),
        (PersistenceConflict("synthetic"), 503, {"status": "temporary_failure"}),
        (UserDisabled("synthetic"), 403, {"status": "user_disabled"}),
    ]:
        resolver = FakeContextResolver(exc=exc)
        client = _client(context_resolver=resolver)
        context_ref = _context_ref()

        response = client.post(
            "/max/app/api/context",
            headers=_headers(context_ref),
            json={"selected_option_id": "one"},
        )

        assert response.status_code == expected_status
        assert response.json() == expected_body


def test_invalid_launch_or_context_does_not_call_services_or_leak_headers(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    identity = FakeIdentityResolver()
    resolver = FakeContextResolver()
    client = _client(identity=identity, context_resolver=resolver)

    response = client.get(
        "/max/app/api/context",
        headers={
            MAX_INIT_DATA_HEADER: f"bad={INIT_MARKER}",
            MAX_MINI_APP_CONTEXT_HEADER: CONTEXT_MARKER,
        },
    )

    assert response.status_code == 403
    assert response.json() == {"status": "invalid_launch"}
    assert identity.calls == []
    assert resolver.get_calls == []
    assert INIT_MARKER not in response.text
    assert CONTEXT_MARKER not in response.text
    captured = capsys.readouterr()
    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert INIT_MARKER not in captured.out
    assert INIT_MARKER not in captured.err
    assert INIT_MARKER not in rendered_logs
    assert CONTEXT_MARKER not in captured.out
    assert CONTEXT_MARKER not in captured.err
    assert CONTEXT_MARKER not in rendered_logs


def test_wrong_context_purpose_user_chat_missing_workflow_and_non_private_rejected() -> None:
    client = _client()
    wrong_purpose = _context_ref(purpose=MiniAppContextPurpose.NOTIFICATION_SETTINGS)
    wrong_user = _context_ref(max_user_id="other-user")
    wrong_chat = _context_ref(chat_id="other-chat")
    missing_workflow = _context_ref(workflow_ref=None)

    responses = [
        client.get("/max/app/api/context", headers=_headers(wrong_purpose)),
        client.get("/max/app/api/context", headers=_headers(wrong_user)),
        client.get("/max/app/api/context", headers=_headers(wrong_chat)),
        client.get("/max/app/api/context", headers=_headers(missing_workflow)),
        client.get("/max/app/api/context", headers=_headers(_context_ref(), chat_type="chat")),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403, 403]
    assert [response.json()["status"] for response in responses] == [
        "invalid_context",
        "invalid_context",
        "invalid_context",
        "invalid_context",
        "private_chat_required",
    ]


def test_expired_launch_and_context_map_to_safe_status() -> None:
    client = _client()
    context_ref = _context_ref()
    expired_context = _context_ref(ttl_seconds=1, now=int(time.time()) - 2)

    expired_launch = client.get(
        "/max/app/api/context",
        headers=_headers(context_ref, auth_date=int(time.time()) - 3601),
    )
    expired_context_response = client.get(
        "/max/app/api/context",
        headers=_headers(expired_context),
    )

    assert expired_launch.status_code == 409
    assert expired_launch.json() == {"status": "expired_launch"}
    assert expired_context_response.status_code == 409
    assert expired_context_response.json() == {"status": "expired_context"}


def test_same_user_chat_rotation_rejects_old_context_and_accepts_fresh_context() -> None:
    resolver = FakeContextResolver()
    client = _client(context_resolver=resolver)
    old_context = _context_ref(chat_id="old-chat")

    rejected = client.get(
        "/max/app/api/context",
        headers=_headers(old_context, chat_id="new-chat"),
    )
    fresh_context = _context_ref(chat_id="new-chat")
    accepted = client.get(
        "/max/app/api/context",
        headers=_headers(fresh_context, chat_id="new-chat"),
    )

    assert rejected.status_code == 403
    assert rejected.json() == {"status": "invalid_context"}
    assert accepted.status_code == 200
    assert resolver.get_calls == [(USER_ID, WORKFLOW_REF)]


def test_disabled_user_after_context_issue_is_blocked_before_resolver() -> None:
    resolver = FakeContextResolver()
    client = _client(
        identity=FakeIdentityResolver(user_status="DISABLED"),
        context_resolver=resolver,
    )
    context_ref = _context_ref()

    response = client.get("/max/app/api/context", headers=_headers(context_ref))

    assert response.status_code == 403
    assert response.json() == {"status": "user_disabled"}
    assert resolver.get_calls == []


def test_identity_and_runtime_errors_map_safely() -> None:
    for exc, expected_status, expected_body in [
        (IdentityConflict("synthetic"), 409, {"status": "identity_conflict"}),
        (PersistenceConflict("synthetic"), 503, {"status": "temporary_failure"}),
    ]:
        identity = FakeIdentityResolver(exc=exc)
        resolver = FakeContextResolver()
        client = _client(identity=identity, context_resolver=resolver)
        context_ref = _context_ref()

        response = client.get("/max/app/api/context", headers=_headers(context_ref))

        assert response.status_code == expected_status
        assert response.json() == expected_body
        assert resolver.get_calls == []


def test_runtime_or_configuration_missing_is_safe() -> None:
    context_ref = _context_ref()
    no_runtime = TestClient(create_app(_settings()))
    no_resolver = _client(without_context_resolver=True)
    no_secret = TestClient(
        create_app(AppSettings(_env_file=None, max_bot_token=SecretStr(BOT_TOKEN)))
    )

    first = no_runtime.get("/max/app/api/context", headers=_headers(context_ref))
    second = no_resolver.get("/max/app/api/context", headers=_headers(context_ref))
    third = no_secret.get("/max/app/api/context", headers=_headers(context_ref))

    assert first.status_code == 503
    assert first.json() == {"status": "interaction_unavailable"}
    assert second.status_code == 503
    assert second.json() == {"status": "interaction_unavailable"}
    assert third.status_code == 503
    assert third.json() == {"status": "configuration_error"}


def test_invalid_resolver_payload_is_rejected() -> None:
    resolver = FakeContextResolver(view=object())
    client = _client(context_resolver=resolver)
    context_ref = _context_ref()

    response = client.get("/max/app/api/context", headers=_headers(context_ref))

    assert response.status_code == 503
    assert response.json() == {"status": "invalid_interaction"}


def _view(*, allow_cancel: bool = True) -> ContextInteractionView:
    return ContextInteractionView(
        WORKFLOW_REF,
        "Выберите карточку",
        "Найдены несколько вариантов.",
        [
            ContextInteractionOption("one", "Первый вариант", "Описание"),
            ContextInteractionOption("two", "Второй вариант"),
        ],
        allow_cancel=allow_cancel,
    )


def _client(
    *,
    identity: FakeIdentityResolver | None = None,
    context_resolver: FakeContextResolver | None = None,
    sender: FakeSender | None = None,
    without_context_resolver: bool = False,
) -> TestClient:
    resolved_context_resolver = context_resolver or FakeContextResolver()
    runtime = MaxMiniAppRuntime(
        identity_resolver_factory=lambda: identity or FakeIdentityResolver(),
        kaiten_connection_binder_factory=lambda: object(),  # type: ignore[arg-type]
        message_sender=sender or FakeSender(),
        context_signer=MiniAppContextSigner(CONTEXT_SECRET),
        context_interaction_resolver_factory=(
            None if without_context_resolver else lambda: resolved_context_resolver
        ),
    )
    return TestClient(create_app(_settings(), max_mini_app_runtime=runtime))


def _settings() -> AppSettings:
    return AppSettings(
        max_bot_token=SecretStr(BOT_TOKEN),
        max_mini_app_context_secret=SecretStr(CONTEXT_SECRET),
    )


def _headers(
    context_ref: str,
    *,
    auth_date: int | None = None,
    chat_type: str = "dialog",
    max_user_id: str = MAX_USER_ID,
    chat_id: str = MAX_CHAT_ID,
) -> dict[str, str]:
    return {
        MAX_INIT_DATA_HEADER: _signed_init_data(
            auth_date=auth_date,
            start_param=context_ref,
            chat_type=chat_type,
            max_user_id=max_user_id,
            chat_id=chat_id,
        ),
        MAX_MINI_APP_CONTEXT_HEADER: context_ref,
    }


def _context_ref(
    *,
    purpose: MiniAppContextPurpose = MiniAppContextPurpose.SYNTHETIC_CONTEXT,
    max_user_id: str = MAX_USER_ID,
    chat_id: str = MAX_CHAT_ID,
    ttl_seconds: int = 900,
    now: int | None = None,
    workflow_ref: str | None = WORKFLOW_REF,
) -> str:
    signer = MiniAppContextSigner(CONTEXT_SECRET)
    binding = signer.make_identity_binding(max_user_id=max_user_id, chat_id=chat_id)
    return signer.issue(
        purpose=purpose,
        identity_binding=binding,
        ttl_seconds=ttl_seconds,
        now=int(time.time()) if now is None else now,
        nonce=f"nonce-{purpose.value}",
        workflow_ref=workflow_ref,
    )


def _signed_init_data(
    *,
    auth_date: int | None = None,
    start_param: str,
    chat_type: str = "dialog",
    max_user_id: str = MAX_USER_ID,
    chat_id: str = MAX_CHAT_ID,
    bot_token: str = BOT_TOKEN,
) -> str:
    params: dict[str, str] = {
        "auth_date": str(auth_date or int(time.time())),
        "user": json.dumps({"id": max_user_id}, separators=(",", ":")),
        "chat": json.dumps({"id": chat_id, "type": chat_type}, separators=(",", ":")),
        "start_param": start_param,
    }
    data_check_string = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(params) + f"&hash={signature}"
