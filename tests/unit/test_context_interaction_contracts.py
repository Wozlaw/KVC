"""Provider-neutral contextual interaction contract tests."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, fields, is_dataclass
from typing import get_args, get_type_hints
from uuid import UUID

import pytest

from kvc_application import (
    CONTEXT_INTERACTION_MAX_DESCRIPTION_LENGTH,
    CONTEXT_INTERACTION_MAX_LABEL_LENGTH,
    CONTEXT_INTERACTION_MAX_OPTION_ID_LENGTH,
    CONTEXT_INTERACTION_MAX_OPTIONS,
    CONTEXT_INTERACTION_MAX_PROMPT_LENGTH,
    CONTEXT_INTERACTION_MAX_RESULT_MESSAGE_LENGTH,
    CONTEXT_INTERACTION_MAX_TITLE_LENGTH,
    CONTEXT_INTERACTION_MAX_WORKFLOW_REF_LENGTH,
    CONTEXT_INTERACTION_WORKFLOW_REF_PATTERN,
    ContextInteractionAlreadyCompleted,
    ContextInteractionExpired,
    ContextInteractionInvalidSelection,
    ContextInteractionMissing,
    ContextInteractionOption,
    ContextInteractionResolver,
    ContextInteractionResult,
    ContextInteractionStatus,
    ContextInteractionView,
    validate_context_interaction_workflow_ref,
)
from kvc_application.errors import ApplicationError
from kvc_application.ports import ContextInteractionResolver as ContextInteractionResolverPort

USER_ID = UUID("00000000-0000-0000-0000-000000000901")
WORKFLOW_REF = "synthetic-choice-001"


def test_context_interaction_status_literal() -> None:
    assert get_args(ContextInteractionStatus) == ("completed", "cancelled")


def test_context_interaction_dto_field_inventory() -> None:
    for dto_type in (ContextInteractionOption, ContextInteractionView, ContextInteractionResult):
        assert is_dataclass(dto_type)

    assert [field.name for field in fields(ContextInteractionOption)] == [
        "option_id",
        "label",
        "description",
    ]
    assert [field.name for field in fields(ContextInteractionView)] == [
        "workflow_ref",
        "title",
        "prompt",
        "options",
        "allow_cancel",
    ]
    assert [field.name for field in fields(ContextInteractionResult)] == ["status", "message"]


def test_context_interaction_dtos_are_frozen_and_bound_options_to_tuple() -> None:
    option = ContextInteractionOption("one", "Первый")
    view = ContextInteractionView(WORKFLOW_REF, "Заголовок", "Выберите вариант", [option])
    result = ContextInteractionResult("completed", "Готово")

    assert view.options == (option,)
    for dto in (option, view, result):
        with pytest.raises(FrozenInstanceError):
            setattr(dto, fields(dto)[0].name, "blocked")


@pytest.mark.parametrize(
    "option",
    [
        ContextInteractionOption("x" * CONTEXT_INTERACTION_MAX_OPTION_ID_LENGTH, "Label"),
        ContextInteractionOption("id", "x" * CONTEXT_INTERACTION_MAX_LABEL_LENGTH),
        ContextInteractionOption("id", "Label", "x" * CONTEXT_INTERACTION_MAX_DESCRIPTION_LENGTH),
    ],
)
def test_context_interaction_option_accepts_bounded_values(
    option: ContextInteractionOption,
) -> None:
    assert option.option_id


@pytest.mark.parametrize(
    ("option_id", "label", "description"),
    [
        ("", "Label", None),
        ("x" * (CONTEXT_INTERACTION_MAX_OPTION_ID_LENGTH + 1), "Label", None),
        ("id", "", None),
        ("id", "x" * (CONTEXT_INTERACTION_MAX_LABEL_LENGTH + 1), None),
        ("id", "Label", ""),
        ("id", "Label", "x" * (CONTEXT_INTERACTION_MAX_DESCRIPTION_LENGTH + 1)),
    ],
)
def test_context_interaction_option_rejects_invalid_values(
    option_id: str,
    label: str,
    description: str | None,
) -> None:
    with pytest.raises(ValueError):
        ContextInteractionOption(option_id, label, description)


def test_context_interaction_view_bounds_options_and_text() -> None:
    options = tuple(
        ContextInteractionOption(f"id-{index}", f"Option {index}")
        for index in range(CONTEXT_INTERACTION_MAX_OPTIONS)
    )
    view = ContextInteractionView(
        "x" * CONTEXT_INTERACTION_MAX_WORKFLOW_REF_LENGTH,
        "x" * CONTEXT_INTERACTION_MAX_TITLE_LENGTH,
        "x" * CONTEXT_INTERACTION_MAX_PROMPT_LENGTH,
        options,
    )

    assert len(view.options) == CONTEXT_INTERACTION_MAX_OPTIONS


@pytest.mark.parametrize(
    "workflow_ref",
    [
        "",
        "has space",
        "slash/ref",
        "кириллица",
        "x" * (CONTEXT_INTERACTION_MAX_WORKFLOW_REF_LENGTH + 1),
    ],
)
def test_context_interaction_workflow_ref_is_opaque_safe_subset(workflow_ref: str) -> None:
    with pytest.raises(ValueError):
        validate_context_interaction_workflow_ref(workflow_ref)


def test_context_interaction_view_rejects_invalid_shape() -> None:
    option = ContextInteractionOption("one", "Первый")

    invalid_cases = [
        ("valid-ref", "", "Prompt", [option]),
        ("valid-ref", "Title", "", [option]),
        ("valid-ref", "Title", "Prompt", []),
        ("valid-ref", "Title", "Prompt", [option, ContextInteractionOption("one", "Dup")]),
    ]

    for workflow_ref, title, prompt, options in invalid_cases:
        with pytest.raises(ValueError):
            ContextInteractionView(workflow_ref, title, prompt, options)


def test_context_interaction_result_bounds_status_and_message() -> None:
    assert ContextInteractionResult("completed").message is None
    assert ContextInteractionResult(
        "cancelled",
        "x" * CONTEXT_INTERACTION_MAX_RESULT_MESSAGE_LENGTH,
    )

    with pytest.raises(ValueError):
        ContextInteractionResult("pending")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ContextInteractionResult("completed", "")
    with pytest.raises(ValueError):
        ContextInteractionResult(
            "completed",
            "x" * (CONTEXT_INTERACTION_MAX_RESULT_MESSAGE_LENGTH + 1),
        )


def test_context_interaction_errors_are_application_errors() -> None:
    for error_type in (
        ContextInteractionMissing,
        ContextInteractionExpired,
        ContextInteractionInvalidSelection,
        ContextInteractionAlreadyCompleted,
    ):
        assert issubclass(error_type, ApplicationError)
        assert isinstance(error_type(), ApplicationError)


def test_context_interaction_resolver_signature_is_async_keyword_only() -> None:
    assert ContextInteractionResolver
    assert CONTEXT_INTERACTION_WORKFLOW_REF_PATTERN == r"^[A-Za-z0-9_-]+$"

    get_signature = inspect.signature(ContextInteractionResolverPort.get_interaction)
    submit_signature = inspect.signature(ContextInteractionResolverPort.submit_selection)
    cancel_signature = inspect.signature(ContextInteractionResolverPort.cancel_interaction)
    get_hints = get_type_hints(ContextInteractionResolverPort.get_interaction)
    submit_hints = get_type_hints(ContextInteractionResolverPort.submit_selection)
    cancel_hints = get_type_hints(ContextInteractionResolverPort.cancel_interaction)

    assert inspect.iscoroutinefunction(ContextInteractionResolverPort.get_interaction)
    assert inspect.iscoroutinefunction(ContextInteractionResolverPort.submit_selection)
    assert inspect.iscoroutinefunction(ContextInteractionResolverPort.cancel_interaction)
    assert list(get_signature.parameters) == ["self", "user_id", "workflow_ref"]
    assert list(submit_signature.parameters) == ["self", "user_id", "workflow_ref", "option_id"]
    assert list(cancel_signature.parameters) == ["self", "user_id", "workflow_ref"]
    for signature in (get_signature, submit_signature, cancel_signature):
        assert signature.parameters["user_id"].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters["workflow_ref"].kind is inspect.Parameter.KEYWORD_ONLY
    assert submit_signature.parameters["option_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert get_hints["user_id"] is UUID
    assert get_hints["workflow_ref"] is str
    assert get_hints["return"] is ContextInteractionView
    assert submit_hints["option_id"] is str
    assert submit_hints["return"] is ContextInteractionResult
    assert cancel_hints["return"] is ContextInteractionResult


def test_context_interaction_port_source_is_provider_neutral() -> None:
    source = inspect.getsource(ContextInteractionResolverPort)

    for forbidden in ("MAX", "FastAPI", "httpx", "sqlalchemy", "Kaiten"):
        assert forbidden not in source
