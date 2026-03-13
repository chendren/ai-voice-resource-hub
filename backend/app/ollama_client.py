from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from .config import SETTINGS


@dataclass
class ModelStatus:
    available: bool
    embedding_model: str
    llm_model: str
    detail: str


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = SETTINGS.ollama_base_url
        self.embedding_model = SETTINGS.embedding_model
        self.llm_model = SETTINGS.llm_model
        self.disable_ollama = SETTINGS.disable_ollama
        self.timeout = httpx.Timeout(20.0, connect=5.0)

    def status(self) -> ModelStatus:
        if self.disable_ollama:
            return ModelStatus(False, self.embedding_model, self.llm_model, 'disabled by environment')
        try:
            response = httpx.get(f'{self.base_url}/api/tags', timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            available_models = {item.get('name') for item in payload.get('models', [])}
            detail = 'available'
            if self.embedding_model not in available_models or self.llm_model not in available_models:
                detail = 'running, but one or more configured models are missing'
            return ModelStatus(True, self.embedding_model, self.llm_model, detail)
        except Exception as error:  # explicit surface later via status detail
            return ModelStatus(False, self.embedding_model, self.llm_model, str(error))

    def embed_text(self, text: str) -> list[float] | None:
        if self.disable_ollama:
            return None
        payload = {'model': self.embedding_model, 'input': text}
        try:
            response = httpx.post(f'{self.base_url}/api/embed', json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return None
        embeddings = data.get('embeddings')
        if isinstance(embeddings, list) and embeddings:
            vector = embeddings[0]
            if isinstance(vector, list):
                return [float(value) for value in vector]
        vector = data.get('embedding')
        if isinstance(vector, list):
            return [float(value) for value in vector]
        return None

    def generate_text(self, prompt: str, *, system: str | None = None) -> str | None:
        if self.disable_ollama:
            return None
        body: dict[str, Any] = {
            'model': self.llm_model,
            'prompt': prompt if system is None else f'SYSTEM:\n{system}\n\nUSER:\n{prompt}',
            'stream': False,
        }
        try:
            response = httpx.post(f'{self.base_url}/api/generate', json=body, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return None
        result = data.get('response')
        return result.strip() if isinstance(result, str) else None

    def generate_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any] | None:
        if self.disable_ollama:
            return None
        body: dict[str, Any] = {
            'model': self.llm_model,
            'prompt': prompt if system is None else f'SYSTEM:\n{system}\n\nUSER:\n{prompt}',
            'stream': False,
            'format': 'json',
        }
        try:
            response = httpx.post(f'{self.base_url}/api/generate', json=body, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return None
        raw = data.get('response')
        if not isinstance(raw, str):
            return None
        raw = raw.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find('{')
            end = raw.rfind('}')
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                return None
