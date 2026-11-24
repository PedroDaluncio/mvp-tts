from contextlib import asynccontextmanager
from queue import Empty, LifoQueue
from typing import Annotated, Literal

from anyio import from_thread, to_thread
from fastapi import FastAPI, HTTPException, Request, Response
from kokoro import KPipeline
from pydantic import BaseModel, StringConstraints

from .kokoro_pt_br import Voice, config, create_pipeline, synthesize


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
    voice: Voice
    provider: Literal["kokoro"] = "kokoro"


class WavResponse(Response):
    media_type = "audio/wav"


@app.post("/speech", response_class=WavResponse)
def generate_speech(payload: SpeechRequest, request: Request) -> WavResponse:
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
