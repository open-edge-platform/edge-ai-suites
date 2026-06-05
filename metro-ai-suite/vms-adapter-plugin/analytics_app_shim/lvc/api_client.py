# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""LVC HTTP API client.

Wraps all HTTP calls made to the Live Video Captioning FastAPI backend.
Keeps network I/O isolated from schema and shim logic so each module
has a single responsibility.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class LvcApiClient:
    """Thin async HTTP client for the LVC backend REST API."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ── internal ──────────────────────────────────────────────────────────────

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    @staticmethod
    def _extract_error(resp: httpx.Response) -> str:
        """Pull a human-readable message out of an LVC error response."""
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            return resp.text or f"HTTP {resp.status_code}"
        detail = data.get("detail", data) if isinstance(data, dict) else data
        if isinstance(detail, dict):
            body = detail.get("body") or detail.get("message") or ""
            if isinstance(body, str):
                body = body.strip().strip('"')
            return body or detail.get("message") or str(detail)
        return str(detail)

    # ── OpenAPI ───────────────────────────────────────────────────────────────

    async def get_openapi(self) -> dict[str, Any]:
        """Fetch the LVC OpenAPI spec (GET /openapi.json)."""
        client = self._ensure_client()
        resp = await client.get("/openapi.json")
        resp.raise_for_status()
        return resp.json()

    # ── Runs ──────────────────────────────────────────────────────────────────

    async def start_run(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """POST /api/generate_captions_alerts — start a new captioning pipeline run.

        Returns the run dict on success, or None on failure (error logged).
        """
        client = self._ensure_client()
        try:
            resp = await client.post("/api/generate_captions_alerts", json=payload)
            if not resp.is_success:
                logger.error(
                    "lvc_start_run_failed",
                    status_code=resp.status_code,
                    detail=self._extract_error(resp),
                    rtsp_url=payload.get("rtspUrl"),
                )
                return None
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("lvc_start_run_error", error=str(exc))
            return None

    async def stop_run(self, run_id: str) -> bool:
        """DELETE /api/generate_captions_alerts/{run_id} — stop a pipeline run."""
        client = self._ensure_client()
        try:
            resp = await client.delete(f"/api/generate_captions_alerts/{run_id}")
            resp.raise_for_status()
            logger.info("lvc_run_stopped", run_id=run_id)
            return True
        except httpx.HTTPError as exc:
            logger.error("lvc_stop_run_failed", run_id=run_id, error=str(exc))
            return False

    async def list_runs(self) -> list[dict[str, Any]]:
        """GET /api/generate_captions_alerts — list all active runs.

        Raises httpx.HTTPError on connection/timeout errors so callers can
        distinguish "LVC unreachable" from "LVC has zero active runs".
        """
        client = self._ensure_client()
        try:
            resp = await client.get("/api/generate_captions_alerts")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("lvc_list_runs_failed", error=str(exc))
            raise

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """GET /api/generate_captions_alerts/{run_id} — get a specific run."""
        client = self._ensure_client()
        try:
            resp = await client.get(f"/api/generate_captions_alerts/{run_id}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("lvc_get_run_failed", run_id=run_id, error=str(exc))
            return None

    # ── Options ───────────────────────────────────────────────────────────────

    async def get_models(self) -> list[str]:
        """GET /api/vlm-models — list available VLM models."""
        client = self._ensure_client()
        try:
            resp = await client.get("/api/vlm-models")
            resp.raise_for_status()
            raw = resp.json()
            if isinstance(raw, dict):
                raw = raw.get("models", [])
            return [m if isinstance(m, str) else m.get("model_name") or m.get("name") or "" for m in raw]
        except httpx.HTTPError as exc:
            logger.error("lvc_get_models_failed", error=str(exc))
            return []

    async def get_pipelines(self) -> list[str]:
        """GET /api/pipelines — list available pipeline names.

        Retries once on transient 502 (pipeline server warm-up).
        """
        client = self._ensure_client()
        for attempt in range(2):
            try:
                resp = await client.get("/api/pipelines")
                resp.raise_for_status()
                data = resp.json()
                items = data.get("pipelines", data) if isinstance(data, dict) else data
                out: list[str] = []
                for p in items:
                    if isinstance(p, str):
                        out.append(p)
                    elif isinstance(p, dict):
                        name = p.get("pipeline_name") or p.get("name")
                        if name:
                            out.append(name)
                return out
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 502 and attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                logger.error("lvc_get_pipelines_failed", error=str(exc))
                return []
            except httpx.HTTPError as exc:
                logger.error("lvc_get_pipelines_failed", error=str(exc))
                return []
        return []

    # ── Streaming ─────────────────────────────────────────────────────────────

    @property
    def results_stream_url(self) -> str:
        """Full URL of the LVC multiplexed SSE metadata stream."""
        return f"{self._base_url}/api/generate_captions_alerts/metadata-stream"

    # ── Health ────────────────────────────────────────────────────────────────

    async def is_reachable(self) -> bool:
        """Quick health check — GET /api/generate_captions_alerts returning < 500 means up."""
        client = self._ensure_client()
        try:
            resp = await client.get("/api/generate_captions_alerts", timeout=3.0)
            return resp.status_code < 500
        except httpx.HTTPError:
            return False
