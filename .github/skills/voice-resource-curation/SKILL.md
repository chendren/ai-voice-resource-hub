---
name: voice-resource-curation
description: Use this skill when expanding the AI Voice Resource Hub catalog, tuning semantic search, adjusting categories, or improving the frontend experience for voice AI discovery.
---

# Voice Resource Curation

Use this skill when the task is about voice AI resources, search quality, or catalog UX.

## Use this skill for

- adding or updating curated resources in `backend/app/seed_data.py`
- expanding feed coverage in `backend/app/refresh_service.py`
- tuning semantic search, reranking, or answer generation in `backend/app/search_service.py`
- adjusting category order or labels in `backend/app/config.py` and `frontend/app.js`
- improving the catalog presentation in `frontend/index.html`, `frontend/app.js`, or `frontend/styles.css`

## Working rules

1. Start by checking the current contract:
   - `backend/app/main.py`
   - `backend/app/config.py`
   - `backend/tests/test_api.py`
2. When you add a new category or filter, update backend and frontend together.
3. Keep resource metadata concrete:
   - provider
   - category
   - summary
   - tags
   - deployment
   - pricing model
   - freshness metadata
4. Prefer grounded retrieval and explicit scoring changes over vague prompt-only fixes.
5. If refresh or ranking behavior changes, run sample refresh plus backend tests.

## Validation

```bash
python3 -m py_compile backend/app/*.py backend/tests/test_api.py scripts/*.py
python3 -m unittest discover -s backend/tests
node --check frontend/app.js
python3 scripts/refresh_catalog.py --mode sample
```
