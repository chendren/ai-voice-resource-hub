from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT_PATH = PROJECT_ROOT / 'backend' / 'app' / 'blueprint.json'
CATEGORY_ORDER = [
    'stt',
    'tts',
    'llm',
    'slm',
    'embedding',
    'realtime',
    's2s',
    'voice-agent',
    'orchestration',
    'telephony',
    'hosting',
    'container',
    'observability',
    'other',
]
SUGGESTED_QUERIES = [
    'Best local speech-to-text and TTS stack for rapid prototyping',
    'LiveKit and Pipecat resources for realtime voice agents',
    'Local models and embeddings for voice RAG applications',
    'Cloud hosting options for containerized voice AI backends',
]


def _resolve_database_path() -> Path:
    configured = os.environ.get('APP_DATABASE_PATH')
    if not configured:
        return PROJECT_ROOT / 'backend' / 'data' / 'app.db'
    path = Path(configured).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    frontend_dir: Path
    database_path: Path
    ollama_base_url: str
    embedding_model: str
    llm_model: str
    disable_ollama: bool
    embedding_dimensions: int


def load_blueprint() -> dict[str, object]:
    return json.loads(BLUEPRINT_PATH.read_text(encoding='utf-8'))


def get_settings() -> Settings:
    return Settings(
        project_root=PROJECT_ROOT,
        frontend_dir=PROJECT_ROOT / 'frontend',
        database_path=_resolve_database_path(),
        ollama_base_url=os.environ.get('VOICE_HUB_OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/'),
        embedding_model=os.environ.get('VOICE_HUB_EMBED_MODEL', 'nomic-embed-text:latest'),
        llm_model=os.environ.get('VOICE_HUB_LLM_MODEL', 'cx-intelligence-slm:latest'),
        disable_ollama=os.environ.get('VOICE_HUB_DISABLE_OLLAMA', '').lower() in {'1', 'true', 'yes'},
        embedding_dimensions=int(os.environ.get('VOICE_HUB_EMBED_DIMS', '96')),
    )


SETTINGS = get_settings()
BLUEPRINT = load_blueprint()
