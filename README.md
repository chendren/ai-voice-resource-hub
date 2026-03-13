# AI Voice Resource Hub

AI Voice Resource Hub is a local-first three-tier web application for researching, comparing, and refreshing the voice AI tooling landscape. It combines a static browser UI, a FastAPI backend, SQLite + FTS5 storage, and optional local Ollama models to help you move from broad market exploration to a concrete shortlist.

The project is designed for builders evaluating speech-to-text, text-to-speech, LLM, SLM, embeddings, realtime media, speech-to-speech, telephony, orchestration, hosting, containers, observability, and related infrastructure.

## Table of contents

- [What this project does](#what-this-project-does)
- [Why it is useful](#why-it-is-useful)
- [Architecture overview](#architecture-overview)
- [Core capabilities](#core-capabilities)
- [Technology stack](#technology-stack)
- [Repository structure](#repository-structure)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [How search and ranking work](#how-search-and-ranking-work)
- [Catalog refresh and freshness automation](#catalog-refresh-and-freshness-automation)
- [HTTP API reference](#http-api-reference)
- [Frontend experience](#frontend-experience)
- [GitHub Copilot assets included in the repo](#github-copilot-assets-included-in-the-repo)
- [Development workflow](#development-workflow)
- [Testing](#testing)
- [Demo recording](#demo-recording)
- [Troubleshooting](#troubleshooting)
- [Current limitations](#current-limitations)

## What this project does

The repository ships a local web application that:

- Curates a catalog of voice AI products, frameworks, and infrastructure options
- Supports category browsing across the major voice application building blocks
- Combines lexical search and semantic retrieval for better discovery
- Uses local models, when available, for embeddings, reranking, and grounded answer generation
- Tracks update sources and refresh history so the catalog stays current
- Provides a daily refresh script and a macOS launch agent installer
- Includes app-local GitHub Copilot instructions, skills, an agent, and hooks for future maintenance

## Why it is useful

A typical voice AI evaluation ends up scattered across product sites, docs, GitHub repos, release feeds, and vendor comparison notes. This project centralizes that work into a single local workspace so you can:

- search by outcome instead of by vendor name
- compare managed and self-hosted options side by side
- keep a local catalog fresh without depending on a hosted SaaS
- use your own local models for ranking and summarization
- extend the catalog and workflow with GitHub Copilot assets included in the repo

## Architecture overview

The app follows a lightweight three-tier design:

1. **Presentation tier**
   - Static HTML, CSS, and JavaScript in `frontend/`
   - Served directly by FastAPI with no Node build step
   - Provides search, category browsing, shortlist generation, update browsing, and resource detail views

2. **Application tier**
   - FastAPI app in `backend/app/main.py`
   - Exposes health, dashboard, resources, search, feed source, refresh run, and refresh endpoints
   - Coordinates model availability checks, refresh execution, and search behavior

3. **Data and AI tier**
   - SQLite database stored under `backend/data/` by default
   - SQLite FTS5 for lexical search
   - Embedding storage in SQLite for semantic retrieval
   - Optional Ollama integration for embeddings, reranking, and answer synthesis

At runtime, the browser talks to the FastAPI backend, the backend reads curated and refreshed data from SQLite, and the search layer optionally enriches results using local models.

## Core capabilities

### 1. Curated voice AI catalog

The app starts with curated seed data for major categories such as:

- STT
- TTS
- LLM
- SLM
- Embeddings
- Realtime media
- Speech-to-speech
- Voice agents
- Orchestration
- Telephony
- Hosting
- Containers
- Observability

### 2. Semantic search with grounded answers

Search requests combine:

- lexical retrieval from SQLite FTS5
- embedding-based similarity scoring
- reranking and answer generation when Ollama is available
- deterministic fallback behavior when Ollama is unavailable

This gives you shortlist-style responses instead of raw keyword matches alone.

### 3. Freshness tracking and daily refresh

The refresh subsystem:

- monitors configured feed or source definitions
- records refresh history
- stores update entries alongside curated resources
- supports one-off refreshes and scheduled daily execution

### 4. Local-model-first behavior

When supported local models are installed in Ollama, the app uses them automatically. If not, the application still works with fallback embeddings and heuristic summaries so the site remains usable offline or in limited environments.

### 5. Copilot-ready project assets

The repository includes project-specific Copilot instructions, skills, an agent, and a hook configuration so future changes can be made in a more guided, repeatable way.

## Technology stack

### Backend

- FastAPI
- Uvicorn
- httpx

### Frontend

- Static HTML
- Plain JavaScript
- Custom CSS

### Data

- SQLite
- SQLite FTS5

### Local AI integration

- Ollama
- `nomic-embed-text:latest` for embeddings by default
- `cx-intelligence-slm:latest` for answer generation and reranking by default

## Repository structure

```text
.
├── .github/
│   ├── agents/
│   ├── hooks/
│   ├── skills/
│   └── copilot-instructions.md
├── backend/
│   ├── app/
│   │   ├── blueprint.json
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── ollama_client.py
│   │   ├── refresh_service.py
│   │   ├── search_service.py
│   │   └── seed_data.py
│   ├── data/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── app.js
│   ├── index.html
│   └── styles.css
├── scripts/
│   ├── install_daily_refresh.py
│   ├── log_copilot_event.py
│   ├── record_demo.py
│   └── refresh_catalog.py
└── run_local.sh
```

## Requirements

Minimum recommended environment:

- macOS or another Unix-like environment
- Python 3 with `venv` support
- Git

Optional but recommended:

- Ollama running locally
- The following models pulled into Ollama:
  - `nomic-embed-text:latest`
  - `cx-intelligence-slm:latest`

## Quick start

### 1. Clone the repository

```bash
git clone git@github.com:YOUR_GITHUB_USERNAME/ai-voice-resource-hub.git
cd ai-voice-resource-hub
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install backend dependencies

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r backend/requirements.txt
```

### 4. Run the test suite

```bash
python3 -m unittest discover -s backend/tests
```

### 5. Start the app

```bash
./run_local.sh
```

The app will be available at:

- `http://127.0.0.1:8000/`

### 6. Try a few example queries

- `Best local speech-to-text and TTS stack for rapid prototyping`
- `LiveKit and Pipecat resources for realtime voice agents`
- `Local models and embeddings for voice RAG applications`
- `Cloud hosting options for containerized voice AI backends`

## Configuration

The application is intentionally simple to configure. Most users can run it with defaults.

### Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_PORT` | Port used by `run_local.sh` | `8000` |
| `APP_DATABASE_PATH` | Override database path | `backend/data/app.db` |
| `VOICE_HUB_OLLAMA_URL` | Ollama base URL | `http://127.0.0.1:11434` |
| `VOICE_HUB_EMBED_MODEL` | Embedding model name | `nomic-embed-text:latest` |
| `VOICE_HUB_LLM_MODEL` | LLM/rerank model name | `cx-intelligence-slm:latest` |
| `VOICE_HUB_DISABLE_OLLAMA` | Force fallback mode | unset |
| `VOICE_HUB_EMBED_DIMS` | Embedding vector size used by fallback path | `96` |
| `VOICE_HUB_STARTUP_REFRESH_MODE` | Initial refresh mode on first startup | `smart` |

### Example shell configuration

```bash
export VOICE_HUB_OLLAMA_URL=http://127.0.0.1:11434
export VOICE_HUB_EMBED_MODEL=nomic-embed-text:latest
export VOICE_HUB_LLM_MODEL=cx-intelligence-slm:latest
export VOICE_HUB_DISABLE_OLLAMA=1
```

## How search and ranking work

The search flow is designed to give useful shortlist recommendations instead of only raw matches.

### Search pipeline

1. The user submits a natural-language query from the frontend.
2. The backend collects lexical candidates using SQLite FTS5.
3. The search service evaluates embedding similarity for semantic matching.
4. If Ollama is available, the service can rerank the shortlist and generate a grounded answer summary.
5. If Ollama is unavailable, the service falls back to deterministic local embeddings and heuristic answer generation.
6. The frontend renders:
   - the answer summary
   - the result cards
   - resource facts and badges
   - detail modals for deeper inspection

### Why fallback mode matters

Fallback mode ensures the app remains functional even when:

- Ollama is not running
- the models are not installed yet
- the machine is offline
- the user wants predictable, lightweight local behavior

## Catalog refresh and freshness automation

### Run a one-off refresh

Smart refresh:

```bash
python3 scripts/refresh_catalog.py --mode smart
```

Sample refresh for predictable local testing:

```bash
python3 scripts/refresh_catalog.py --mode sample
```

JSON output:

```bash
python3 scripts/refresh_catalog.py --mode smart --json
```

### Install a daily macOS refresh job

```bash
python3 scripts/install_daily_refresh.py --hour 8 --minute 15 --load
```

What this does:

- writes a plist into `~/Library/LaunchAgents`
- points the job at `scripts/refresh_catalog.py`
- preserves relevant environment variables for the refresh process
- optionally loads the agent immediately with `launchctl`

### Refresh modes

| Mode | Meaning |
| --- | --- |
| `smart` | Default behavior, attempts the normal refresh path |
| `remote` | Force remote/source-oriented refresh behavior |
| `sample` | Use deterministic sample updates for testing or offline demos |

## HTTP API reference

### `GET /health`

Returns a simple health payload with project metadata and model availability.

### `GET /api/meta`

Returns:

- display name
- description
- categories
- suggested queries
- model status
- capability flags

### `GET /api/dashboard`

Returns the data needed to render the main dashboard:

- top-level stats
- featured collections
- updates
- feed sources
- refresh history
- suggested queries
- model status

### `GET /api/resources`

Supported query parameters:

- `category`
- `record_type` (`resource`, `update`, or `all`)
- `provider`
- `local_only`
- `hosted_only`
- `open_source_only`
- `limit`

### `GET /api/resources/{resource_id}`

Returns a single resource or update record by numeric ID.

### `GET /api/search`

Supported query parameters:

- `q`
- `category`
- `include_updates`
- `limit`

Returns:

- an answer summary
- ranked results
- rerank metadata

### `GET /api/feed-sources`

Returns tracked source definitions.

### `GET /api/refresh-runs`

Returns recent refresh history.

### `POST /api/refresh`

Example payload:

```json
{
  "mode": "smart"
}
```

Accepted modes:

- `smart`
- `remote`
- `sample`

The response includes refresh metadata plus a fresh dashboard payload.

## Frontend experience

The frontend is intentionally zero-build and easy to maintain. It provides:

- a template-inspired SaaS hero section
- a search-first research workflow
- curated collections for common evaluation patterns
- a compact directory-style catalog
- update and source panels for freshness tracking
- resource detail modals for deeper review

Because it is plain HTML, CSS, and JavaScript, the app is easy to run locally and easy to edit without a frontend toolchain.

## GitHub Copilot assets included in the repo

This repository contains app-specific Copilot assets:

- `.github/copilot-instructions.md`
- `.github/skills/voice-resource-curation/SKILL.md`
- `.github/skills/voice-resource-ops/SKILL.md`
- `.github/agents/voice-resource-hub-maintainer.agent.md`
- `.github/hooks/voice-resource-hub.json`

These assets are intended to help future sessions with:

- catalog curation
- freshness operations
- demo generation
- app maintenance
- guided Copilot behavior within this repo

## Development workflow

A straightforward local workflow looks like this:

1. Create and activate a virtual environment
2. Install dependencies from `backend/requirements.txt`
3. Run backend tests
4. Start the server with `./run_local.sh`
5. Open the app in the browser
6. Run refresh scripts as needed
7. Record demo evidence if you want a local walkthrough artifact

There is no frontend build step and no separate API gateway or background worker required for normal local use.

## Testing

Run the existing backend regression suite:

```bash
python3 -m unittest discover -s backend/tests
```

The tests cover:

- health and dashboard endpoints
- resource filters
- semantic search behavior
- manual refresh behavior

For quick manual smoke testing, open the UI and try:

- the homepage
- a search query
- the refresh button
- one resource detail modal

## Demo recording

To capture a local demo:

```bash
python3 scripts/record_demo.py --base-url http://127.0.0.1:8000 --output-dir artifacts/demo
```

The recorder produces:

- screenshots
- a transcript JSON file
- an MP4 video when the local environment supports it

This is implemented as a practical local fallback because direct ChatGPT Computer Use is not exposed inside this CLI environment.

## Troubleshooting

### The app starts but search quality is weak

Check whether Ollama is running and whether the expected models are installed:

```bash
ollama list
```

If the models are missing, pull them:

```bash
ollama pull nomic-embed-text:latest
ollama pull cx-intelligence-slm:latest
```

### I want deterministic local testing

Disable Ollama and use sample refresh mode:

```bash
export VOICE_HUB_DISABLE_OLLAMA=1
export VOICE_HUB_STARTUP_REFRESH_MODE=sample
```

### Port 8000 is already taken

Run on a different port:

```bash
APP_PORT=8010 ./run_local.sh
```

### Refresh automation does not appear to run

Check the generated launch agent and logs under:

- `~/Library/LaunchAgents`
- `artifacts/logs/`

### The database should live somewhere else

Override it with:

```bash
export APP_DATABASE_PATH=/absolute/path/to/app.db
```

## Current limitations

- The frontend is intentionally static and does not use React or a component framework.
- Search quality depends on local model availability when advanced ranking is desired.
- Refresh quality depends on the configured sources and local network access.
- The app is designed for local research and evaluation, not multi-user production hosting.
- The repo does not include generated demo artifacts or runtime databases by default.

If you want to evolve the project, natural next steps would be:

- richer provider branding and screenshots
- stronger filtering and comparison views
- admin tooling for curation
- optional authentication and saved shortlists
- a more advanced vector storage layer if the catalog becomes much larger
