"""
pipeline.py — GStreamer pipeline wrapper with state tracking, FPS and latency metrics.

Threading model
---------------
- GLib main loop thread  : bus_call() and GLib timeout callbacks run here.
- GStreamer streaming threads : pad probes (_source_pad_probe, _sink_pad_probe) run here.
- External/caller threads : start(), stop(), status() may be called from any thread.
- Teardown thread         : _do_delete_pipeline() spawned to avoid blocking the GLib loop.

Lock discipline
---------------
_state_lock     : guards `state` field only.
_metrics_lock   : guards all FPS/latency counters.
_latency_lock   : guards `_latency_times` dict (source→sink matching).
_delete_lock    : ensures _delete_pipeline() runs exactly once.

Locks are NEVER held simultaneously — each critical section acquires at most one lock.
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402


logger = logging.getLogger(__name__)


class PipelineState(Enum):
    QUEUED = "QUEUED"
    PLAYING = "PLAYING"
    ABORTED = "ABORTED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"

    def is_terminal(self) -> bool:
        return self in (
            PipelineState.ABORTED,
            PipelineState.COMPLETED,
            PipelineState.ERROR,
        )


class Pipeline:
    """
    Wraps a single GStreamer pipeline described by an externally-provided launch string.

    Parameters
    ----------
    pipeline_id:
        Unique identifier for this pipeline instance.
    launch_string:
        A ``gst-launch-1.0``-style pipeline description passed verbatim to
        ``Gst.parse_launch()``.  Constructed by the caller; not interpreted here.
    source_element_name:
        Name of the first/source element (as given by ``name=`` in the launch string)
        to attach a latency source-probe on its ``src`` pad.  If the element exposes
        dynamic pads (e.g. ``decodebin``) the probe is deferred to ``pad-added``.
        When ``None`` latency measurement is disabled.
    sink_element_name:
        Name of the final/sink element to attach FPS + latency sink-probe on its
        ``sink`` pad.  When ``None`` FPS measurement is disabled.
    on_state_change:
        Called with ``(pipeline_id=str, state=PipelineState)`` when state changes.
    on_completed:
        Called with ``(pipeline_id=str,)`` on EOS.
    on_error:
        Called with ``(pipeline_id=str, error=str, debug=str|None)`` on GStreamer error.
    finished_callback:
        Internal hook called by the manager after teardown completes.
    """

    def __init__(
        self,
        pipeline_id: str,
        launch_string: str,
        source_element_name: Optional[str] = None,
        sink_element_name: Optional[str] = None,
        on_state_change: Optional[Callable[..., None]] = None,
        on_completed: Optional[Callable[..., None]] = None,
        on_error: Optional[Callable[..., None]] = None,
        finished_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.id = pipeline_id
        self.launch_string = launch_string
        self.source_element_name = source_element_name
        self.sink_element_name = sink_element_name

        self._on_state_change = on_state_change
        self._on_completed = on_completed
        self._on_error = on_error
        self._finished_callback = finished_callback

        # ── state ──────────────────────────────────────────────────────────────
        self.state = PipelineState.QUEUED
        self._state_lock = threading.Lock()

        # ── GStreamer handles ──────────────────────────────────────────────────
        self.pipeline: Optional[Gst.Pipeline] = None
        self._bus_signal_id: Optional[int] = None

        # ── delete guard ──────────────────────────────────────────────────────
        self._delete_lock = threading.Lock()
        self._deleted = False
        self._stop_requested = False

        # ── FPS / frame metrics  (accessed from streaming threads) ────────────
        self._metrics_lock = threading.Lock()
        self._frame_count = 0
        self._start_time: Optional[float] = None
        self._last_fps_time: Optional[float] = None
        self._last_fps_frame_count = 0
        self._avg_fps = 0.0
        self._current_fps = 0.0

        # ── Latency metrics ───────────────────────────────────────────────────
        # Probe on source pad records wall-clock timestamp keyed by PTS.
        # Probe on sink pad pops that entry and accumulates round-trip latency.
        self._latency_lock = threading.Lock()
        self._latency_times: Dict[int, float] = {}  # pts (ns) → wall time (s)

        self._total_latency_ms = 0.0
        self._matched_latency_count = 0
        self._avg_latency_ms = 0.0

    # ── public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Parse the launch string and transition the pipeline to PLAYING."""
        try:
            self.pipeline = Gst.parse_launch(self.launch_string)
        except Exception as exc:
            logger.error("[%s] parse_launch failed: %s", self.id, exc)
            self._set_state(PipelineState.ERROR)
            self._invoke_callback(self._on_error, error=str(exc), debug=None)
            if self._finished_callback:
                self._finished_callback(self.id)
            return

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        self._bus_signal_id = bus.connect("message", self._bus_call)

        self._attach_pad_probes()

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("[%s] set_state(PLAYING) failed", self.id)
            self._set_state(PipelineState.ERROR)
            self._invoke_callback(self._on_error, error="set_state(PLAYING) failed", debug=None)
            self._delete_pipeline()

    def stop(self, graceful: bool = True, timeout_s: float = 5.0) -> None:
        """
        Stop the pipeline.

        Parameters
        ----------
        graceful:
            If ``True`` an EOS event is sent first and the pipeline is given
            ``timeout_s`` seconds to finish naturally before a forced abort is
            posted via an APPLICATION bus message.
            If ``False`` the APPLICATION/stop message is posted immediately.
        timeout_s:
            Seconds to wait for graceful EOS before forcing abort.
        """
        with self._state_lock:
            if self.state.is_terminal():
                return  # already done

        self._stop_requested = True
        if graceful and self.pipeline is not None:
            self.pipeline.send_event(Gst.Event.new_eos())
            GLib.timeout_add(int(timeout_s * 1000), self._force_abort)
        else:
            self._post_stop_message()

    def status(self) -> Dict[str, Any]:
        """Return a snapshot of current state and metrics (safe to call from any thread)."""
        with self._state_lock:
            state = self.state
        with self._metrics_lock:
            return {
                "id": self.id,
                "state": state.value,
                "frame_count": self._frame_count,
                "avg_fps": round(self._avg_fps, 2),
                "current_fps": round(self._current_fps, 2),
                "avg_latency_ms": round(self._avg_latency_ms, 2),
            }

    # ── bus callback (GLib main loop thread) ──────────────────────────────────

    def _bus_call(self, bus: Gst.Bus, message: Gst.Message) -> bool:
        mtype = message.type

        if mtype == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old, new, _ = message.parse_state_changed()
                if old == Gst.State.PAUSED and new == Gst.State.PLAYING:
                    self._set_state(PipelineState.PLAYING)
                    logger.info("[%s] -> PLAYING", self.id)
                    self._invoke_callback(self._on_state_change, state=PipelineState.PLAYING)

        elif mtype == Gst.MessageType.EOS:
            if self._stop_requested:
                logger.info("[%s] EOS -> ABORTED", self.id)
                self._set_state(PipelineState.ABORTED)
            else:
                logger.info("[%s] EOS -> COMPLETED", self.id)
                self._set_state(PipelineState.COMPLETED)
                self._invoke_callback(self._on_completed)
            self._delete_pipeline()

        elif mtype == Gst.MessageType.ERROR:
            err, dbg = message.parse_error()
            logger.error("[%s] ERROR: %s | debug: %s", self.id, err.message, dbg)
            self._set_state(PipelineState.ERROR)
            self._invoke_callback(self._on_error, error=err.message, debug=dbg)
            self._delete_pipeline()

        elif mtype == Gst.MessageType.APPLICATION:
            structure = message.get_structure()
            if structure is not None and structure.get_name() == "stop":
                logger.info("[%s] APPLICATION/stop -> ABORTED", self.id)
                self._set_state(PipelineState.ABORTED)
                self._delete_pipeline()

        return True  # keep watch active

    # ── pad probes (GStreamer streaming threads) ───────────────────────────────

    def _attach_pad_probes(self) -> None:
        """Attach source and sink pad probes. Requires self.pipeline to be set."""
        if self.source_element_name:
            self._attach_source_probe(self.source_element_name)

        if self.sink_element_name:
            self._attach_sink_probe_by_name(self.sink_element_name)
        else:
            self._attach_sink_probe_auto()

    def _attach_source_probe(self, name: str) -> None:
        elem = self.pipeline.get_by_name(name)
        if elem is None:
            logger.warning("[%s] Source element '%s' not found in pipeline", self.id, name)
            return

        pad = elem.get_static_pad("src")
        if pad is not None:
            pad.add_probe(Gst.PadProbeType.BUFFER, self._source_pad_probe)
            logger.debug("[%s] Source probe attached to %s:src (static)", self.id, name)
        else:
            # Dynamic-pad element (e.g. decodebin, urisourcebin)
            elem.connect("pad-added", self._on_dynamic_source_pad)
            logger.debug("[%s] Source element %s has no static src pad - using pad-added", self.id, name)

    def _attach_sink_probe_by_name(self, name: str) -> None:
        """Attach sink pad probe to a named element."""
        elem = self.pipeline.get_by_name(name)
        if elem is None:
            logger.warning("[%s] Sink element '%s' not found in pipeline", self.id, name)
            return
        self._attach_sink_probe_to_elem(elem)

    def _attach_sink_probe_auto(self) -> None:
        """Auto-detect the terminal sink element and attach a pad probe to it.

        Uses pipeline.iterate_sinks() so the probe is always on the actual output
        element (rtspclientsink, whipclientsink, autovideosink, fakesink, etc.)
        regardless of what the user puts in the launch string.
        """
        it = self.pipeline.iterate_sinks()
        result, elem = it.next()
        if result != Gst.IteratorResult.OK or elem is None:
            logger.info("[%s] No sink element found - FPS metrics disabled", self.id)
            return
        logger.debug("[%s] Auto-detected sink element: %s", self.id, elem.get_name())
        self._attach_sink_probe_to_elem(elem)

    def _attach_sink_probe_to_elem(self, elem: Gst.Element) -> None:
        """Attach a sink pad probe to an element, trying static pad then iterating pads."""
        name = elem.get_name()
        # Try static sink pad first; fall back to iterating pads (handles ghost pads
        # in bin elements such as rtspclientsink / whipclientsink).
        pad = elem.get_static_pad("sink")
        if pad is None:
            it = elem.iterate_sink_pads()
            result, pad = it.next()
            if result != Gst.IteratorResult.OK or pad is None:
                logger.warning(
                    "[%s] Sink element '%s' has no accessible sink pad - metrics disabled",
                    self.id, name,
                )
                return

        pad.add_probe(Gst.PadProbeType.BUFFER, self._sink_pad_probe)
        logger.debug("[%s] Sink probe attached to %s:%s", self.id, name, pad.get_name())

    def _on_dynamic_source_pad(self, element: Gst.Element, pad: Gst.Pad) -> None:
        """Deferred source probe for elements with dynamic pads."""
        pad.add_probe(Gst.PadProbeType.BUFFER, self._source_pad_probe)
        logger.debug("[%s] Source probe attached to dynamic pad %s", self.id, pad.get_name())

    def _source_pad_probe(self, pad: Gst.Pad, info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        """Record the wall-clock time of each buffer, keyed by PTS."""
        buf = info.get_buffer()
        if buf is None or buf.pts == Gst.CLOCK_TIME_NONE:
            return Gst.PadProbeReturn.OK

        now = time.monotonic()
        with self._latency_lock:
            self._latency_times[buf.pts] = now
            # Evict entries older than 30 s to prevent unbounded growth
            stale: List[int] = [
                pts for pts, ts in self._latency_times.items() if now - ts > 30.0
            ]
            for pts in stale:
                del self._latency_times[pts]

        return Gst.PadProbeReturn.OK

    def _sink_pad_probe(self, pad: Gst.Pad, info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        """Count frames, compute FPS, and match latency against source probe."""
        buf = info.get_buffer()
        if buf is None:
            return Gst.PadProbeReturn.OK

        now = time.monotonic()

        # ── frame count + FPS  (metrics_lock) ────────────────────────────────
        with self._metrics_lock:
            self._frame_count += 1

            if self._start_time is None:
                self._start_time = now
                self._last_fps_time = now
                self._last_fps_frame_count = 0

            elapsed = now - self._start_time
            self._avg_fps = self._frame_count / elapsed if elapsed > 0 else 0.0

            delta = now - self._last_fps_time
            if delta >= 1.0:
                self._current_fps = (self._frame_count - self._last_fps_frame_count) / delta
                self._last_fps_time = now
                self._last_fps_frame_count = self._frame_count

        # ── latency matching  (latency_lock, then metrics_lock separately) ────
        if buf.pts != Gst.CLOCK_TIME_NONE:
            with self._latency_lock:
                source_time = self._latency_times.pop(buf.pts, None)

            if source_time is not None:
                latency_ms = (now - source_time) * 1000.0
                with self._metrics_lock:
                    self._total_latency_ms += latency_ms
                    self._matched_latency_count += 1
                    self._avg_latency_ms = (
                        self._total_latency_ms / self._matched_latency_count
                    )

        return Gst.PadProbeReturn.OK

    # ── teardown helpers ──────────────────────────────────────────────────────

    def _force_abort(self) -> bool:
        """GLib timeout callback — post abort if pipeline has not already completed."""
        with self._state_lock:
            if not self.state.is_terminal():
                logger.warning("[%s] Graceful EOS timed out - forcing abort", self.id)
                self._post_stop_message()
        return False  # do not repeat

    def _post_stop_message(self) -> None:
        """Post an APPLICATION/stop message on the bus for asynchronous teardown."""
        if self.pipeline is not None:
            structure = Gst.Structure.new_empty("stop")
            msg = Gst.Message.new_application(self.pipeline, structure)
            self.pipeline.get_bus().post(msg)

    def _delete_pipeline(self) -> None:
        """Trigger teardown.  Called from the GLib main loop thread (bus_call) or
        error paths.  Actual work is done on a dedicated thread to avoid blocking
        the shared GLib main loop."""
        with self._delete_lock:
            if self._deleted:
                return
            self._deleted = True

        threading.Thread(
            target=self._do_delete_pipeline,
            name=f"pipeline-teardown-{self.id}",
            daemon=True,
        ).start()

    def _do_delete_pipeline(self) -> None:
        """Perform blocking NULL-state transition on a dedicated thread."""
        if self.pipeline is None:
            self._notify_finished()
            return

        # Disconnect bus watch first so no more bus callbacks fire
        bus = self.pipeline.get_bus()
        if self._bus_signal_id is not None:
            bus.disconnect(self._bus_signal_id)
            self._bus_signal_id = None
        bus.remove_signal_watch()

        self.pipeline.set_state(Gst.State.NULL)
        ret, _, _ = self.pipeline.get_state(5 * Gst.SECOND)
        if ret != Gst.StateChangeReturn.SUCCESS:
            logger.warning(
                "[%s] NULL transition incomplete (returned %s)", self.id, ret
            )

        self.pipeline = None
        logger.info("[%s] Pipeline torn down", self.id)
        self._notify_finished()

    def _notify_finished(self) -> None:
        if self._finished_callback:
            try:
                self._finished_callback(self.id)
            except Exception as exc:
                logger.error("[%s] finished_callback raised: %s", self.id, exc)

    # ── internal helpers ──────────────────────────────────────────────────────

    def _set_state(self, new_state: PipelineState) -> None:
        with self._state_lock:
            self.state = new_state

    def _invoke_callback(self, cb: Optional[Callable], **kwargs: Any) -> None:
        """Dispatch a user callback, swallowing any exceptions."""
        if cb is None:
            return
        try:
            cb(pipeline_id=self.id, **kwargs)
        except Exception as exc:
            logger.error("[%s] User callback %s raised: %s", self.id, cb, exc)
