# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
AlertServiceClient — async HTTP client for the alert-agent-service microservice.

Replaces the embedded AlertActionAgent by delegating action dispatch to the
external alert-agent-service via its REST API.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from src.config import settings

logger = logging.getLogger(__name__)


class AlertServiceClient:
    """HTTP client wrapping calls to the alert-agent-service microservice."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        self._base_url = (base_url or settings.ALERT_AGENT_SERVICE_URL).rstrip("/")
        self._timeout = aiohttp.ClientTimeout(
            total=timeout or settings.ALERT_AGENT_SERVICE_TIMEOUT
        )
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def health_check(self) -> Dict[str, Any]:
        """Check alert-agent-service health (GET /health)."""
        session = await self._get_session()
        try:
            async with session.get(f"{self._base_url}/health") as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"status": "unhealthy", "http_status": resp.status}
        except Exception as exc:
            logger.warning(f"Alert service health check failed: {exc}")
            return {"status": "unreachable", "error": str(exc)}

    async def dispatch_alert(
        self,
        source_id: str,
        alert_name: str,
        answer: str = "YES",
        reason: str = "",
        consecutive_count: int = 1,
        escalated: bool = False,
        tools: Optional[List[str]] = None,
        tool_arguments: Optional[Dict[str, dict]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        image_frame: Optional[bytes] = None,
        snapshot_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dispatch an alert action via POST /actions/execute.

        Parameters
        ----------
        source_id : str
            Stream/camera/sensor identifier.
        alert_name : str
            Name of the fired alert.
        answer : str
            Detection answer (YES/NO).
        reason : str
            Human-readable explanation.
        consecutive_count : int
            Number of consecutive YES detections.
        escalated : bool
            Whether escalation threshold was reached.
        tools : list[str]
            Tools to invoke.
        tool_arguments : dict
            Per-tool argument overrides.
        metadata : dict
            Additional metadata to pass through.
        image_frame : bytes | None
            Raw image bytes (JPEG-encoded) to include as a payload.
        snapshot_path : str | None
            Pre-captured snapshot path (included in metadata).

        Returns
        -------
        dict with keys: event_id, source_id, alert_name, actions_taken, duration_ms, snapshot_path
        """
        payload: Dict[str, Any] = {
            "source_id": source_id,
            "alert_name": alert_name,
            "answer": answer,
            "reason": reason,
            "consecutive_count": consecutive_count,
            "escalated": escalated,
            "tools": tools or ["log_alert"],
            "tool_arguments": tool_arguments or {},
            "metadata": metadata or {},
            "payloads": [],
        }

        if snapshot_path:
            payload["metadata"]["snapshot_path"] = snapshot_path

        # Attach image frame as base64-encoded payload
        if image_frame is not None:
            payload["payloads"].append({
                "kind": "image",
                "mime_type": "image/jpeg",
                "encoding": "base64",
                "data_base64": base64.b64encode(image_frame).decode("ascii"),
                "metadata": {},
            })

        session = await self._get_session()
        url = f"{self._base_url}/actions/execute"

        # FastAPI endpoint expects body as {"data": <AlertActionRequest fields>}
        request_body = {"data": payload}

        try:
            async with session.post(url, json=request_body) as resp:
                if resp.status == 200:
                    return await resp.json()
                body = await resp.text()
                logger.error(
                    f"Alert service dispatch failed: HTTP {resp.status} — {body}"
                )
                return {
                    "event_id": "",
                    "source_id": source_id,
                    "alert_name": alert_name,
                    "actions_taken": [],
                    "duration_ms": 0.0,
                    "error": f"HTTP {resp.status}: {body}",
                }
        except aiohttp.ClientError as exc:
            logger.error(f"Alert service dispatch error: {exc}")
            return {
                "event_id": "",
                "source_id": source_id,
                "alert_name": alert_name,
                "actions_taken": [],
                "duration_ms": 0.0,
                "error": str(exc),
            }

    async def ingest_alert(self, alert_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post a flexible alert payload via POST /alerts.

        This is the generic ingestion endpoint that accepts any JSON body.
        """
        session = await self._get_session()
        url = f"{self._base_url}/alerts"

        try:
            async with session.post(url, json=alert_payload) as resp:
                return await resp.json()
        except Exception as exc:
            logger.error(f"Alert ingestion error: {exc}")
            return {"status": "error", "error": str(exc)}

    async def list_tools(self) -> Dict[str, Any]:
        """GET /tools — list all registered action tools."""
        session = await self._get_session()
        try:
            async with session.get(f"{self._base_url}/tools") as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"tools": [], "error": f"HTTP {resp.status}"}
        except Exception as exc:
            logger.error(f"Failed to list tools from alert service: {exc}")
            return {"tools": [], "error": str(exc)}

    async def invoke_tool(
        self, tool_name: str, parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """POST /tools/{tool_name}/invoke — manually invoke a tool."""
        session = await self._get_session()
        url = f"{self._base_url}/tools/{tool_name}/invoke"
        body = {"parameters": parameters or {}}

        try:
            async with session.post(url, json=body) as resp:
                if resp.status == 200:
                    return await resp.json()
                text = await resp.text()
                return {
                    "tool": tool_name,
                    "status": "error",
                    "result": {"error": f"HTTP {resp.status}: {text}"},
                    "duration_ms": 0.0,
                }
        except Exception as exc:
            logger.error(f"Failed to invoke tool '{tool_name}': {exc}")
            return {
                "tool": tool_name,
                "status": "error",
                "result": {"error": str(exc)},
                "duration_ms": 0.0,
            }

    async def reload_tools(self) -> Dict[str, Any]:
        """POST /tools/reload — hot-reload tools in the service."""
        session = await self._get_session()
        try:
            async with session.post(f"{self._base_url}/tools/reload") as resp:
                return await resp.json()
        except Exception as exc:
            logger.error(f"Failed to reload tools: {exc}")
            return {"status": "error", "error": str(exc)}
