---
name: voice-resource-ops
description: Use this skill when running the AI Voice Resource Hub locally, refreshing the catalog, validating Ollama usage, installing daily macOS refresh automation, or recording demo evidence.
---

# Voice Resource Operations

Use this skill when the task is about running, refreshing, validating, or demoing the app.

## Use this skill for

- starting the app with `./run_local.sh`
- checking `/health`, `/api/dashboard`, `/api/search`, and `/api/refresh`
- running `python3 scripts/refresh_catalog.py`
- installing or updating the launch agent with `python3 scripts/install_daily_refresh.py`
- recording local demo artifacts with `python3 scripts/record_demo.py`
- reviewing hook logs under `artifacts/`

## Workflow

1. Verify local model readiness from `/health` or `/api/meta`.
2. Run a refresh before demoing if freshness-sensitive changes were made.
3. For offline validation, use `--mode sample`.
4. Capture evidence when the task changes UI, search, or refresh behavior.
5. If the environment cannot expose direct browser automation, use the built-in local screen capture workflow and document the limitation explicitly.

## Validation commands

```bash
python3 scripts/refresh_catalog.py --mode sample
python3 -m unittest discover -s backend/tests
python3 scripts/record_demo.py --base-url http://127.0.0.1:8000 --output-dir artifacts/demo
```
