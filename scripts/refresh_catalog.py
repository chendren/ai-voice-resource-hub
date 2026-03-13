#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'backend'))

from app.database import get_connection, initialize_database, latest_refresh_runs, resource_counts, seed_database  # noqa: E402
from app.ollama_client import OllamaClient  # noqa: E402
from app.refresh_service import run_refresh  # noqa: E402
from app.search_service import SearchService  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Refresh the AI Voice Resource Hub catalog and embeddings.')
    parser.add_argument('--mode', choices=['smart', 'remote', 'sample'], default='smart')
    parser.add_argument('--json', action='store_true', help='Print the result as JSON.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    search_service = SearchService(OllamaClient())
    with get_connection() as connection:
        initialize_database(connection)
        seed_database(connection)
        result = run_refresh(connection, mode=args.mode)
        search_service.ensure_embeddings(connection)
        payload = {
            **result,
            'stats': resource_counts(connection),
            'latest_run': latest_refresh_runs(connection, limit=1)[0],
        }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"status: {payload['status']}")
        print(f"message: {payload['message']}")
        print(f"items_upserted: {payload['items_upserted']}")
        print(f"curated_count: {payload['stats']['curated_count']}")
        print(f"update_count: {payload['stats']['update_count']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
