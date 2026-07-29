# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""DLStreamer Pipeline Server REST API client.

Wraps all HTTP calls to the Pipeline Server REST API.

URL conventions (via nginx /api/ → dlstreamer:8080):
  GET  /pipelines                  → list templates; each item has "name" (root) + "version" (pipeline id)
  POST /pipelines/{root}/{version} → start instance; response is a hex UUID string (instance_id)
  GET  /pipelines/status           → list all running instances (id, state, avg_fps, ...)
  GET  /pipelines/{instance_id}    → get one instance
  DELETE /pipelines/{instance_id}  → stop one instance (id only, no root/version)
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class ObjectDetectionApiClient:
    """Async HTTP client for the DLStreamer Pipeline Server REST API."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        tls_verify: bool = False,
        tls_ca_bundle: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._tls_verify = tls_verify
        self._tls_ca_bundle = tls_ca_bundle
        self._client: httpx.AsyncClient | None = None

    def _httpx_verify(self) -> bool | str:
        if self._tls_verify and self._tls_ca_bundle:
            return self._tls_ca_bundle
        return self._tls_verify

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                verify=self._httpx_verify(),
            )
        return self._client

    # ── Pipelines (templates) ─────────────────────────────────────────────────

    async def list_pipelines(self) -> list[dict[str, Any]]:
        """GET /pipelines — list available pipeline templates.

        Each entry has:
          - "name":    pipeline root directory (e.g. "user_defined_pipelines")
          - "version": pipeline identifier shown to users (e.g. "dls_vision_pipeline")
        """
        client = self._ensure_client()
        try:
            resp = await client.get("/pipelines")
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except httpx.HTTPError as exc:
            logger.error("od_list_pipelines_failed", error=str(exc))
            return []

    # ── Pipeline instances (runs) ─────────────────────────────────────────────

    async def start_run(
        self, pipeline_root: str, pipeline_version: str, payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        """POST /pipelines/{pipeline_root}/{pipeline_version} — start a new pipeline instance.

        The Pipeline Server returns the instance_id as a hex UUID string
        (e.g. "4b36b3ce52ad11f0ad60863f511204e2").

        Returns {"instance_id": "<hex-uuid>"} on success, None on failure.
        """
        client = self._ensure_client()
        try:
            resp = await client.post(f"/pipelines/{pipeline_root}/{pipeline_version}", json=payload)
            if not resp.is_success:
                logger.error(
                    "od_start_run_failed",
                    pipeline_root=pipeline_root,
                    pipeline_version=pipeline_version,
                    status_code=resp.status_code,
                    detail=resp.text[:200],
                )
                return None
            result = resp.json()
            # Response is a plain hex UUID string
            if isinstance(result, str):
                return {"instance_id": result}
            return result
        except httpx.HTTPError as exc:
            logger.error(
                "od_start_run_error",
                pipeline_root=pipeline_root,
                pipeline_version=pipeline_version,
                error=str(exc),
            )
            return None

    async def list_runs(self) -> list[dict[str, Any]]:
        """GET /pipelines/status — list all running pipeline instances.

        Each entry has: id, state, avg_fps, elapsed_time, start_time, message.
        """
        client = self._ensure_client()
        try:
            resp = await client.get("/pipelines/status")
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except httpx.HTTPError as exc:
            logger.error("od_list_runs_failed", error=str(exc))
            return []

    async def get_run(self, instance_id: str) -> dict[str, Any] | None:
        """GET /pipelines/{instance_id} — get a specific running instance."""
        client = self._ensure_client()
        try:
            resp = await client.get(f"/pipelines/{instance_id}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("od_get_run_failed", instance_id=instance_id, error=str(exc))
            return None

    async def stop_run(self, instance_id: str) -> bool:
        """DELETE /pipelines/{instance_id} — stop a pipeline instance by its hex UUID."""
        client = self._ensure_client()
        try:
            resp = await client.delete(f"/pipelines/{instance_id}")
            resp.raise_for_status()
            logger.info("od_run_stopped", instance_id=instance_id)
            return True
        except httpx.HTTPError as exc:
            logger.error("od_stop_run_failed", instance_id=instance_id, error=str(exc))
            return False

    # ── Health ────────────────────────────────────────────────────────────────

    async def is_reachable(self) -> bool:
        """Health check — GET /pipelines returning < 500 means the server is up."""
        client = self._ensure_client()
        try:
            resp = await client.get("/pipelines", timeout=3.0)
            return resp.status_code < 500
        except httpx.HTTPError:
            return False
