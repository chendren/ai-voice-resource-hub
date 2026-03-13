from __future__ import annotations

import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from .database import (
    finish_refresh_run,
    list_feed_sources,
    now_iso,
    start_refresh_run,
    update_feed_checked_at,
    upsert_resource,
)
from .seed_data import SAMPLE_FEED_ITEMS


ATOM_NS = {'atom': 'http://www.w3.org/2005/Atom'}


def _iso_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
        except ValueError:
            return None


def fetch_feed_entries(url: str, kind: str) -> list[dict[str, Any]]:
    with urllib.request.urlopen(url, timeout=8) as response:
        body = response.read()
    root = ET.fromstring(body)
    entries: list[dict[str, Any]] = []
    if kind == 'atom' or root.tag.endswith('feed'):
        for entry in root.findall('atom:entry', ATOM_NS):
            title = (entry.findtext('atom:title', default='', namespaces=ATOM_NS) or '').strip()
            link_node = entry.find('atom:link', ATOM_NS)
            link = link_node.attrib.get('href', '') if link_node is not None else ''
            summary = (entry.findtext('atom:summary', default='', namespaces=ATOM_NS) or '').strip()
            published = entry.findtext('atom:updated', default='', namespaces=ATOM_NS)
            if title and link:
                entries.append(
                    {
                        'title': title,
                        'link': link,
                        'summary': summary,
                        'published': _iso_datetime(published) or now_iso(),
                    }
                )
    else:
        for item in root.findall('./channel/item'):
            title = (item.findtext('title') or '').strip()
            link = (item.findtext('link') or '').strip()
            summary = (item.findtext('description') or '').strip()
            published = _iso_datetime(item.findtext('pubDate')) or now_iso()
            if title and link:
                entries.append(
                    {
                        'title': title,
                        'link': link,
                        'summary': summary,
                        'published': published,
                    }
                )
    return entries


def classify_update(entry: dict[str, Any], category_hint: str) -> dict[str, Any]:
    title = entry['title']
    lowered = title.lower()
    provider = entry.get('provider') or title.split()[0]
    category = category_hint
    if 'livekit' in lowered:
        provider = 'LiveKit'
        category = 'voice-agent'
    elif 'pipecat' in lowered:
        provider = 'Pipecat'
        category = 'orchestration'
    elif 'ollama' in lowered:
        provider = 'Ollama'
        category = 'slm'
    elif 'piper' in lowered:
        provider = 'Rhasspy'
        category = 'tts'
    tags = [provider.lower(), category, 'update']
    return {
        'provider': provider,
        'category': category,
        'tags': tags,
    }


def build_update_payload(entry: dict[str, Any], category_hint: str) -> dict[str, Any]:
    classified = classify_update(entry, category_hint)
    return {
        'record_type': 'update',
        'name': entry['title'],
        'provider': classified['provider'],
        'category': classified['category'],
        'summary': entry['summary'],
        'resource_url': entry['link'],
        'tags': classified['tags'],
        'local_model_ready': False,
        'hosted_service': True,
        'open_source': False,
        'deployment': 'external update feed',
        'pricing_model': 'n/a',
        'source_name': entry['source_name'],
        'source_type': 'feed',
        'source_url': entry['link'],
        'last_updated': entry['published'],
    }


def run_refresh(connection, *, mode: str = 'smart') -> dict[str, Any]:
    run_id = start_refresh_run(connection, mode)
    discovered_entries: list[dict[str, Any]] = []
    checked_sources: list[str] = []
    used_sample_fallback = False
    feed_sources = [source for source in list_feed_sources(connection) if source['enabled']]
    if mode in {'smart', 'remote'}:
        for source in feed_sources:
            try:
                entries = fetch_feed_entries(source['url'], source['kind'])
            except (urllib.error.URLError, ET.ParseError, TimeoutError, ValueError):
                continue
            for entry in entries[:6]:
                discovered_entries.append({**entry, 'source_name': source['name'], 'category_hint': source['category_hint']})
            checked_sources.append(source['name'])
    if mode == 'sample' or (mode == 'smart' and not discovered_entries):
        discovered_entries = [dict(item) for item in SAMPLE_FEED_ITEMS]
        used_sample_fallback = True
        checked_sources = [item['source_name'] for item in SAMPLE_FEED_ITEMS]
    upserted = 0
    for entry in discovered_entries:
        payload = build_update_payload(entry, entry.get('category_hint', 'other'))
        upsert_resource(connection, payload)
        upserted += 1
    if checked_sources:
        update_feed_checked_at(connection, checked_sources)
    message = 'Refresh completed using sample fallback.' if used_sample_fallback else 'Refresh completed from remote feeds.'
    finish_refresh_run(
        connection,
        run_id,
        status='completed',
        message=message,
        items_discovered=len(discovered_entries),
        items_upserted=upserted,
        used_sample_fallback=used_sample_fallback,
    )
    return {
        'run_id': run_id,
        'status': 'completed',
        'message': message,
        'items_discovered': len(discovered_entries),
        'items_upserted': upserted,
        'used_sample_fallback': used_sample_fallback,
    }
