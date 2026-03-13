# Copilot instructions for AI Voice Resource Hub

This repository is a local-first voice AI discovery app with semantic search, reranking, refresh automation, and demo capture.

## Repository priorities

- Preserve the local-first architecture: FastAPI, SQLite, static frontend assets, and Ollama-hosted local models.
- Prefer extending the current search and refresh pipeline over introducing new infrastructure.
- Keep the catalog grounded in `backend/app/seed_data.py`, `backend/app/refresh_service.py`, and `backend/app/search_service.py`.
- When adding a new category, update `backend/app/config.py`, `frontend/app.js`, and any affected tests together.
- Keep user-visible failures explicit. Do not silently suppress model, refresh, or fetch failures.

## Recommended Copilot workflow

- Use `voice-resource-curation` when expanding seed data, feed coverage, category UX, or search ranking behavior.
- Use `voice-resource-ops` when validating local models, running refreshes, recording demos, or installing the daily macOS refresh agent.
- If the reusable toolkit is available globally, pair these app-local assets with `server-foundation`, `local-llm-feature-integration`, `testing-and-demo`, and `ui-foundation`.

## Validation requirements

After backend or script changes, run:

```bash
python3 -m py_compile backend/app/*.py backend/tests/test_api.py scripts/*.py
python3 -m unittest discover -s backend/tests
```

After frontend changes, run:

```bash
node --check frontend/app.js
```

When refresh or demo logic changes, also run:

```bash
python3 scripts/refresh_catalog.py --mode sample
```

## App conventions

- Keep refresh automation compatible with standard macOS user-level launch agents.
- Store demo and hook outputs under `artifacts/`.
- Prefer standard library scripts for local operations unless an existing dependency is already in use.
