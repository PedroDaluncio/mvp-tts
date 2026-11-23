import asyncio
import json
import unittest
from unittest.mock import patch

import httpx
from edge_tts.exceptions import NoAudioReceived

from backend.api import app


class SpeechProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def test_edge_works_independently_of_the_kokoro_pool(self):
        with patch("backend.api.edge_pt_br.synthesize", return_value=b"wav bytes") as synthesize:
            response = await self.client.post("/speech", json={
                "provider": "edge", "text": " Olá ", "voice": "pt-BR-AntonioNeural",
            })
        synthesize.assert_awaited_once_with("Olá", "pt-BR-AntonioNeural")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "audio/wav")
        self.assertEqual(response.content, b"wav bytes")

    async def test_rejects_mismatched_provider_and_voice(self):
        for provider, voice in [
            ("edge", "pf_dora"), ("kokoro", "pt-BR-AntonioNeural"), ("other", "pf_dora"),
        ]:
            with self.subTest(provider=provider, voice=voice):
                response = await self.client.post("/speech", json={
                    "provider": provider, "text": "Olá", "voice": voice,
                })
                self.assertEqual(response.status_code, 422)

    async def test_edge_service_error(self):
        with patch("backend.api.edge_pt_br.synthesize", side_effect=NoAudioReceived()):
            response = await self.client.post("/speech", json={
                "provider": "edge", "text": "Olá", "voice": "pt-BR-FranciscaNeural",
            })
        self.assertEqual(response.status_code, 502)

    async def test_disconnect_cancels_edge_synthesis(self):
        started = asyncio.Event()
        stopped = asyncio.Event()
        body = json.dumps({"provider": "edge", "text": "Olá", "voice": "pt-BR-AntonioNeural"}).encode()

        async def synthesize(text, voice):
            started.set()
            try:
                await asyncio.Future()
            finally:
                stopped.set()

        async def receive():
            nonlocal body
            if body:
                message = {"type": "http.request", "body": body}
                body = b""
                return message
            await started.wait()
            return {"type": "http.disconnect"}

        messages = []

        async def send(message):
            messages.append(message)

        with patch("backend.api.edge_pt_br.synthesize", synthesize):
            await app({
                "type": "http", "method": "POST", "path": "/speech", "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
            }, receive, send)
        self.assertTrue(stopped.is_set())
        self.assertEqual(messages[0]["status"], 499)
