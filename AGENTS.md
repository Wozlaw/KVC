# AGENTS.md

## Architecture Rules

- Keep module boundaries explicit: API, application, domain, persistence, notifications, config, and integrations are separate packages.
- Do not place integration code in `kvc_domain` or `kvc_application`.
- Kaiten is the source of truth for project state.
- Do not create a local copy of Kaiten content without a separate architecture decision.
- LLM providers do not execute business operations directly.
- Any Kaiten mutation must follow an explicit user command.
- The background worker may read Kaiten and send notifications, but must not mutate Kaiten.
- Provider-specific code belongs in integration adapters.
- Do not bind the application layer directly to GigaChat, SaluteSpeech, MAX, or Kaiten SDKs.

## Development Rules

Before finishing an implementation task, run these checks when applicable:

```text
pytest
ruff format --check
ruff check
mypy
pip check
git diff --check
```

## Secrets

- Never put secrets in tracked files.
- Never print secrets in reports.
- Do not add `.env` to Git.
- Use `.env.example` only for empty or demonstration values.

## Reports

Store all Codex reports in `codex/reports/`.

Each report must include:

- what was done;
- created or changed files;
- technical decisions;
- checks performed;
- actual command results;
- notes or risks;
- stage status.

## Specifications

Treat materials in `docs/specifications/` as project requirements.

Do not silently change product requirements. If implementation requires revisiting a fixed contract, record the conflict in the report instead of making a new product decision.

