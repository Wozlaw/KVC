"""Canonical production ASGI target."""

from kvc_api.production import create_production_app

app = create_production_app()
