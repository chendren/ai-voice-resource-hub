from __future__ import annotations

import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import CATEGORY_ORDER, SETTINGS
from .seed_data import DEFAULT_FEED_SOURCES, SEED_RESOURCES


IDENTIFIER_PATTERN = re.compile(r'^[a-z_][a-z0-9_]*$')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(text: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', text.strip().lower()).strip('-')
    slug = re.sub(r'-{2,}', '-', slug)
    return slug or 'voice-resource'


def identifier(name: str) -> str:
    if not IDENTIFIER_PATTERN.fullmatch(name):
        raise ValueError(f'invalid identifier: {name}')
    return name


def get_connection() -> sqlite3.Connection:
    SETTINGS.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(SETTINGS.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        '''
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            record_type TEXT NOT NULL DEFAULT 'resource',
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            category TEXT NOT NULL,
            summary TEXT NOT NULL,
            resource_url TEXT NOT NULL,
            tags_json TEXT NOT NULL DEFAULT '[]',
            tags_text TEXT NOT NULL DEFAULT '',
            local_model_ready INTEGER NOT NULL DEFAULT 0,
            hosted_service INTEGER NOT NULL DEFAULT 0,
            open_source INTEGER NOT NULL DEFAULT 0,
            deployment TEXT NOT NULL DEFAULT '',
            pricing_model TEXT NOT NULL DEFAULT '',
            source_name TEXT NOT NULL DEFAULT '',
            source_type TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            freshness_score INTEGER NOT NULL DEFAULT 50,
            related_resource_slug TEXT,
            last_verified_at TEXT,
            last_updated TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS resource_embeddings (
            resource_id INTEGER PRIMARY KEY,
            model TEXT NOT NULL,
            vector_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(resource_id) REFERENCES resources(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS feed_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL,
            kind TEXT NOT NULL,
            category_hint TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            update_interval_hours INTEGER NOT NULL DEFAULT 24,
            last_checked_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS refresh_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            items_discovered INTEGER NOT NULL DEFAULT 0,
            items_upserted INTEGER NOT NULL DEFAULT 0,
            used_sample_fallback INTEGER NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL,
            finished_at TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS resources_fts USING fts5(
            name,
            provider,
            category,
            summary,
            tags_text,
            deployment,
            pricing_model,
            content='resources',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS resources_ai AFTER INSERT ON resources BEGIN
            INSERT INTO resources_fts(rowid, name, provider, category, summary, tags_text, deployment, pricing_model)
            VALUES (new.id, new.name, new.provider, new.category, new.summary, new.tags_text, new.deployment, new.pricing_model);
        END;

        CREATE TRIGGER IF NOT EXISTS resources_ad AFTER DELETE ON resources BEGIN
            INSERT INTO resources_fts(resources_fts, rowid, name, provider, category, summary, tags_text, deployment, pricing_model)
            VALUES ('delete', old.id, old.name, old.provider, old.category, old.summary, old.tags_text, old.deployment, old.pricing_model);
        END;

        CREATE TRIGGER IF NOT EXISTS resources_au AFTER UPDATE ON resources BEGIN
            INSERT INTO resources_fts(resources_fts, rowid, name, provider, category, summary, tags_text, deployment, pricing_model)
            VALUES ('delete', old.id, old.name, old.provider, old.category, old.summary, old.tags_text, old.deployment, old.pricing_model);
            INSERT INTO resources_fts(rowid, name, provider, category, summary, tags_text, deployment, pricing_model)
            VALUES (new.id, new.name, new.provider, new.category, new.summary, new.tags_text, new.deployment, new.pricing_model);
        END;
        '''
    )
    connection.commit()


def compute_freshness_score(last_updated: str | None) -> int:
    if not last_updated:
        return 50
    try:
        parsed = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
    except ValueError:
        return 50
    delta_days = max((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days, 0)
    score = max(15, 100 - delta_days)
    return int(score)


def normalize_tags(tags: Iterable[str] | str | None) -> tuple[str, str]:
    if tags is None:
        values: list[str] = []
    elif isinstance(tags, str):
        values = [item.strip() for item in tags.split(',') if item.strip()]
    else:
        values = [str(item).strip() for item in tags if str(item).strip()]
    deduped = list(dict.fromkeys(values))
    return json.dumps(deduped), ', '.join(deduped)


def resource_document(resource: dict[str, Any]) -> str:
    return ' | '.join(
        str(resource.get(key, ''))
        for key in ('name', 'provider', 'category', 'summary', 'tags_text', 'deployment', 'pricing_model')
    )


def row_to_resource(row: sqlite3.Row) -> dict[str, Any]:
    return {
        'id': row['id'],
        'slug': row['slug'],
        'record_type': row['record_type'],
        'name': row['name'],
        'provider': row['provider'],
        'category': row['category'],
        'summary': row['summary'],
        'resource_url': row['resource_url'],
        'tags': json.loads(row['tags_json']),
        'local_model_ready': bool(row['local_model_ready']),
        'hosted_service': bool(row['hosted_service']),
        'open_source': bool(row['open_source']),
        'deployment': row['deployment'],
        'pricing_model': row['pricing_model'],
        'source_name': row['source_name'],
        'source_type': row['source_type'],
        'source_url': row['source_url'],
        'freshness_score': row['freshness_score'],
        'related_resource_slug': row['related_resource_slug'],
        'last_verified_at': row['last_verified_at'],
        'last_updated': row['last_updated'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def upsert_resource(connection: sqlite3.Connection, payload: dict[str, Any]) -> int:
    timestamp = now_iso()
    slug = payload.get('slug') or slugify(f"{payload.get('provider', '')}-{payload.get('name', '')}-{payload.get('record_type', 'resource')}")
    tags_json, tags_text = normalize_tags(payload.get('tags'))
    values = {
        'slug': slug,
        'record_type': payload.get('record_type', 'resource'),
        'name': payload['name'],
        'provider': payload['provider'],
        'category': payload['category'],
        'summary': payload['summary'],
        'resource_url': payload['resource_url'],
        'tags_json': tags_json,
        'tags_text': tags_text,
        'local_model_ready': int(bool(payload.get('local_model_ready'))),
        'hosted_service': int(bool(payload.get('hosted_service'))),
        'open_source': int(bool(payload.get('open_source'))),
        'deployment': payload.get('deployment', ''),
        'pricing_model': payload.get('pricing_model', ''),
        'source_name': payload.get('source_name', ''),
        'source_type': payload.get('source_type', ''),
        'source_url': payload.get('source_url', payload.get('resource_url', '')),
        'freshness_score': payload.get('freshness_score') or compute_freshness_score(payload.get('last_updated')),
        'related_resource_slug': payload.get('related_resource_slug'),
        'last_verified_at': payload.get('last_verified_at'),
        'last_updated': payload.get('last_updated'),
        'created_at': payload.get('created_at', timestamp),
        'updated_at': timestamp,
    }
    connection.execute(
        '''
        INSERT INTO resources (
            slug, record_type, name, provider, category, summary, resource_url,
            tags_json, tags_text, local_model_ready, hosted_service, open_source,
            deployment, pricing_model, source_name, source_type, source_url,
            freshness_score, related_resource_slug, last_verified_at, last_updated,
            created_at, updated_at
        ) VALUES (
            :slug, :record_type, :name, :provider, :category, :summary, :resource_url,
            :tags_json, :tags_text, :local_model_ready, :hosted_service, :open_source,
            :deployment, :pricing_model, :source_name, :source_type, :source_url,
            :freshness_score, :related_resource_slug, :last_verified_at, :last_updated,
            :created_at, :updated_at
        )
        ON CONFLICT(slug) DO UPDATE SET
            record_type = excluded.record_type,
            name = excluded.name,
            provider = excluded.provider,
            category = excluded.category,
            summary = excluded.summary,
            resource_url = excluded.resource_url,
            tags_json = excluded.tags_json,
            tags_text = excluded.tags_text,
            local_model_ready = excluded.local_model_ready,
            hosted_service = excluded.hosted_service,
            open_source = excluded.open_source,
            deployment = excluded.deployment,
            pricing_model = excluded.pricing_model,
            source_name = excluded.source_name,
            source_type = excluded.source_type,
            source_url = excluded.source_url,
            freshness_score = excluded.freshness_score,
            related_resource_slug = excluded.related_resource_slug,
            last_verified_at = COALESCE(excluded.last_verified_at, resources.last_verified_at),
            last_updated = COALESCE(excluded.last_updated, resources.last_updated),
            updated_at = excluded.updated_at
        ''',
        values,
    )
    row = connection.execute('SELECT id FROM resources WHERE slug = ?', (slug,)).fetchone()
    connection.commit()
    if row is None:
        raise RuntimeError(f'failed to upsert resource {slug}')
    return int(row['id'])


def seed_database(connection: sqlite3.Connection) -> None:
    resource_count = connection.execute('SELECT COUNT(*) AS count FROM resources').fetchone()['count']
    if resource_count == 0:
        for resource in SEED_RESOURCES:
            upsert_resource(connection, resource)
    source_count = connection.execute('SELECT COUNT(*) AS count FROM feed_sources').fetchone()['count']
    if source_count == 0:
        timestamp = now_iso()
        connection.executemany(
            '''
            INSERT INTO feed_sources (name, url, kind, category_hint, enabled, update_interval_hours, created_at, updated_at)
            VALUES (:name, :url, :kind, :category_hint, :enabled, :update_interval_hours, :created_at, :updated_at)
            ''',
            [
                {
                    **source,
                    'enabled': int(bool(source.get('enabled', True))),
                    'created_at': timestamp,
                    'updated_at': timestamp,
                }
                for source in DEFAULT_FEED_SOURCES
            ],
        )
        connection.commit()


def list_resources(
    connection: sqlite3.Connection,
    *,
    category: str | None = None,
    record_type: str | None = None,
    limit: int = 24,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if category:
        conditions.append('category = ?')
        params.append(category)
    if record_type:
        conditions.append('record_type = ?')
        params.append(record_type)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ''
    rows = connection.execute(
        f'''
        SELECT * FROM resources
        {where_clause}
        ORDER BY freshness_score DESC, updated_at DESC, name ASC
        LIMIT ?
        ''',
        (*params, limit),
    ).fetchall()
    return [row_to_resource(row) for row in rows]


def get_resource(connection: sqlite3.Connection, resource_id: int) -> dict[str, Any] | None:
    row = connection.execute('SELECT * FROM resources WHERE id = ?', (resource_id,)).fetchone()
    return None if row is None else row_to_resource(row)


def list_feed_sources(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        'SELECT * FROM feed_sources ORDER BY enabled DESC, name ASC'
    ).fetchall()
    return [dict(row) for row in rows]


def latest_refresh_runs(connection: sqlite3.Connection, limit: int = 10) -> list[dict[str, Any]]:
    rows = connection.execute(
        'SELECT * FROM refresh_runs ORDER BY started_at DESC, id DESC LIMIT ?', (limit,)
    ).fetchall()
    return [dict(row) for row in rows]


def start_refresh_run(connection: sqlite3.Connection, mode: str) -> int:
    cursor = connection.execute(
        '''
        INSERT INTO refresh_runs (mode, status, message, started_at)
        VALUES (?, 'running', '', ?)
        ''',
        (mode, now_iso()),
    )
    connection.commit()
    return int(cursor.lastrowid)


def finish_refresh_run(
    connection: sqlite3.Connection,
    run_id: int,
    *,
    status: str,
    message: str,
    items_discovered: int,
    items_upserted: int,
    used_sample_fallback: bool,
) -> None:
    connection.execute(
        '''
        UPDATE refresh_runs
        SET status = ?, message = ?, items_discovered = ?, items_upserted = ?,
            used_sample_fallback = ?, finished_at = ?
        WHERE id = ?
        ''',
        (
            status,
            message,
            items_discovered,
            items_upserted,
            int(used_sample_fallback),
            now_iso(),
            run_id,
        ),
    )
    connection.commit()


def update_feed_checked_at(connection: sqlite3.Connection, source_names: Iterable[str]) -> None:
    timestamp = now_iso()
    for source_name in source_names:
        connection.execute(
            'UPDATE feed_sources SET last_checked_at = ?, updated_at = ? WHERE name = ?',
            (timestamp, timestamp, source_name),
        )
    connection.commit()


def upsert_embedding(connection: sqlite3.Connection, resource_id: int, model: str, vector: list[float]) -> None:
    connection.execute(
        '''
        INSERT INTO resource_embeddings (resource_id, model, vector_json, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(resource_id) DO UPDATE SET
            model = excluded.model,
            vector_json = excluded.vector_json,
            updated_at = excluded.updated_at
        ''',
        (resource_id, model, json.dumps(vector), now_iso()),
    )
    connection.commit()


def get_all_embeddings(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        '''
        SELECT r.id, r.record_type, r.category, r.provider, r.name, r.summary, r.tags_text, r.deployment,
               e.model, e.vector_json
        FROM resource_embeddings e
        JOIN resources r ON r.id = e.resource_id
        ''',
    ).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                'id': row['id'],
                'record_type': row['record_type'],
                'category': row['category'],
                'provider': row['provider'],
                'name': row['name'],
                'summary': row['summary'],
                'tags_text': row['tags_text'],
                'deployment': row['deployment'],
                'model': row['model'],
                'vector': json.loads(row['vector_json']),
            }
        )
    return results


def resource_counts(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = connection.execute(
        'SELECT category, COUNT(*) AS count FROM resources WHERE record_type = ? GROUP BY category',
        ('resource',),
    ).fetchall()
    category_counts = {category: 0 for category in CATEGORY_ORDER}
    for row in rows:
        category_counts[row['category']] = row['count']
    totals = connection.execute(
        '''
        SELECT
            SUM(CASE WHEN record_type = 'resource' THEN 1 ELSE 0 END) AS curated_count,
            SUM(CASE WHEN record_type = 'update' THEN 1 ELSE 0 END) AS update_count,
            COUNT(*) AS total_count
        FROM resources
        '''
    ).fetchone()
    return {
        'category_counts': category_counts,
        'curated_count': totals['curated_count'] or 0,
        'update_count': totals['update_count'] or 0,
        'total_count': totals['total_count'] or 0,
    }
