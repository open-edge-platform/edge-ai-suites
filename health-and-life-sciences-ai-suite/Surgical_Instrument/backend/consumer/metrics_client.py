"""HTTP client for the `surgical-metrics-collector` sidecar.

The collector is a prebuilt image shared with the NICU-Warmer /
multi-modal patient monitoring programs. It scrapes host CPU (sar),
iGPU (qmassa), NPU (sysfs CSV), memory (`free`), and Intel PCM power
counters, then exposes the aggregated snapshot at ``GET /metrics``.

This client is deliberately thin: it fetches, JSON-decodes, and caps
each time-series to the most recent ``max_points`` samples so chart.js
in the UI does not choke on a long-running collector. It always returns
the canonical five-key shape — an empty payload with ``available: False``
if the collector is unreachable — so the frontend never has to branch.

Response schema (matches multi_modal_patient_monitoring/services/
metrics-collector/app.py::build_metrics_payload):

    {
        "cpu_utilization": [[iso_ts, usage_pct], ...],
        "gpu_utilization": [[iso_ts, usage_pct, ...], ...],
        "npu_utilization": [[iso_ts, usage_pct], ...],
        "memory":          [[iso_ts, total_gb, used_gb, free_gb, pct], ...],
        "power":           [[iso_ts, ...], ...],
    }
"""
from __future__ import annotations

import logging
from typing import Any

import requests

log = logging.getLogger(__name__)

_SERIES_KEYS = (
    "cpu_utilization",
    "gpu_utilization",
    "npu_utilization",
    "memory",
    "power",
)


def _empty_payload() -> dict[str, Any]:
    return {
        "cpu_utilization": [],
        "gpu_utilization": [],
        "npu_utilization": [],
        "memory": [],
        "power": [],
        "available": False,
    }


class MetricsClient:
    """Thin proxy to the surgical-metrics-collector container.

    Args:
        base_url:   Full URL of the collector, e.g. ``http://surgical-metrics-collector:9000``.
        timeout_s:  Read timeout (seconds). The collector can hold up to a
                    few thousand samples so keep this generous.
        max_points: Per-series sample cap applied before returning to the UI.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 30.0,
        max_points: int = 120,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._max_points = int(max_points)
        # Corporate HTTP_PROXY env would otherwise route these internal
        # container-network calls through an unreachable DMZ proxy → 504.
        # A dedicated Session with trust_env=False sidesteps that (same
        # pattern used by PipelineClient).
        self._session = requests.Session()
        self._session.trust_env = False

    def fetch_metrics(self) -> dict[str, Any]:
        """Return the collector's /metrics payload, trimmed to ``max_points``.

        On any failure (timeout, connection refused, non-JSON body) returns
        the canonical empty payload with ``available: False`` so the UI can
        render the panel without null-checking every series.
        """
        try:
            r = self._session.get(f"{self._base}/metrics", timeout=self._timeout)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("metrics-collector unreachable at %s: %s", self._base, exc)
            return _empty_payload()

        if not isinstance(data, dict):
            log.warning("metrics-collector returned non-dict payload: %r", type(data).__name__)
            return _empty_payload()

        # Ensure all canonical keys exist so the UI schema stays stable.
        for key in _SERIES_KEYS:
            series = data.get(key)
            if not isinstance(series, list):
                data[key] = []
                continue
            if self._max_points > 0 and len(series) > self._max_points:
                data[key] = series[-self._max_points:]
        return data

    def fetch_platform_info(self) -> dict[str, Any]:
        """Return the collector's /platform-info payload or {available: False}."""
        try:
            r = self._session.get(f"{self._base}/platform-info", timeout=5.0)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            log.debug("metrics-collector platform-info unreachable: %s", exc)
            return {"available": False}
