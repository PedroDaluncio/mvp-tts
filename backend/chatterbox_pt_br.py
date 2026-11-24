"""Manage the isolated Python 3.10 Chatterbox inference process."""

import asyncio
import json
import os
import signal
from pathlib import Path


class ChatterboxWorker:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.process = None

    async def close(self):
        process = self.process
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.communicate()
            self.process = None

    async def synthesize(self, text: str, reference: Path | None = None) -> bytes:
        async with self.lock:
            try:
                if self.process is None:
                    script = Path(__file__).with_name("chatterbox_worker.py")
                    self.process = await asyncio.create_subprocess_exec(
                        "uv", "run", "--script", str(script),
                        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                        start_new_session=True,
                    )
                process = self.process
                process.stdin.write(json.dumps({"text": text, "reference": str(reference) if reference else None}).encode() + b"\n")
                await process.stdin.drain()
                length = int.from_bytes(await process.stdout.readexactly(8), "big")
                return await process.stdout.readexactly(length)
            except (Exception, asyncio.CancelledError):
                await self.close()
                raise
