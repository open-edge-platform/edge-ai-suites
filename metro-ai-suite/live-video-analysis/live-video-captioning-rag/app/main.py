# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from backend.config import APP_PORT, DASHBOARD_PORT, RAG_CHATBOT_MODE, UI_DIR
from backend.routes import (
    chat_router,
    model_router,
    embedding_router,
    health_router,
)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import os
from urllib.parse import urlparse


app = FastAPI(title="Live Video Captioning RAG")


def _is_navigation_request(request: Request) -> bool:
    mode = request.headers.get("sec-fetch-mode", "").strip().lower()
    accept = request.headers.get("accept", "").strip().lower()
    return mode == "navigate" or "text/html" in accept


def _is_embedded_iframe_request(request: Request) -> bool:
    dest = request.headers.get("sec-fetch-dest", "").strip().lower()
    return dest == "iframe"


def _is_from_dashboard_referrer(request: Request) -> bool:
    referer = request.headers.get("referer", "").strip()
    if not referer:
        return False
    try:
        parsed = urlparse(referer)
    except ValueError:
        return False

    req_host = (request.url.hostname or "").strip().lower()
    ref_host = (parsed.hostname or "").strip().lower()
    if not req_host or req_host != ref_host:
        return False

    if parsed.port is not None:
        return parsed.port == DASHBOARD_PORT

    if parsed.scheme == "https":
        return DASHBOARD_PORT == 443
    if parsed.scheme == "http":
        return DASHBOARD_PORT == 80
    return False


@app.middleware("http")
async def enforce_embedded_ui_access(request: Request, call_next):
    if RAG_CHATBOT_MODE != "embedded":
        return await call_next(request)

    path = request.url.path or "/"
    if path.startswith("/api/"):
        return await call_next(request)

    if _is_navigation_request(request):
        if _is_embedded_iframe_request(request) or _is_from_dashboard_referrer(request):
            return await call_next(request)
        return PlainTextResponse(
            "RAG UI is available only inside the embedded dashboard chatbot panel.",
            status_code=403,
        )

    return await call_next(request)

# Include all API routers
app.include_router(chat_router)
app.include_router(model_router)
app.include_router(embedding_router)
app.include_router(health_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(
        ","
    ),  # Adjust this to your needs
    allow_credentials=True,
    allow_methods=os.getenv("CORS_ALLOW_METHODS", "*").split(","),
    allow_headers=os.getenv("CORS_ALLOW_HEADERS", "*").split(","),
)

@app.get("/")
async def root() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=APP_PORT, reload=True)