from __future__ import annotations

import math
import re
from typing import Any

from .config import SETTINGS
from .database import get_resource, get_all_embeddings, resource_document, upsert_embedding
from .ollama_client import OllamaClient


TOKEN_PATTERN = re.compile(r'[a-zA-Z0-9]+')


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def fallback_embedding(text: str, dimensions: int = 96) -> list[float]:
    vector = [0.0] * dimensions
    tokens = tokenize(text)
    if not tokens:
        return vector
    for token in tokens:
        slot = hash(token) % dimensions
        vector[slot] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    limit = min(len(left), len(right))
    if limit == 0:
        return 0.0
    numerator = sum(left[index] * right[index] for index in range(limit))
    left_magnitude = math.sqrt(sum(value * value for value in left[:limit])) or 1.0
    right_magnitude = math.sqrt(sum(value * value for value in right[:limit])) or 1.0
    return numerator / (left_magnitude * right_magnitude)


class SearchService:
    def __init__(self, model_client: OllamaClient) -> None:
        self.model_client = model_client

    def embed_text(self, text: str) -> list[float]:
        vector = self.model_client.embed_text(text)
        if vector:
            return vector
        return fallback_embedding(text, SETTINGS.embedding_dimensions)

    def ensure_embeddings(self, connection) -> None:
        model_status = self.model_client.status()
        model_name = SETTINGS.embedding_model if model_status.available else 'fallback-hash'
        rows = connection.execute('SELECT * FROM resources').fetchall()
        for row in rows:
            row_dict = dict(row)
            document = resource_document(row_dict)
            vector = self.embed_text(document)
            upsert_embedding(connection, row['id'], model_name, vector)

    def lexical_candidates(self, connection, query: str, *, category: str | None, include_updates: bool) -> dict[int, float]:
        tokens = tokenize(query)
        if not tokens:
            return {}
        match_query = ' OR '.join(tokens)
        conditions = []
        params: list[Any] = [match_query]
        if category:
            conditions.append('r.category = ?')
            params.append(category)
        if not include_updates:
            conditions.append("r.record_type = 'resource'")
        where_clause = ' AND ' + ' AND '.join(conditions) if conditions else ''
        rows = connection.execute(
            f'''
            SELECT r.id, bm25(resources_fts, 5.0, 3.0, 2.0, 1.5, 1.0, 1.0, 1.0) AS lexical_score
            FROM resources_fts
            JOIN resources r ON r.id = resources_fts.rowid
            WHERE resources_fts MATCH ? {where_clause}
            ORDER BY lexical_score ASC
            LIMIT 24
            ''',
            params,
        ).fetchall()
        results: dict[int, float] = {}
        for row in rows:
            score = row['lexical_score']
            normalized = 1.0 / (1.0 + max(score, 0.0))
            results[row['id']] = normalized
        return results

    def semantic_candidates(self, connection, query: str, *, category: str | None, include_updates: bool) -> dict[int, float]:
        query_vector = self.embed_text(query)
        results: dict[int, float] = {}
        for item in get_all_embeddings(connection):
            if category and item['category'] != category:
                continue
            if not include_updates and item['record_type'] != 'resource':
                continue
            score = cosine_similarity(query_vector, item['vector'])
            results[item['id']] = max(score, 0.0)
        return results

    def heuristics_bonus(self, resource: dict[str, Any], query: str) -> float:
        lowered = query.lower()
        bonus = 0.0
        if resource['category'] in lowered:
            bonus += 0.08
        if 'local' in lowered and resource['local_model_ready']:
            bonus += 0.08
        if 'cloud' in lowered and resource['hosted_service']:
            bonus += 0.05
        if resource['record_type'] == 'resource':
            bonus += 0.03
        return bonus

    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
        status = self.model_client.status()
        if not status.available or not candidates:
            return candidates, False
        prompt = (
            'You are reranking AI voice platform resources for a developer. '
            'Return strict JSON in the form {"items":[{"id":123,"score":0-100,"reason":"short reason"}]}. '
            'Prefer resources that directly answer the query, are current, and fit the stack described.\n\n'
            f'Query: {query}\n\nCandidates:\n{candidates}'
        )
        payload = self.model_client.generate_json(prompt)
        if not payload:
            return candidates, False
        items = payload.get('items') if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return candidates, False
        rerank_lookup: dict[int, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                resource_id = int(item.get('id'))
                score = float(item.get('score', 0)) / 100.0
            except (TypeError, ValueError):
                continue
            rerank_lookup[resource_id] = {
                'score': max(0.0, min(score, 1.0)),
                'reason': str(item.get('reason', '')).strip(),
            }
        reranked: list[dict[str, Any]] = []
        for candidate in candidates:
            adjustment = rerank_lookup.get(candidate['id'])
            if adjustment:
                candidate = {
                    **candidate,
                    'rerank_score': adjustment['score'],
                    'rerank_reason': adjustment['reason'],
                }
                candidate['final_score'] = round((candidate['base_score'] * 0.35) + (adjustment['score'] * 0.65), 4)
            reranked.append(candidate)
        reranked.sort(key=lambda item: item['final_score'], reverse=True)
        return reranked, True

    def generate_answer(self, query: str, results: list[dict[str, Any]]) -> str:
        if not results:
            return 'No matching resources were found yet. Try broadening the query or refresh the catalog.'
        status = self.model_client.status()
        if status.available:
            prompt = (
                'You are a helpful assistant for a voice AI developer resource hub. '
                'Answer in 4-6 short bullet points. Cite supporting resources using [id] after each claim. '
                'Stay concrete and do not invent features.\n\n'
                f'Query: {query}\n\nTop resources:\n{results[:6]}'
            )
            response = self.model_client.generate_text(prompt)
            if response:
                return response
        lines = ['Top matches:']
        for result in results[:4]:
            lines.append(
                f"- [{result['id']}] {result['name']} ({result['provider']}, {result['category']}): {result['summary']}"
            )
        return '\n'.join(lines)

    def search(
        self,
        connection,
        *,
        query: str,
        category: str | None = None,
        include_updates: bool = True,
        limit: int = 8,
    ) -> dict[str, Any]:
        query = query.strip()
        if not query:
            return {'query': query, 'answer': '', 'results': [], 'rerank_applied': False}
        lexical = self.lexical_candidates(connection, query, category=category, include_updates=include_updates)
        semantic = self.semantic_candidates(connection, query, category=category, include_updates=include_updates)
        candidate_ids = sorted(set(lexical) | set(semantic))
        candidates: list[dict[str, Any]] = []
        for resource_id in candidate_ids:
            resource = get_resource(connection, resource_id)
            if not resource:
                continue
            candidate = dict(resource)
            candidate['lexical_score'] = round(lexical.get(resource_id, 0.0), 4)
            candidate['semantic_score'] = round(semantic.get(resource_id, 0.0), 4)
            candidate['base_score'] = round(
                candidate['semantic_score'] * 0.68
                + candidate['lexical_score'] * 0.22
                + self.heuristics_bonus(candidate, query),
                4,
            )
            candidate['final_score'] = candidate['base_score']
            candidates.append(candidate)
        candidates.sort(key=lambda item: item['final_score'], reverse=True)
        reranked, rerank_applied = self.rerank(query, candidates[:12])
        trimmed = reranked[:limit]
        return {
            'query': query,
            'answer': self.generate_answer(query, trimmed),
            'results': trimmed,
            'rerank_applied': rerank_applied,
        }
