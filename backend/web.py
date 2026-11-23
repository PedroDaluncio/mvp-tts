"""Serve the API and compiled frontend together in the production container."""

from pathlib import Path

from fastapi.staticfiles import StaticFiles

from .api import app

frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
