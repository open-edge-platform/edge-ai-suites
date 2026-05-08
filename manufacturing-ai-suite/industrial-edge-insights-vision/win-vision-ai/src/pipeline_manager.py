"""
manager.py — manages a pool of parallel GStreamer pipelines sharing one GLib main loop.

The GLib main loop is a module-level singleton started on the first ``PipelineManager``
instantiation and shared by all instances.  It is never restarted once stopped.

Lifecycle
---------
1. ``manager.create(launch_string, ...)``   → returns a pipeline_id (UUID)
2. ``manager.status(pipeline_id)``          → dict with state + metrics
3. ``manager.stop(pipeline_id)``            → graceful (EOS) or forced abort
4. ``manager.remove(pipeline_id)``          → explicit cleanup after terminal state
5. ``manager.shutdown()``                   → stop all pipelines + quit GLib loop
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402

from pipeline import Pipeline, PipelineState  # noqa: E402

logger = logging.getLogger(__name__)

# ── module-level GLib main loop singleton ─────────────────────────────────────
_loop_lock = threading.Lock()
_mainloop: Optional[GLib.MainLoop] = None
_mainloop_thread: Optional[threading.Thread] = None


def _ensure_mainloop() -> None:
    """Start the GLib main loop in a daemon thread if it is not yet running."""
    global _mainloop, _mainloop_thread
    with _loop_lock:
        if _mainloop is not None and _mainloop.is_running():
            return
        _mainloop = GLib.MainLoop()
        _mainloop_thread = threading.Thread(
            target=_mainloop.run,
            name="glib-mainloop",
            daemon=True,
        )
        _mainloop_thread.start()
        logger.info("GLib main loop started (thread %s)", _mainloop_thread.name)


def _quit_mainloop() -> None:
    global _mainloop
    with _loop_lock:
        if _mainloop is not None and _mainloop.is_running():
            _mainloop.quit()
            logger.info("GLib main loop stopped")
        _mainloop = None


class PipelineManager:
    """
    Create, monitor, and stop multiple GStreamer pipelines running in parallel.

    All pipelines share a single GLib main loop that drives GStreamer's bus
    callbacks and GLib timers.

    Thread safety
    -------------
    ``create()``, ``stop()``, ``status()``, ``remove()``, and ``list_all()`` are
    safe to call from any thread.
    """

    def __init__(self) -> None:
        Gst.init(None)
        _ensure_mainloop()
        self._pipelines: Dict[str, Pipeline] = {}
        self._lock = threading.Lock()
        self._pending_teardowns: set[str] = set()
        self._teardown_done = threading.Event()
        self._teardown_done.set()  # nothing pending yet

    # ── pipeline lifecycle ────────────────────────────────────────────────────

    def create(
        self,
        launch_string: str,
        pipeline_id: Optional[str] = None,
        source_element_name: Optional[str] = None,
        sink_element_name: Optional[str] = None,
        on_state_change: Optional[Callable[..., None]] = None,
        on_completed: Optional[Callable[..., None]] = None,
        on_error: Optional[Callable[..., None]] = None,
    ) -> str:
        """
        Parse and start a new pipeline.

        Parameters
        ----------
        launch_string:
            Full ``gst-launch-1.0``-style description, e.g.
            ``"videotestsrc name=src ! videoconvert ! fakesink name=sink"``.
        pipeline_id:
            Optional stable identifier; a UUID is generated when omitted.
        source_element_name:
            Element name (``name=`` in launch string) for latency source probe.
        sink_element_name:
            Element name (``name=`` in launch string) for FPS + latency sink probe.
        on_state_change:
            Callback ``(pipeline_id: str, state: PipelineState) → None``.
        on_completed:
            Callback ``(pipeline_id: str) → None`` on EOS.
        on_error:
            Callback ``(pipeline_id: str, error: str, debug: str | None) → None``.

        Returns
        -------
        str
            The pipeline's ID (same as ``pipeline_id`` when provided).
        """
        pid = pipeline_id or str(uuid.uuid4())

        pipeline = Pipeline(
            pipeline_id=pid,
            launch_string=launch_string,
            source_element_name=source_element_name,
            sink_element_name=sink_element_name,
            on_state_change=on_state_change,
            on_completed=on_completed,
            on_error=on_error,
            finished_callback=self._on_pipeline_finished,
        )

        # Register BEFORE starting to guarantee the entry exists when any
        # callback (including an immediate-failure finished_callback) fires.
        with self._lock:
            self._pipelines[pid] = pipeline
            self._pending_teardowns.add(pid)
            self._teardown_done.clear()

        # start() is called OUTSIDE the lock to prevent deadlock: if start()
        # fails synchronously it calls finished_callback which does NOT touch
        # the manager dict (see _on_pipeline_finished below).
        pipeline.start()
        return pid

    def stop(
        self,
        pipeline_id: str,
        graceful: bool = True,
        timeout_s: float = 5.0,
    ) -> None:
        """
        Stop a running pipeline.

        Parameters
        ----------
        graceful:
            Send EOS first and allow ``timeout_s`` seconds for clean completion
            before forcing an immediate abort.
        timeout_s:
            How long to wait for graceful EOS before forcing abort.
        """
        pipeline = self._get(pipeline_id)
        if pipeline is not None:
            pipeline.stop(graceful=graceful, timeout_s=timeout_s)
        else:
            logger.warning("stop: pipeline '%s' not found", pipeline_id)

    def stop_all(self, graceful: bool = True, timeout_s: float = 5.0) -> None:
        """Stop all managed pipelines."""
        with self._lock:
            ids = list(self._pipelines.keys())
        for pid in ids:
            self.stop(pid, graceful=graceful, timeout_s=timeout_s)

    def remove(self, pipeline_id: str) -> None:
        """
        Remove a pipeline from the registry.

        Call this after a pipeline has reached a terminal state
        (COMPLETED, ABORTED, or ERROR) to free the manager entry.
        Logs a warning if called on a non-terminal pipeline.
        """
        with self._lock:
            pipeline = self._pipelines.pop(pipeline_id, None)

        if pipeline is None:
            logger.warning("remove: pipeline '%s' not found", pipeline_id)
        elif not pipeline.state.is_terminal():
            logger.warning(
                "remove: pipeline '%s' is in non-terminal state %s",
                pipeline_id,
                pipeline.state.value,
            )

    # ── status / introspection ────────────────────────────────────────────────

    def status(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the status snapshot for one pipeline, or ``None`` if not found.
        """
        pipeline = self._get(pipeline_id)
        return pipeline.status() if pipeline is not None else None

    def list_all(self) -> List[Dict[str, Any]]:
        """Return status snapshots for every managed pipeline."""
        with self._lock:
            pipelines = list(self._pipelines.values())
        return [p.status() for p in pipelines]

    # ── shutdown ──────────────────────────────────────────────────────────────

    def shutdown(self, graceful: bool = True, timeout_s: float = 5.0) -> None:
        """
        Stop all pipelines and stop the shared GLib main loop.

        When ``graceful`` is True (default), pipelines are sent EOS and given
        ``timeout_s`` seconds to finish naturally before being forcibly aborted.
        Waits for all pipeline teardown threads to complete (so NULL state
        transitions actually finish) before quitting the GLib main loop.

        After ``shutdown()`` this manager instance should not be used.
        """
        self.stop_all(graceful=graceful, timeout_s=timeout_s)
        wait_s = timeout_s + 2.0 if graceful else 5.0
        if not self._teardown_done.wait(timeout=wait_s):
            with self._lock:
                pending = sorted(self._pending_teardowns)
            logger.warning("shutdown: teardown timed out, pending=%s", pending)
        _quit_mainloop()

    # ── internal helpers ──────────────────────────────────────────────────────

    def _on_pipeline_finished(self, pipeline_id: str) -> None:
        """
        Called by Pipeline after its GStreamer teardown completes.

        Intentionally does NOT remove the entry from ``_pipelines`` — callers
        must explicitly call ``remove()`` so that terminal status remains
        observable.  This also avoids any lock-ordering issues between the
        teardown thread and the manager lock.
        """
        logger.info("Pipeline '%s' teardown complete", pipeline_id)
        with self._lock:
            self._pending_teardowns.discard(pipeline_id)
            if not self._pending_teardowns:
                self._teardown_done.set()

    def _get(self, pipeline_id: str) -> Optional[Pipeline]:
        with self._lock:
            return self._pipelines.get(pipeline_id)
