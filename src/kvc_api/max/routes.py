"""MAX webhook routes."""

from __future__ import annotations

from json import JSONDecodeError

from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse, Response

from kvc_api.max.dispatcher import UpdateDispatcher, WebhookRetryableDispatchError
from kvc_api.max.webhook import MAX_WEBHOOK_SECRET_HEADER, validate_webhook_secret
from kvc_config import AppSettings
from kvc_integrations.max.errors import MaxUpdateParseError
from kvc_integrations.max.update_parser import parse_max_update


class MaxWebhookResponse(BaseModel):
    """Safe MAX webhook response body."""

    status: str


def create_max_router(
    *,
    settings: AppSettings,
    dispatcher: UpdateDispatcher | None,
) -> APIRouter:
    """Create the MAX webhook router."""

    router = APIRouter()

    @router.post(settings.max_webhook_path, response_model=MaxWebhookResponse)
    async def max_webhook(request: Request) -> Response:
        if settings.max_inbound_mode != "webhook":
            return JSONResponse({"status": "inactive_inbound_mode"}, status_code=409)

        supplied_secret = request.headers.get(MAX_WEBHOOK_SECRET_HEADER)
        if not validate_webhook_secret(
            configured_secret=settings.max_webhook_secret,
            supplied_secret=supplied_secret,
        ):
            return JSONResponse({"status": "forbidden"}, status_code=403)

        if dispatcher is None:
            return JSONResponse({"status": "unavailable"}, status_code=503)

        try:
            raw_update: object = await request.json()
        except JSONDecodeError:
            return JSONResponse({"status": "invalid_json"}, status_code=400)

        try:
            update = parse_max_update(raw_update, source="webhook")
        except MaxUpdateParseError:
            return JSONResponse({"status": "invalid_update"}, status_code=400)

        try:
            await dispatcher.dispatch(update)
        except WebhookRetryableDispatchError:
            return JSONResponse({"status": "retryable_failure"}, status_code=503)

        return JSONResponse({"status": "accepted"}, status_code=200)

    return router


__all__ = ["MaxWebhookResponse", "create_max_router"]
