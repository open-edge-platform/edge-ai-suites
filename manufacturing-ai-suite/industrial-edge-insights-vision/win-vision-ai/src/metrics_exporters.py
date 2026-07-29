#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""
metrics_exporters.py — MetricsExporter interface and built-in implementations.

Add a new exporter by subclassing :class:`MetricsExporter` and implementing
:meth:`~MetricsExporter.export`.  Pass the instance to
:class:`~win_vision_ai.metrics_collector.MetricsCollector`.

Built-in exporters
------------------
- :class:`LogExporter`        — writes metrics to the logger at DEBUG level.
- :class:`PrometheusExporter` — exposes a ``/metrics`` HTTP endpoint
  (skeleton; implement TODO comments before use).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class MetricsExporter(ABC):
    """
    Base class for metrics exporters.

    Subclass this to send pipeline metrics to any backend
    (Prometheus, InfluxDB, StatsD, etc.).
    """

    def setup(self) -> None:
        """
        Called once by :class:`~win_vision_ai.metrics_collector.MetricsCollector`
        before the polling loop starts.

        Override to register metrics definitions, open connections, etc.
        Default implementation is a no-op.
        """

    @abstractmethod
    def export(self, snapshots: List[Dict[str, Any]]) -> None:
        """
        Receive a list of pipeline status snapshots and push them to the backend.

        Parameters
        ----------
        snapshots:
            List of dicts as returned by
            :meth:`~win_vision_ai.pipeline_manager.PipelineManager.list_all`.
            Each dict has keys: ``id``, ``state``, ``frame_count``,
            ``avg_fps``, ``current_fps``, ``avg_latency_ms``.
        """

    def teardown(self) -> None:
        """
        Called once by :class:`~win_vision_ai.metrics_collector.MetricsCollector`
        after the polling loop stops.

        Override to flush buffers, close connections, etc.
        Default implementation is a no-op.
        """


# ---------------------------------------------------------------------------
# Prometheus exporter
# ---------------------------------------------------------------------------


class PrometheusExporter(MetricsExporter):
    """
    Exports pipeline metrics via a Prometheus HTTP endpoint.

    Requires the ``prometheus_client`` package::

        pip install prometheus_client

    The HTTP server is started in :meth:`setup` and listens on ``port``
    indefinitely.  Metrics are updated on each :meth:`export` call and
    scraped by Prometheus on demand.

    Parameters
    ----------
    port:
        TCP port for the ``/metrics`` HTTP endpoint (default: 8000).
    """

    def __init__(self, port: int = 8000) -> None:
        self._port = port
        self._gauges: Dict[str, Any] = {}
        self._httpd: Any = None  # set in setup() once HTTP server is started

    def setup(self) -> None:
        """Start the Prometheus HTTP server and register gauge metrics."""
        try:
            from prometheus_client import Gauge, start_http_server
        except ImportError as exc:
            raise RuntimeError(
                "prometheus_client is not installed. "
                "Run: pip install prometheus_client"
            ) from exc

        label = ["pipeline_id"]
        self._gauges["avg_fps"] = Gauge(
            "pipeline_avg_fps", "Rolling average FPS per pipeline", label
        )
        self._gauges["current_fps"] = Gauge(
            "pipeline_current_fps", "Instantaneous FPS per pipeline", label
        )
        self._gauges["avg_latency_ms"] = Gauge(
            "pipeline_avg_latency_ms",
            "Rolling average inference latency in milliseconds per pipeline",
            label,
        )
        self._gauges["frame_count"] = Gauge(
            "pipeline_frame_count", "Total frames processed per pipeline", label
        )
        self._gauges["running"] = Gauge(
            "pipeline_running",
            "1 if the pipeline is in PLAYING state, 0 otherwise",
            label,
        )

        # start_http_server returns an (httpd, thread) tuple in prometheus_client >= 0.12
        result = start_http_server(self._port)
        self._httpd = result[0] if isinstance(result, tuple) else None
        logger.info("Prometheus exporter listening on :%d/metrics", self._port)

    def export(self, snapshots: List[Dict[str, Any]]) -> None:
        """Update Prometheus gauges from *snapshots*."""
        for snap in snapshots:
            pid = snap["id"]
            self._gauges["avg_fps"].labels(pipeline_id=pid).set(snap["avg_fps"])
            self._gauges["current_fps"].labels(pipeline_id=pid).set(snap["current_fps"])
            self._gauges["avg_latency_ms"].labels(pipeline_id=pid).set(snap["avg_latency_ms"])
            self._gauges["frame_count"].labels(pipeline_id=pid).set(snap["frame_count"])
            self._gauges["running"].labels(pipeline_id=pid).set(
                1 if snap["state"].upper() == "PLAYING" else 0
            )

    def teardown(self) -> None:
        """Shut down the Prometheus HTTP server if a handle is available."""
        httpd = getattr(self, "_httpd", None)
        if httpd is not None:
            try:
                httpd.shutdown()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Log exporter (debug / fallback)
# ---------------------------------------------------------------------------


class LogExporter(MetricsExporter):
    """
    Writes pipeline metrics to the Python logger at DEBUG level.

    Useful for local development and as a reference implementation.
    """

    def export(self, snapshots: List[Dict[str, Any]]) -> None:
        for snap in snapshots:
            logger.debug(
                "[metrics] id=%-14s  state=%-10s  fps_avg=%-6.1f  fps_now=%-6.1f"
                "  lat_avg=%.2f ms  frames=%d",
                snap["id"],
                snap["state"],
                snap["avg_fps"],
                snap["current_fps"],
                snap["avg_latency_ms"],
                snap["frame_count"],
            )
