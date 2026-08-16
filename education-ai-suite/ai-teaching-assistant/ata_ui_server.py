"""kiosk-ui-server — serves the React single-page app and proxies backends.

This lightweight FastAPI app replaces the previous Gradio UI. It:

1. Serves the built React app (``kiosk-ui-react/dist``) as static files.
2. Reverse-proxies API calls to the backend services so the browser talks to a
   single origin (no CORS juggling):

   - ``/api/kiosk/*``    -> kiosk-core       (default http://127.0.0.1:8012)
   - ``/api/rag/*``      -> rag-service      (default http://127.0.0.1:8020)
   - ``/api/tts/*``      -> text-to-speech   (default http://127.0.0.1:8011)
   - ``/api/analyzer/*`` -> audio-analyzer   (default http://127.0.0.1:8010)

Run: python ata_ui_server.py   (listens on 0.0.0.0:7860)
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "assistant-react-ui" / "dist"

UPSTREAMS = {
    "kiosk": os.getenv("KIOSK_UI_KIOSK_CORE_URL", "http://127.0.0.1:8012"),
    "rag": os.getenv("KIOSK_UI_RAG_URL", "http://127.0.0.1:8020"),
    "tts": os.getenv("KIOSK_UI_TTS_URL", "http://127.0.0.1:8011"),
    "analyzer": os.getenv("KIOSK_UI_ANALYZER_URL", "http://127.0.0.1:8010"),
}

# Long timeout: RAG generation + TTS synthesis can take a while.
_PROXY_TIMEOUT = float(os.getenv("KIOSK_UI_PROXY_TIMEOUT_SECONDS", "600"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One pooled client shared by every proxied request. Creating a client per
    # request rebuilds the connection pool each call and collapses throughput
    # under the browser's concurrent polling; a shared pool keeps it fast.
    app.state.client = httpx.AsyncClient(
        timeout=_PROXY_TIMEOUT,
        trust_env=False,
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
    )
    try:
        yield
    finally:
        await app.state.client.aclose()


app = FastAPI(title="kiosk-ui-server", lifespan=lifespan)

# Hop-by-hop headers must not be forwarded.
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


def _filter_headers(headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(service: str, path: str, request: Request) -> Response:
    upstream = UPSTREAMS.get(service)
    if upstream is None:
        return Response(content=f"Unknown proxy target: {service}", status_code=404)

    target_url = f"{upstream}/{path}"
    body = await request.body()

    client: httpx.AsyncClient = request.app.state.client
    try:
        upstream_response = await client.request(
            request.method,
            target_url,
            params=request.query_params,
            headers=_filter_headers(request.headers),
            content=body,
        )
    except httpx.RequestError as exc:
        return Response(content=f"Upstream error: {exc}", status_code=502)

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=_filter_headers(upstream_response.headers),
        media_type=upstream_response.headers.get("content-type"),
    )


if DIST_DIR.is_dir():
    # Serve hashed assets and other static files.
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        # SPA fallback: serve the requested file if it exists, else index.html.
        candidate = DIST_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
else:  # pragma: no cover - only hit before the first build
    @app.get("/")
    def missing_build() -> Response:
        return Response(
            content=(
                "React UI is not built yet. Run 'npm install' and 'npm run build' "
                "inside kiosk-ui-react/."
            ),
            status_code=503,
        )


if __name__ == "__main__":
    host = os.getenv("KIOSK_UI_HOST", "0.0.0.0")
    port = int(os.getenv("KIOSK_UI_PORT", "7860"))
    uvicorn.run("ata_ui_server:app", host=host, port=port, reload=False)
