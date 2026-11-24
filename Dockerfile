FROM node:24-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/yarn.lock ./
RUN yarn install --frozen-lockfile
COPY frontend/ ./
RUN yarn build

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KOKORO_DEVICE=cpu \
    HF_HOME=/opt/huggingface \
    OMP_NUM_THREADS=1 \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg espeak-ng libsndfile1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
# Use the project's pinned torch version from the CPU wheel index.
RUN grep '^torch==' /tmp/requirements.txt > /tmp/torch.txt \
    && pip install --no-deps --index-url https://download.pytorch.org/whl/cpu -r /tmp/torch.txt \
    && grep -Ev '^(cuda-|nvidia-|triton==)' /tmp/requirements.txt > /tmp/requirements-cpu.txt \
    && pip install -r /tmp/requirements-cpu.txt

# Bundle only the files needed for Brazilian Portuguese before instances start.
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('hexgrad/Kokoro-82M', allow_patterns=['config.json', 'kokoro-v1_0.pth', 'voices/pf_dora.pt', 'voices/pm_alex.pt', 'voices/pm_santa.pt'])"
# Chatterbox needs its own Python 3.10 / CPU Torch environment.
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python UV_CACHE_DIR=/opt/uv-cache
COPY backend/chatterbox_worker.py ./backend/chatterbox_worker.py
RUN uv run --python 3.10 --script backend/chatterbox_worker.py </dev/null
ENV HF_HUB_OFFLINE=1 UV_OFFLINE=1

COPY backend/ ./backend/
COPY --from=frontend /build/frontend/dist/ ./frontend/dist/
EXPOSE 8080
CMD ["sh", "-c", "exec python -m uvicorn backend.web:app --host 0.0.0.0 --port \"$PORT\""]
