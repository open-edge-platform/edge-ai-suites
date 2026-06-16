#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""
metrics_collector.py — Background metrics polling loop.

:class:`MetricsCollector` polls
:meth:`~win_vision_ai.pipeline_manager.PipelineManager.list_all` on a daemon
thread and pushes snapshots to a :class:`~win_vision_ai.metrics_exporters.MetricsExporter`.

Usage::

    from metrics_collector import MetricsCollector
    from metrics_exporters import LogExporter

    collector = MetricsCollector(manager, cfg.metrics, LogExporter())
    collector.start()
    ...
    collector.stop()
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Optional

from config_loader import MetricsConfig
from metrics_exporters import LogExporter, MetricsExporter

if TYPE_CHECKING:
    from pipeline_manager import PipelineManager

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Periodically polls :class:`~win_vision_ai.pipeline_manager.PipelineManager`
    and pushes snapshots to an exporter.

    Parameters
    ----------
    manager:
        The pipeline manager whose pipelines are being monitored.
    config:
        Metrics configuration (enabled flag, polling interval).
    exporter:
        Where to send the metrics.  Defaults to :class:`~win_vision_ai.metrics_exporters.LogExporter`
        when ``None``.
    """

    def __init__(
        self,
        manager: "PipelineManager",
        config: MetricsConfig,
        exporter: Optional[MetricsExporter] = None,
    ) -> None:
        self._manager = manager
        self._config = config
        self._exporter: MetricsExporter = exporter or LogExporter()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ── lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background polling thread (no-op when metrics are disabled)."""
        if not self._config.enabled:
            logger.info("Metrics collection disabled by config")
            return

        self._exporter.setup()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._collect_loop,
            name="metrics-collector",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "MetricsCollector started (interval=%.1fs)", self._config.export_interval_s
        )

    def stop(self, timeout_s: float = 5.0) -> None:
        """Signal the polling thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout_s)
            self._thread = None
        self._exporter.teardown()
        logger.info("MetricsCollector stopped")

    # ── internal ──────────────────────────────────────────────────────────

    def _collect_loop(self) -> None:
        """Background thread: poll -> export on each interval tick."""
        while not self._stop_event.wait(timeout=self._config.export_interval_s):
            try:
                snapshots = self._manager.list_all()
                self._exporter.export(snapshots)
            except Exception:
                logger.exception("MetricsCollector: unhandled error in collect loop")
        logger.debug("MetricsCollector loop exited")
