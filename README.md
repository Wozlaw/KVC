# Kaiten Voice Control

Kaiten Voice Control is a planned dialog client for Kaiten in the MAX messenger. It will support text and voice input, direct commands, dialog context, attachments, AI summaries, and background deadline checks.

Current status: infrastructure bootstrap. Business features and external integrations are not implemented at this stage.

## Stack

- Python 3.12
- FastAPI and ASGI
- Hypercorn
- Pydantic 2 and pydantic-settings
- HTTPX
- PostgreSQL through SQLAlchemy 2, Alembic, and asyncpg
- GigaChat through an isolated provider adapter
- Replaceable speech-to-text provider abstraction

Production deployment is expected on NetAngels. MAX production transport is webhook-based; long polling is only a local development option.

## Structure

- `src/kvc_api` - FastAPI transport layer.
- `src/kvc_worker` - background worker entrypoint.
- `src/kvc_domain` - domain models and contracts.
- `src/kvc_application` - application and use-case layer.
- `src/kvc_persistence` - future database layer.
- `src/kvc_notifications` - future notification policies.
- `src/kvc_config` - application settings.
- `src/kvc_integrations` - external service adapters.

## Development Setup

Create and activate the root virtual environment on Windows:

```powershell
& 'C:\Users\79527\AppData\Local\Programs\Python\Python312\python.exe' -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
```

Real secrets must be supplied through environment variables or a local `.env` file. Secrets are not stored in Git. Use `.env.example` as a template only.

## Run Locally

```powershell
python -m hypercorn kvc_api.main:app --bind 127.0.0.1:8000
```

Health check:

```text
GET /health
```

## Quality Gates

```powershell
python -m pip check
python -m pytest
python -m pytest -W error
python -m ruff format --check .
python -m ruff check .
python -m mypy src
git diff --check
```

## PostgreSQL

Persistence infrastructure targets PostgreSQL through SQLAlchemy async APIs and `asyncpg`. Set `KVC_DATABASE_URL` in local `.env` or environment variables before running database checks or Alembic online commands. `/health` remains a process liveness check and does not require a database connection.
