"""ASGI application shell."""

from fastapi import FastAPI
from pydantic import BaseModel

from kvc_config import AppSettings, get_settings

SERVICE_NAME = "kaiten-voice-control"


class HealthResponse(BaseModel):
    """Stable health response used by smoke tests and deployment probes."""

    status: str
    service: str


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create the FastAPI application without opening external connections."""

    app_settings = settings or get_settings()
    app = FastAPI(title=app_settings.service_name)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service=SERVICE_NAME)

    return app


app = create_app()
