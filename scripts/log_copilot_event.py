#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print('usage: log_copilot_event.py <event-name>', file=sys.stderr)
        return 1

    event_name = sys.argv[1]
    payload_text = sys.stdin.read().strip()
    payload: dict[str, object] | str
    if payload_text:
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            payload = payload_text
    else:
        payload = {}

    artifact_dir = Path('artifacts')
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_path = artifact_dir / 'copilot-hook-events.jsonl'
    event = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'event': event_name,
        'payload': payload,
    }
    with log_path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(event, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
