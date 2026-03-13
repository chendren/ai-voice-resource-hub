#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Record a local demo of the AI Voice Resource Hub.')
    parser.add_argument('--base-url', required=True, help='Base URL of the running app, for example http://127.0.0.1:8000')
    parser.add_argument('--output-dir', '-o', required=True, help='Directory for screenshots, transcript, and video output')
    parser.add_argument(
        '--query',
        default='LiveKit and Pipecat resources for realtime voice agents',
        help='Search query used during the recorded walkthrough',
    )
    parser.add_argument('--timeout', type=float, default=20.0)
    return parser.parse_args()


def http_request(url: str, method: str = 'GET', payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            if not raw:
                return None
            if 'application/json' in response.headers.get('Content-Type', ''):
                return json.loads(raw.decode('utf-8'))
            return raw.decode('utf-8', errors='replace')
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'{method} {url} failed with {error.code}: {detail}') from error
    except urllib.error.URLError as error:
        raise RuntimeError(f'{method} {url} failed: {error.reason}') from error


def wait_for_http(url: str, timeout: float) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            http_request(url)
            return
        except RuntimeError as error:
            last_error = error
            time.sleep(0.5)
    raise SystemExit(f'error: timed out waiting for {url}: {last_error}')


def run_osascript(*lines: str) -> None:
    command = ['osascript']
    for line in lines:
        command.extend(['-e', line])
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or completed.stdout.strip())


def open_in_safari(url: str) -> None:
    run_osascript(
        'tell application "Safari" to activate',
        f'tell application "Safari" to open location "{url}"',
    )
    time.sleep(3)


def capture_screen(path: Path) -> None:
    completed = subprocess.run(['screencapture', '-x', str(path)], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or completed.stdout.strip())


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def render_video(output_dir: Path) -> Path | None:
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        return None
    video_path = output_dir / 'demo.mp4'
    completed = subprocess.run(
        [
            ffmpeg,
            '-y',
            '-framerate',
            '1',
            '-pattern_type',
            'glob',
            '-i',
            '*.png',
            '-vf',
            'scale=1440:-2,format=yuv420p',
            str(video_path),
        ],
        cwd=output_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip())
    return video_path


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip('/')
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    wait_for_http(f'{base_url}/health', args.timeout)

    dashboard = http_request(f'{base_url}/api/dashboard')
    search_params = urllib.parse.urlencode({'q': args.query})
    search_payload = http_request(f'{base_url}/api/search?{search_params}')
    refresh_payload = http_request(f'{base_url}/api/refresh', method='POST', payload={'mode': 'sample'})

    write_json(output_dir / 'dashboard.json', dashboard)
    write_json(output_dir / 'search.json', search_payload)
    write_json(output_dir / 'refresh.json', refresh_payload)

    transcript: list[dict[str, Any]] = []

    home_url = base_url
    open_in_safari(home_url)
    home_path = output_dir / '01-home.png'
    capture_screen(home_path)
    transcript.append(
        {
            'step': 'home',
            'url': home_url,
            'artifact': str(home_path),
            'summary': 'Opened the Voice Resource Hub landing page.',
            'limitation': 'Direct ChatGPT Computer Use is not exposed in this environment, so the demo uses local Safari launches and screen capture.',
        }
    )

    search_url = f'{base_url}/?{urllib.parse.urlencode({"q": args.query})}'
    open_in_safari(search_url)
    search_path = output_dir / '02-search.png'
    capture_screen(search_path)
    transcript.append(
        {
            'step': 'search',
            'url': search_url,
            'artifact': str(search_path),
            'summary': f'Loaded the semantic search view for query: {args.query}',
            'answer_preview': search_payload.get('answer', ''),
            'result_count': len(search_payload.get('results', [])),
        }
    )

    refresh_url = f'{base_url}/?{urllib.parse.urlencode({"q": args.query, "includeUpdates": "true"})}'
    open_in_safari(refresh_url)
    refresh_path = output_dir / '03-refresh.png'
    capture_screen(refresh_path)
    transcript.append(
        {
            'step': 'refresh',
            'url': refresh_url,
            'artifact': str(refresh_path),
            'summary': 'Captured the refreshed catalog after a sample refresh run.',
            'refresh_message': refresh_payload.get('message', ''),
            'items_upserted': refresh_payload.get('items_upserted', 0),
        }
    )

    transcript_path = output_dir / 'transcript.json'
    write_json(transcript_path, transcript)
    video_path = render_video(output_dir)
    result = {
        'mode': 'local-safari-screencapture',
        'transcript': str(transcript_path),
        'video': str(video_path) if video_path else None,
        'screenshots': [entry['artifact'] for entry in transcript],
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
