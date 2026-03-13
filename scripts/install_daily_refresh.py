#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABEL = 'com.chadhendren.voice-resource-hub.refresh'
ENV_KEYS = [
    'APP_DATABASE_PATH',
    'VOICE_HUB_DISABLE_OLLAMA',
    'VOICE_HUB_OLLAMA_URL',
    'VOICE_HUB_EMBED_MODEL',
    'VOICE_HUB_LLM_MODEL',
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Install a daily macOS launch agent for catalog refresh.')
    parser.add_argument('--label', default=DEFAULT_LABEL)
    parser.add_argument('--hour', type=int, default=8)
    parser.add_argument('--minute', type=int, default=15)
    parser.add_argument('--mode', choices=['smart', 'remote', 'sample'], default='smart')
    parser.add_argument('--load', action='store_true', help='Load the launch agent after writing it.')
    return parser.parse_args()


def build_plist(label: str, hour: int, minute: int, mode: str) -> dict[str, object]:
    logs_dir = PROJECT_ROOT / 'artifacts' / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    script_path = PROJECT_ROOT / 'scripts' / 'refresh_catalog.py'
    environment = {key: value for key, value in os.environ.items() if key in ENV_KEYS and value}
    environment.setdefault('PATH', os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin'))
    return {
        'Label': label,
        'ProgramArguments': [sys.executable, str(script_path), '--mode', mode],
        'WorkingDirectory': str(PROJECT_ROOT),
        'RunAtLoad': True,
        'StartCalendarInterval': {'Hour': hour, 'Minute': minute},
        'StandardOutPath': str(logs_dir / 'refresh.stdout.log'),
        'StandardErrorPath': str(logs_dir / 'refresh.stderr.log'),
        'EnvironmentVariables': environment,
    }


def write_plist(destination: Path, payload: dict[str, object]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('wb') as handle:
        plistlib.dump(payload, handle)


def load_agent(destination: Path) -> None:
    domain = f'gui/{os.getuid()}'
    subprocess.run(['launchctl', 'bootout', domain, str(destination)], check=False, capture_output=True)
    subprocess.run(['launchctl', 'bootstrap', domain, str(destination)], check=True)


def main() -> int:
    args = parse_args()
    if not (0 <= args.hour <= 23 and 0 <= args.minute <= 59):
        raise SystemExit('hour must be 0-23 and minute must be 0-59')
    destination = Path.home() / 'Library' / 'LaunchAgents' / f'{args.label}.plist'
    payload = build_plist(args.label, args.hour, args.minute, args.mode)
    write_plist(destination, payload)
    if args.load:
        load_agent(destination)
    print(destination)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
