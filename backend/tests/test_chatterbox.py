import asyncio
import json
import io
import wave
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from backend.api import app


class ChatterboxTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_and_voice_validation(self):
        worker = Mock(synthesize=AsyncMock(return_value=b"wav"))
        request = {"provider": "chatterbox", "text": " Olá "}
        with patch.object(app.state, "chatterbox", worker, create=True):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                for invalid in ({"voice": "pf_dora"}, {"text": "  "}):
                    response = await client.post("/speech", json=request | invalid)
                    self.assertEqual(response.status_code, 422)
                response = await client.post("/speech", json=request)
        worker.synthesize.assert_awaited_once_with("Olá")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "audio/wav")
        self.assertEqual(response.content, b"wav")

    async def test_reference_is_validated_normalized_and_removed(self):
        recording = io.BytesIO()
        with wave.open(recording, "wb") as wav:
            wav.setparams((1, 2, 16000, 0, "NONE", ""))
            wav.writeframes(b"\x10\x00" * 16000)
        prompts = []

        async def synthesize(text, prompt):
            self.assertEqual(text, "Olá")
            with wave.open(str(prompt)) as wav:
                self.assertEqual(wav.getparams()[:4], (1, 2, 24000, 24000))
            prompts.append(prompt)
            return b"speech"

        with patch.object(app.state, "chatterbox", Mock(synthesize=synthesize), create=True):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                url = "/speech/chatterbox/custom"
                for data in (b"", b"invalid"):
                    response = await client.post(url, data={"text": "Olá"}, files={"reference_audio": ("ref.wav", data)})
                    self.assertEqual(response.status_code, 422)
                response = await client.post(url, data={"text": " Olá "}, files={"reference_audio": ("ref.wav", recording.getvalue())})
        self.assertEqual(response.content, b"speech")
        self.assertFalse(prompts[0].exists())

    async def test_disconnect_cancels_active_synthesis(self):
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def synthesize(text):
            started.set()
            try:
                await asyncio.Future()
            finally:
                stopped.set()

        body = json.dumps({"provider": "chatterbox", "text": "Olá"}).encode()

        async def receive():
            nonlocal body
            if body:
                message = {"type": "http.request", "body": body}
                body = b""
                return message
            await started.wait()
            return {"type": "http.disconnect"}

        send = AsyncMock()
        with patch.object(app.state, "chatterbox", Mock(synthesize=synthesize), create=True):
            await app({
                "type": "http", "method": "POST", "path": "/speech", "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
            }, receive, send)
        self.assertTrue(stopped.is_set())
        self.assertEqual(send.await_args_list[0].args[0]["status"], 499)
