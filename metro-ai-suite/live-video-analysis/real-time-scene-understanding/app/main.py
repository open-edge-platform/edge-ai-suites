# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

import boto3
import uvicorn
from backend.config import settings
from backend.config import setup_logging
from backend.routes import build_alert_router
from backend.routes import build_health_router
from backend.routes import build_registry_router
from backend.routes import build_runtime_config_router
from backend.routes import build_stream_router
from backend.services.alert_index import get_alert_index
from backend.services.frame_registry import SegmentFrameRegistry
from backend.services.stream_registry import StreamRegistry
from botocore.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

setup_logging()
logger = logging.getLogger(__name__)

_startup_time = time.monotonic()
frame_registry = SegmentFrameRegistry(max_records_per_stream=settings.FRAME_REGISTRY_MAX_RECORDS_PER_STREAM)
registry = StreamRegistry(frame_registry)
alert_index = get_alert_index()

_UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")


def _get_alert_s3_client():
    logger.info("Initialize SeaweedFS S3 client for video segment storage")

    return boto3.client(
        "s3",
        endpoint_url=settings.SEAWEEDFS_ENDPOINT_URL,
        aws_access_key_id=settings.SEAWEEDFS_ACCESS_KEY,
        aws_secret_access_key=settings.SEAWEEDFS_SECRET_KEY,
        use_ssl=settings.SEAWEEDFS_USE_SSL,
        verify=settings.SEAWEEDFS_VERIFY_SSL,
        config=Config(max_pool_connections=settings.SEAWEEDFS_MAX_POOL_CONNECTIONS),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Real Time Scene Understanding service | port=%s", settings.DASHBOARD_PORT)
    logger.info("No startup stream auto-registration — add streams via UI or POST /api/streams")
    try:
        yield
    finally:
        logger.info("Shutting down — stopping streams ...")
        registry.stop_all()


app = FastAPI(
    title="Real Time Scene Understanding",
    description="RTSP ingestion and WebRTC rendering pipeline powered by PyAV.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """SDL423: catch-all handler — logs full detail internally, never leaks
    internals (stack trace, file paths, exception class) to the client."""
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(build_health_router(registry, _startup_time))
app.include_router(build_runtime_config_router(settings))
app.include_router(build_registry_router(frame_registry))
app.include_router(build_stream_router(registry, alert_index))
app.include_router(build_alert_router(alert_index, _get_alert_s3_client, settings))


_static_dir = os.path.join(_UI_DIR, "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, tags=["UI"])
async def index():
    ui_path = os.path.join(_UI_DIR, "index.html")
    if not os.path.exists(ui_path):
        return HTMLResponse(content="<h1>UI not found</h1>", status_code=404)
    with open(ui_path, encoding="utf-8") as fh:
        return HTMLResponse(content=fh.read())


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.DASHBOARD_HOST,
        port=settings.DASHBOARD_PORT,
        log_level=settings.LOG_LEVEL.lower(),
    )
