#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import logging
import signal
import sys
import threading
from typing import TYPE_CHECKING

from pipeline import PipelineState

if TYPE_CHECKING:
    from pipeline_manager import PipelineManager

logger = logging.getLogger(__name__)


class AppRunner:

    def _wait_for_completion(self) -> None:
        # threading.Event acts as a wake-up call. Instead of sleeping a fixed 1s, the main thread can be woken instantly.
        self._stop_event = threading.Event()
        try:
            while self._running:
                # Main thread parks here for up to 1s.
                # _handle_signal() calls _stop_event.set() which wakes this immediately.
                self._stop_event.wait(timeout=1.0)
                if not self._running:
                    break
                statuses = self._manager.list_all()
                if not statuses:
                    logger.info("No active pipelines - exiting")
                    break
                logger.info("--- pipeline status ---")
                for s in statuses:
                    if getattr(self, "_metrics_enabled", True):
                        logger.info(
                            "  %-16s  state=%-10s  fps_avg=%-6.1f  fps_now=%-6.1f  lat_avg=%.2f ms  frames=%d",
                            s["id"], s["state"], s["avg_fps"], s["current_fps"], s["avg_latency_ms"], s["frame_count"],
                        )
                    else:
                        logger.info(
                            "  %-16s  state=%-10s  frames=%d",
                            s["id"], s["state"], s["frame_count"],
                        )
                if all(PipelineState(s["state"]).is_terminal() for s in statuses):
                    logger.info("All pipelines finished - exiting")
                    break
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt - stopping")
        finally:
            # Runs whether we exited via Ctrl+C, all pipelines finished, or an error.
            self.stop()

    def _install_signal_handlers(self) -> None:
        # Tell the OS: "when Ctrl+C is pressed, call _handle_signal instead of crashing"
        signal.signal(signal.SIGINT, self._handle_signal)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, sig: int, _frame: object) -> None:
        # Called automatically by Python on the main thread when Ctrl+C is pressed.
        # No separate thread — Python interrupts whatever the main thread was doing.
        logger.info("Signal %d received - stopping", sig)
        # Tell the wait loop to stop on its next iteration.
        self._running = False
        # Wake the main thread immediately instead of waiting for the 1s timeout.
        if hasattr(self, "_stop_event"):
            self._stop_event.set()

    def _on_state_change(self, pipeline_id: str, state: PipelineState) -> None:
        logger.info("[%s] -> %s", pipeline_id, state.value)

    def _on_completed(self, pipeline_id: str) -> None:
        logger.info("[%s] COMPLETED", pipeline_id)
        self._manager.remove(pipeline_id)

    def _on_error(self, pipeline_id: str, error: str, debug: str | None = None) -> None:
        logger.error("[%s] ERROR: %s (debug: %s)", pipeline_id, error, debug)
        self._manager.remove(pipeline_id)
