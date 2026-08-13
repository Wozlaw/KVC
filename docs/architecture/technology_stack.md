# Technology Stack

## Runtime

- Python 3.12 is the target runtime.
- FastAPI provides the API and webhook transport layer.
- Hypercorn is the ASGI server used for local and production-compatible startup.
- Pydantic 2 and pydantic-settings define contracts and configuration.
- HTTPX is the base HTTP client for MAX, Kaiten, STT, and other adapters.
- PostgreSQL is accessed through SQLAlchemy 2.x async APIs with `asyncpg`.
- Alembic owns future schema migrations and uses the shared persistence metadata.

## Integrations

- MAX Webhook is the production transport.
- MAX Long Polling is allowed only as an auxiliary local development transport.
- GigaChat is the primary LLM provider.
- The official `gigachat` SDK must be isolated inside the integration adapter layer.
- STT is accessed through a replaceable `SpeechToTextProvider` boundary.
- A SaluteSpeech adapter is allowed when valid access exists.
- Kaiten access is isolated behind a dedicated adapter.

## Data and Background Processing

- Kaiten is the source of truth for cards, boards, comments, deadlines, and attachments.
- PostgreSQL is the service database for application state only.
- SQLAlchemy 2, Alembic, and asyncpg are reserved for persistence.
- Persistence infrastructure contains no business tables yet and does not depend on MAX, Kaiten, GigaChat, or STT.
- The background worker has a separate Python entrypoint.
- The worker may read Kaiten and send notifications, but must not mutate Kaiten.

## Bootstrap Exclusions

- Redis is not part of the MVP bootstrap.
- Celery is not part of the MVP bootstrap.
- Docker is not required for the first stage.
- Business operations, database schema, migrations, webhooks, polling, LLM prompts, and STT calls are outside this stage.
