import unittest
from threading import Barrier
from unittest.mock import Mock, patch

import anyio
import httpx
import torch

from backend.api import app


class SpeechConcurrencyTests(unittest.TestCase):
    def test_two_requests_reach_separate_models_at_the_same_time(self):
        both_running = Barrier(2, timeout=5)

        def generate(chunk, voice):
            both_running.wait()
            return [Mock(audio=torch.zeros(24))]

        models = [Mock(), Mock()]
        for model in models:
            model.g2p.return_value = ("ola", None)
            model.generate_from_tokens.side_effect = generate

        async def post_both():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                async def post(voice):
                    response = await client.post("/speech", json={"text": "Olá", "voice": voice})
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.content.startswith(b"RIFF"))

                async with anyio.create_task_group() as group:
                    group.start_soon(post, "pf_dora")
                    group.start_soon(post, "pm_alex")

        async def exercise_lifespan():
            async with app.router.lifespan_context(app):
                self.assertEqual(factory.call_count, 2)
                await post_both()
                for model in models:
                    model.generate_from_tokens.assert_called_once()
                await post_both()
                self.assertEqual(app.state.pipelines.qsize(), 2)
                self.assertEqual(factory.call_count, 2)

        with patch("backend.api.config", return_value=2), patch("backend.api.create_pipeline", side_effect=models) as factory:
            anyio.run(exercise_lifespan)
