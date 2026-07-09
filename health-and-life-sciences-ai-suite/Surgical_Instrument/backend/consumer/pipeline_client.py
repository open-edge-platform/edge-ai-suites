"""HTTP client for the `surgical-pipeline` control plane."""
from __future__ import annotations

import logging
from typing import Any

import requests

log = logging.getLogger(__name__)


class PipelineClient:
    def __init__(self, host: str, port: int = 8000, timeout: float = 10.0) -> None:
        self._base = f"http://{host}:{port}"
        self._timeout = timeout
        # Corporate HTTP_PROXY env vars would otherwise route these
        # internal-network calls through an unreachable DMZ proxy → 504.
        # A dedicated Session with trust_env=False sidesteps that.
        self._session = requests.Session()
        self._session.trust_env = False

    def health(self) -> dict[str, Any]:
        r = self._session.get(f"{self._base}/health", timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def start(
        self,
        device: str,
        *,
        source_kind: str | None = None,
        source_arg: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"device": device.upper()}
        if source_kind is not None:
            payload["source"] = {"kind": source_kind, "arg": source_arg}
        r = self._session.post(
            f"{self._base}/start",
            json=payload,
            timeout=self._timeout,
        )
        if r.status_code == 409:
            log.warning("pipeline already running; treating as no-op")
            return r.json()
        r.raise_for_status()
        return r.json()

    def stop(self) -> dict[str, Any]:
        r = self._session.post(f"{self._base}/stop", timeout=self._timeout)
        r.raise_for_status()
        return r.json()
