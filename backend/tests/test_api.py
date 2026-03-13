from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / 'backend'))


class VoiceHubApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ['APP_DATABASE_PATH'] = str(Path(cls.temp_dir.name) / 'test.db')
        os.environ['VOICE_HUB_DISABLE_OLLAMA'] = '1'
        os.environ['VOICE_HUB_STARTUP_REFRESH_MODE'] = 'sample'
        from app.main import app

        cls.client_manager = TestClient(app)
        cls.client = cls.client_manager.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_manager.__exit__(None, None, None)
        os.environ.pop('APP_DATABASE_PATH', None)
        os.environ.pop('VOICE_HUB_DISABLE_OLLAMA', None)
        os.environ.pop('VOICE_HUB_STARTUP_REFRESH_MODE', None)
        cls.temp_dir.cleanup()

    def test_health_and_dashboard(self) -> None:
        health = self.client.get('/health')
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()['status'], 'ok')

        dashboard = self.client.get('/api/dashboard')
        self.assertEqual(dashboard.status_code, 200)
        payload = dashboard.json()
        self.assertGreaterEqual(payload['stats']['curated_count'], 10)
        self.assertGreaterEqual(payload['stats']['update_count'], 1)
        self.assertTrue(payload['featured']['local_ready'])
        self.assertTrue(payload['refresh_runs'])

    def test_resource_filters_and_search(self) -> None:
        resources = self.client.get('/api/resources', params={'category': 'embedding'})
        self.assertEqual(resources.status_code, 200)
        payload = resources.json()
        self.assertGreaterEqual(payload['count'], 1)
        self.assertTrue(any(item['category'] == 'embedding' for item in payload['results']))

        search = self.client.get('/api/search', params={'q': 'local embedding model for voice rag'})
        self.assertEqual(search.status_code, 200)
        search_payload = search.json()
        self.assertTrue(search_payload['results'])
        self.assertIn('Top', search_payload['answer'])
        first = search_payload['results'][0]
        self.assertIn('category', first)
        self.assertIn('final_score', first)

    def test_manual_refresh(self) -> None:
        refresh = self.client.post('/api/refresh', json={'mode': 'sample'})
        self.assertEqual(refresh.status_code, 200)
        payload = refresh.json()
        self.assertEqual(payload['status'], 'completed')
        self.assertGreaterEqual(payload['items_upserted'], 1)
        self.assertIn('dashboard', payload)


if __name__ == '__main__':
    unittest.main()
