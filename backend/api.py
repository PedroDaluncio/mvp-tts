import asyncio
from contextlib import asynccontextmanager
from queue import Empty, LifoQueue
from typing import Annotated, Literal

from aiohttp import ClientError
from anyio import from_thread, to_thread
from edge_tts.exceptions import EdgeTTSException
from fastapi import FastAPI, HTTPException, Request, Response
from kokoro import KPipeline
from pydantic import BaseModel, StringConstraints

from . import edge_pt_br
from .kokoro_pt_br import Voice as KokoroVoice, config, create_pipeline, synthesize


@asynccontextmanager
async def lifespan(app: FastAPI):
    concurrency = config("KOKORO_MAX_CONCURRENT_REQUESTS", cast=int, default=2)
    if concurrency < 1:
        raise ValueError("KOKORO_MAX_CONCURRENT_REQUESTS must be at least 1")

    pipelines: LifoQueue[KPipeline] = LifoQueue(maxsize=concurrency)
    for _ in range(concurrency):
        pipelines.put_nowait(await to_thread.run_sync(create_pipeline))
    app.state.pipelines = pipelines
    try:
        yield
    finally:
        del app.state.pipelines


app = FastAPI(title="Brazilian Portuguese text-to-speech", lifespan=lifespan)


class SpeechRequest(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class KokoroRequest(SpeechRequest):
    provider: Literal["kokoro"] = "kokoro"
    voice: KokoroVoice


class EdgeRequest(SpeechRequest):
    provider: Literal["edge"]
    voice: edge_pt_br.Voice


class WavResponse(Response):
    media_type = "audio/wav"


def generate_kokoro(payload: KokoroRequest, request: Request) -> WavResponse:
    def check_connection() -> None:
        if from_thread.run(request.is_disconnected):
            raise HTTPException(status_code=499, detail="Client disconnected")

    pipelines: LifoQueue[KPipeline] = request.app.state.pipelines
    while True:
        check_connection()
        try:
            pipeline = pipelines.get(timeout=0.25)
            break
        except Empty:
            continue

    try:
        check_connection()
        audio = synthesize(payload.text, payload.voice, checkpoint=check_connection, pipeline=pipeline)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        pipelines.put_nowait(pipeline)
    return WavResponse(audio)


async def wait_for_disconnect(request: Request) -> None:
    while (await request.receive())["type"] != "http.disconnect":
        pass


@app.post("/speech", response_class=WavResponse)
async def generate_speech(payload: KokoroRequest | EdgeRequest, request: Request) -> WavResponse:
    if isinstance(payload, KokoroRequest):
        return await to_thread.run_sync(generate_kokoro, payload, request)

    synthesis = asyncio.create_task(edge_pt_br.synthesize(payload.text, payload.voice))
    disconnect = asyncio.create_task(wait_for_disconnect(request))
    try:
        done, _ = await asyncio.wait((synthesis, disconnect), return_when=asyncio.FIRST_COMPLETED)
        if disconnect in done:
            await disconnect
            raise HTTPException(status_code=499, detail="Client disconnected")
        return WavResponse(await synthesis)
    except (ClientError, EdgeTTSException, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail="Edge TTS could not generate speech.") from exc
    finally:
        disconnect.cancel()
        synthesis.cancel()
        await asyncio.gather(disconnect, synthesis, return_exceptions=True)
