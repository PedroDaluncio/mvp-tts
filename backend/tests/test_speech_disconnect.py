import json
from queue import LifoQueue
import unittest
from unittest.mock import Mock, patch

import anyio
import torch

from backend.api import app


class SpeechDisconnectTests(unittest.TestCase):
    def test_disconnect_stops_remaining_chunks_and_releases_model(self):
        pipeline = Mock()
        pipeline.g2p.side_effect = lambda text: (text, None)
        pipeline.generate_from_tokens.return_value = [Mock(audio=torch.zeros(24))]
        body = json.dumps({"text": "olá " * 200, "voice": "pf_dora"}).encode()

        async def post(disconnect_after):
            body_sent = False
            responses = []

            async def receive():
                nonlocal body_sent
                if not body_sent:
                    body_sent = True
                    return {"type": "http.request", "body": body}
                if pipeline.generate_from_tokens.call_count == disconnect_after:
                    return {"type": "http.disconnect"}
                await anyio.sleep_forever()

            async def send(message):
                responses.append(message)

            await app({
                "type": "http", "method": "POST", "path": "/speech",
                "query_string": b"", "headers": [(b"content-type", b"application/json")],
            }, receive, send)
            return responses[0]["status"]

        slots = LifoQueue()
        slots.put_nowait(pipeline)
        with patch.object(app.state, "pipelines", slots, create=True):
            self.assertEqual(anyio.run(post, 0), 499)
            pipeline.generate_from_tokens.assert_not_called()
            self.assertEqual(anyio.run(post, 1), 499)
            self.assertEqual(pipeline.generate_from_tokens.call_count, 1)
            self.assertEqual(anyio.run(post, None), 200)
