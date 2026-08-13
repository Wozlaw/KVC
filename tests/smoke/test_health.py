"""Smoke tests for the FastAPI application shell."""

from fastapi.testclient import TestClient

from kvc_api.main import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "kaiten-voice-control",
    }


def test_app_shell_starts_without_external_api_connections() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
