#!/usr/bin/env python3
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .config import BLUEPRINT, CATEGORY_ORDER, SETTINGS, SUGGESTED_QUERIES
from .database import (
    get_connection,
    get_resource,
    initialize_database,
    latest_refresh_runs,
    list_feed_sources,
    list_resources,
    resource_counts,
    seed_database,
)
from .ollama_client import OllamaClient
from .refresh_service import run_refresh
from .search_service import SearchService


model_client = OllamaClient()
search_service = SearchService(model_client)


def model_status_payload() -> dict[str, Any]:
    status = model_client.status()
    return {
        'available': status.available,
        'embedding_model': status.embedding_model,
        'llm_model': status.llm_model,
        'detail': status.detail,
    }


def filter_resources(
    resources: list[dict[str, Any]],
    *,
    provider: str | None = None,
    local_only: bool = False,
    hosted_only: bool = False,
    open_source_only: bool = False,
) -> list[dict[str, Any]]:
    filtered = resources
    if provider:
        provider_normalized = provider.strip().lower()
        filtered = [item for item in filtered if item['provider'].lower() == provider_normalized]
    if local_only:
        filtered = [item for item in filtered if item['local_model_ready']]
    if hosted_only:
        filtered = [item for item in filtered if item['hosted_service']]
    if open_source_only:
        filtered = [item for item in filtered if item['open_source']]
    return filtered


def build_dashboard(connection) -> dict[str, Any]:
    curated_resources = list_resources(connection, record_type='resource', limit=80)
    updates = list_resources(connection, record_type='update', limit=8)
    stats = resource_counts(connection)
    category_counts = [
        {
            'category': category,
            'count': stats['category_counts'].get(category, 0),
        }
        for category in CATEGORY_ORDER
    ]
    category_spotlights = []
    for category in CATEGORY_ORDER:
        matches = [item for item in curated_resources if item['category'] == category][:2]
        if matches:
            category_spotlights.append(
                {
                    'category': category,
                    'resources': matches,
                }
            )
    return {
        'stats': stats,
        'categories': category_counts,
        'spotlights': category_spotlights,
        'featured': {
            'local_ready': [item for item in curated_resources if item['local_model_ready']][:6],
            'cloud_ready': [item for item in curated_resources if item['hosted_service']][:6],
            'open_source': [item for item in curated_resources if item['open_source']][:6],
            'realtime_stack': [
                item
                for item in curated_resources
                if item['category'] in {'realtime', 'voice-agent', 'orchestration', 'telephony', 's2s'}
            ][:6],
        },
        'updates': updates,
        'feed_sources': list_feed_sources(connection),
        'refresh_runs': latest_refresh_runs(connection, limit=10),
        'suggested_queries': SUGGESTED_QUERIES,
        'model_status': model_status_payload(),
    }


def maybe_run_startup_refresh(connection) -> None:
    startup_mode = os.environ.get('VOICE_HUB_STARTUP_REFRESH_MODE', 'smart').strip().lower() or 'smart'
    if startup_mode == 'off':
        return
    if latest_refresh_runs(connection, limit=1):
        return
    run_refresh(connection, mode=startup_mode)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with get_connection() as connection:
        initialize_database(connection)
        seed_database(connection)
        maybe_run_startup_refresh(connection)
        search_service.ensure_embeddings(connection)
    yield


app = FastAPI(title=BLUEPRINT['display_name'], lifespan=lifespan)


@app.get('/health')
def health() -> dict[str, Any]:
    return {
        'status': 'ok',
        'project': BLUEPRINT['display_name'],
        'models': model_status_payload(),
    }


@app.get('/api/meta')
def meta() -> dict[str, Any]:
    return {
        'project_name': BLUEPRINT['project_name'],
        'display_name': BLUEPRINT['display_name'],
        'description': BLUEPRINT['description'],
        'categories': CATEGORY_ORDER,
        'suggested_queries': SUGGESTED_QUERIES,
        'model_status': model_status_payload(),
        'capabilities': {
            'semantic_search': True,
            'rag_answers': True,
            'local_reranking': True,
            'daily_refresh_agent': True,
        },
    }


@app.get('/api/dashboard')
def dashboard() -> dict[str, Any]:
    with get_connection() as connection:
        return build_dashboard(connection)


@app.get('/api/resources')
def resources(
    category: str | None = Query(default=None),
    record_type: str = Query(default='resource', pattern='^(resource|update|all)$'),
    provider: str | None = Query(default=None),
    local_only: bool = Query(default=False),
    hosted_only: bool = Query(default=False),
    open_source_only: bool = Query(default=False),
    limit: int = Query(default=36, ge=1, le=100),
) -> dict[str, Any]:
    with get_connection() as connection:
        selected_type = None if record_type == 'all' else record_type
        items = list_resources(connection, category=category, record_type=selected_type, limit=120)
        items = filter_resources(
            items,
            provider=provider,
            local_only=local_only,
            hosted_only=hosted_only,
            open_source_only=open_source_only,
        )
        return {
            'count': len(items[:limit]),
            'results': items[:limit],
        }


@app.get('/api/resources/{resource_id}')
def resource_detail(resource_id: int) -> dict[str, Any]:
    with get_connection() as connection:
        resource = get_resource(connection, resource_id)
        if resource is None:
            raise HTTPException(status_code=404, detail='Resource not found')
        return resource


@app.get('/api/search')
def search(
    q: str = Query(min_length=2),
    category: str | None = Query(default=None),
    include_updates: bool = Query(default=True),
    limit: int = Query(default=8, ge=1, le=20),
) -> dict[str, Any]:
    with get_connection() as connection:
        return search_service.search(
            connection,
            query=q,
            category=category,
            include_updates=include_updates,
            limit=limit,
        )


@app.get('/api/feed-sources')
def feed_sources() -> dict[str, Any]:
    with get_connection() as connection:
        return {'results': list_feed_sources(connection)}


@app.get('/api/refresh-runs')
def refresh_runs(limit: int = Query(default=10, ge=1, le=50)) -> dict[str, Any]:
    with get_connection() as connection:
        return {'results': latest_refresh_runs(connection, limit=limit)}


@app.post('/api/refresh')
def refresh(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    mode = 'smart'
    if payload:
        requested = str(payload.get('mode', 'smart')).strip().lower()
        if requested not in {'smart', 'remote', 'sample'}:
            raise HTTPException(status_code=400, detail='mode must be one of: smart, remote, sample')
        mode = requested
    with get_connection() as connection:
        result = run_refresh(connection, mode=mode)
        search_service.ensure_embeddings(connection)
        return {
            **result,
            'dashboard': build_dashboard(connection),
        }


app.mount('/', StaticFiles(directory=SETTINGS.frontend_dir, html=True), name='frontend')
