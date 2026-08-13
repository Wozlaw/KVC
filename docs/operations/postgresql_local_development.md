# PostgreSQL Local Development

Kaiten Voice Control uses PostgreSQL as its service database. SQLite is not used as a fallback for development or tests.

The runtime database path is SQLAlchemy 2.x async API with the `asyncpg` driver. Local database credentials must be stored only in a local `.env` file or environment variables, never in tracked files.

Example local URL:

```dotenv
KVC_DATABASE_URL=postgresql+asyncpg://kvc_user:change_me@127.0.0.1:5432/kvc_dev
```

Check whether PostgreSQL tooling is available:

```powershell
psql --version
where.exe psql
Get-Service *postgres*
```

Run a project database health smoke after setting a real local `KVC_DATABASE_URL`:

```powershell
python -c "import asyncio; from kvc_persistence import check_database_connection, create_async_engine_from_settings, dispose_async_engine; engine = create_async_engine_from_settings(); result = asyncio.run(check_database_connection(engine)); asyncio.run(dispose_async_engine(engine)); print('database health ok' if result.ok else f'database health failed: {result.error_type}')"
```

Automatic PostgreSQL installation, service creation, database/user creation, PATH changes, Docker setup, and system configuration changes are not part of Codex tasks without a separate user request.

Production is planned for Linux on NetAngels. Do not move the local Windows `.venv` to production.

