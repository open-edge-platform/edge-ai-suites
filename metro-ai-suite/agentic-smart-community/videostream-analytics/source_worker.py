"""Manages registered video sources and their pipelines."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from shared.config import (
    AppConfig,
    SourceConfig,
    WebhookConfig,
    MotionConfig,
    SegmentConfig,
    PrefilterConfig,
    RoiConfig,
    RecordingConfig,
    HealthConfig,
    KeepaliveConfig,
    expand_path,
    expand_user_path,
    merge_config,
    resolve_contained_dir,
    validate_effective_segment,
)
from stream_monitor.rtsp_monitor import StreamPipeline
from stream_monitor.continuous_recorder import ContinuousRecorder
from sinks import EventSink, WebhookSink

logger = logging.getLogger(__name__)


def _log_id(source_id: str) -> str:
    """Strip line breaks from `source_id` before it reaches a log line.

    A no-op in practice. Every `source_id` that can get here has already been
    matched against `service.SOURCE_ID_PATTERN` (`^[A-Za-z0-9_-]{1,128}$`) —
    on the request body via a pydantic `Field(pattern=...)` and on every path
    parameter via `service.SourceIdPath` — so a line break cannot be present.

    It exists because that constraint lives in another module behind pydantic's
    declarative validation, which static analysis cannot see through: CodeQL
    treats the whole request object as tainted and flags every log call below
    as `py/log-injection` without an explicit scrub on the data flow. Inline
    suppression comments (`# codeql[...]` / `# lgtm[...]`) do not work — they
    are honoured by GitHub code scanning at ingestion, not by
    `codeql database analyze`, which is what the SDL gate runs.

    Keep the literal `"\\n"` argument: the query only recognises
    `.replace("\\n", ...)` / `.replace("\\r\\n", ...)` with a string literal as a
    sanitizer, so hoisting it into a constant silently re-opens all findings.
    """
    return source_id.replace("\n", "").replace("\r", "")


@dataclass
class SourceBundle:
    """Per-source state: motion pipeline + optional continuous recorder + sink.

    `lock` serializes the slow lifecycle operations on THIS source (stop/start
    each `join(timeout=10)` on a worker thread). It is deliberately per-bundle
    rather than a manager-wide lock so a 20-second teardown of one source does
    not stall requests for every other source, and deliberately owned by the
    bundle rather than keyed by `source_id` so it cannot accumulate entries for
    ids that no longer exist.
    """

    pipeline: StreamPipeline
    recorder: ContinuousRecorder | None
    sink: EventSink
    data_dir: str
    keepalive: KeepaliveConfig | None = None
    last_keepalive_at: float | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)


class SourceManager:
    """Registry of live sources.

    Thread-safety model — endpoints run in FastAPI's threadpool, so every
    public method here can be called concurrently:

    * `_registry_lock` guards ONLY the `_bundles` dict and the `_registering`
      set. Every critical section under it is a dict/set operation, never a
      `join()`, so it is never held for a meaningful length of time.
    * Slow work happens outside `_registry_lock`, under the relevant
      `SourceBundle.lock`. A caller that intends to destroy a bundle first pops
      it from `_bundles` under `_registry_lock`; after that pop no other caller
      can reach it, so tearing it down unlocked is safe.
    * `_registering` makes concurrent registrations of the SAME id mutually
      exclusive. Without it the "read `_bundles` -> build -> write `_bundles`"
      sequence is a lost update: both callers build a full pipeline + recorder
      (threads and an ffmpeg child process each), only one lands in the dict,
      and the other leaks forever while still writing to `data_dir`.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self._default_sink: EventSink = WebhookSink(config.webhook)
        self._bundles: dict[str, SourceBundle] = {}
        self._registry_lock = threading.RLock()
        self._registering: set[str] = set()
        self._watchdog_running = True
        # Use an Event instead of plain time.sleep so register_source can
        # wake the daemon up — otherwise a short-interval source registered
        # mid-sleep has to wait out the previous (potentially long) tick.
        self._watchdog_wakeup = threading.Event()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="keepalive-watchdog",
            daemon=True,
        )
        self._watchdog_thread.start()

    def _data_roots(self) -> list[str]:
        return [
            expand_path(self.config.data_dir),
            *(expand_path(r) for r in self.config.allowed_data_roots),
        ]

    def _resolve_data_dir(self, source: SourceConfig) -> str:
        """Resolve the output dir, refusing anything outside the permitted roots.

        A request-supplied `data_dir` is expanded with `expand_user_path` (no
        `$VAR` expansion — see its docstring) and then contained. The default
        branch is contained too: `source_id` is already constrained by the API
        layer's regex, but the regex and this join live in different files, so
        loosening either one on its own must not turn into a traversal.
        """
        roots = self._data_roots()
        if source.data_dir:
            return resolve_contained_dir(roots, expand_user_path(source.data_dir))
        return resolve_contained_dir(roots, os.path.join(roots[0], source.source_id))

    def _build_sink(self, source: SourceConfig) -> EventSink:
        if source.webhook_url:
            return WebhookSink(WebhookConfig(url=source.webhook_url))
        return self._default_sink

    def register_source(self, source: SourceConfig) -> dict[str, Any]:
        """Register and start a new video source pipeline.

        Concurrent calls for the same `source_id` are refused rather than
        queued: the loser would have to wait out a 20-second teardown holding a
        threadpool worker, which is exactly the amplification an unauthenticated
        caller would aim for.
        """
        source_id = source.source_id

        # Pure input validation FIRST, before any registry state is touched, so
        # a rejected request cannot have torn down the source it was replacing.
        # Neither of these depends on what is currently registered.
        validate_effective_segment(
            merge_config(self.config.defaults.segment, source.segment)
        )
        data_dir = self._resolve_data_dir(source)

        with self._registry_lock:
            if source_id in self._registering:
                return {"status": "registration_in_progress", "source_id": source_id}
            existing = self._bundles.get(source_id)
            if existing is not None and existing.pipeline.is_running:
                return {"status": "already_running", "source_id": source_id}
            # Claim the id for the whole build, and detach any dead bundle so no
            # other caller can reach the instance we are about to tear down.
            self._registering.add(source_id)
            if existing is not None:
                self._bundles.pop(source_id, None)
        try:
            return self._register_claimed(source, data_dir, existing)
        finally:
            with self._registry_lock:
                self._registering.discard(source_id)

    def _register_claimed(
        self, source: SourceConfig, data_dir: str, existing: SourceBundle | None
    ) -> dict[str, Any]:
        """Build and start the source. Caller holds the `_registering` claim."""
        if existing is not None:
            # Re-register: tear down old bundle so resources are released. Safe
            # outside `_registry_lock` — it is already detached from `_bundles`.
            with existing.lock:
                self._teardown_bundle(source.source_id, existing)

        sink = self._build_sink(source)
        os.makedirs(data_dir, exist_ok=True)

        pipeline = StreamPipeline(
            source=source,
            defaults=self.config.defaults,
            data_dir=data_dir,
            sink=sink,
            on_remove_callback=self._handle_source_removed,
        )

        recorder: ContinuousRecorder | None = None
        recording_cfg = merge_config(self.config.defaults.recording, source.recording)
        source.recording = recording_cfg
        if recording_cfg.enabled:
            recorder = ContinuousRecorder(
                source=source,
                recording_cfg=recording_cfg,
                data_dir=data_dir,
                sink=sink,
                protocol_whitelist=self.config.security.ffmpeg_protocol_whitelist,
            )

        keepalive_cfg = merge_config(self.config.defaults.keepalive, source.keepalive)
        source.keepalive = keepalive_cfg
        last_keepalive_at = time.time() if keepalive_cfg.enabled else None

        bundle = SourceBundle(
            pipeline=pipeline,
            recorder=recorder,
            sink=sink,
            data_dir=data_dir,
            keepalive=keepalive_cfg,
            last_keepalive_at=last_keepalive_at,
        )
        # Nudge the watchdog so a fresh source with a shorter check_interval
        # doesn't have to wait out the previous (potentially default 10s) tick.
        self._watchdog_wakeup.set()
        with self._registry_lock:
            self._bundles[source.source_id] = bundle
        with bundle.lock:
            pipeline.start()
            if recorder is not None:
                recorder.start()

        logger.info(
            "Registered source: %s (%s) data_dir=%s recording=%s",
            source.source_id,
            source.source_url,
            data_dir,
            recording_cfg.enabled,
        )
        return {
            "status": "started",
            "source_id": source.source_id,
            "source_url": source.source_url,
            "data_dir": data_dir,
        }

    def _teardown_bundle(self, source_id: str, bundle: SourceBundle) -> None:
        """Stop pipeline + recorder, close per-source sink if not default."""
        bundle.pipeline.stop()
        if bundle.recorder is not None:
            bundle.recorder.stop()
        if bundle.sink is not self._default_sink:
            try:
                bundle.sink.close()
            except Exception as e:
                logger.warning("[%s] sink close error: %s", _log_id(source_id), e)

    def unregister_source(self, source_id: str) -> dict[str, Any]:
        # Pop under the registry lock, tear down outside it. Once popped the
        # bundle is unreachable by any other caller, so the ~20s of `join()`
        # inside `_teardown_bundle` blocks only this request.
        with self._registry_lock:
            bundle = self._bundles.pop(source_id, None)
        if bundle is None:
            return {"status": "not_found", "source_id": source_id}
        with bundle.lock:
            self._teardown_bundle(source_id, bundle)
        logger.info("Unregistered source: %s", _log_id(source_id))
        return {"status": "stopped", "source_id": source_id}

    def _handle_source_removed(self, source_id: str):
        """Callback: pipeline triggered 'remove' recovery strategy.

        Runs on the pipeline's own worker thread, so it must not take
        `bundle.lock` — the thread it would wait on is itself.
        """
        with self._registry_lock:
            bundle = self._bundles.pop(source_id, None)
        if bundle is not None:
            # pipeline already self-stopped; clean up recorder + sink
            if bundle.recorder is not None:
                bundle.recorder.stop()
            if bundle.sink is not self._default_sink:
                try:
                    bundle.sink.close()
                except Exception:
                    pass
        logger.info("Source auto-removed by health policy: %s", source_id)

    def update_pipeline_config(
        self,
        source_id: str,
        motion: MotionConfig | None = None,
        segment: SegmentConfig | None = None,
        prefilter: PrefilterConfig | None = None,
        roi: RoiConfig | None = None,
        recording: RecordingConfig | None = None,
        health: HealthConfig | None = None,
    ) -> dict[str, Any]:
        """Hot-update pipeline config (stop + update + restart)."""
        with self._registry_lock:
            bundle = self._bundles.get(source_id)
        if bundle is None:
            return {"status": "not_found", "source_id": source_id}

        # Validate BEFORE stopping — a rejected update must leave the running
        # pipeline untouched rather than stopped-and-not-restarted.
        if segment is not None:
            current_segment = (
                bundle.pipeline.source.segment or self.config.defaults.segment
            )
            validate_effective_segment(merge_config(current_segment, segment))

        with bundle.lock:
            return self._update_pipeline_locked(
                source_id, bundle, motion, segment, prefilter, roi, recording, health
            )

    def _update_pipeline_locked(
        self,
        source_id: str,
        bundle: SourceBundle,
        motion: MotionConfig | None,
        segment: SegmentConfig | None,
        prefilter: PrefilterConfig | None,
        roi: RoiConfig | None,
        recording: RecordingConfig | None,
        health: HealthConfig | None,
    ) -> dict[str, Any]:
        """Stop + update + restart. Caller holds `bundle.lock`."""
        bundle.pipeline.stop()
        bundle.pipeline.update_pipeline_config(
            motion=motion,
            segment=segment,
            prefilter=prefilter,
            roi=roi,
            health=health,
        )
        bundle.pipeline.start()

        if recording is not None:
            current_recording = (
                bundle.pipeline.source.recording or self.config.defaults.recording
            )
            recording = merge_config(current_recording, recording)
            bundle.pipeline.source.recording = recording
            new_enabled = recording.enabled
            if bundle.recorder is not None:
                bundle.recorder.stop()
                if new_enabled:
                    bundle.recorder = ContinuousRecorder(
                        source=bundle.pipeline.source,
                        recording_cfg=recording,
                        data_dir=bundle.data_dir,
                        sink=bundle.sink,
                        protocol_whitelist=self.config.security.ffmpeg_protocol_whitelist,
                    )
                    bundle.recorder.start()
                else:
                    bundle.recorder = None
            elif new_enabled:
                bundle.recorder = ContinuousRecorder(
                    source=bundle.pipeline.source,
                    recording_cfg=recording,
                    data_dir=bundle.data_dir,
                    sink=bundle.sink,
                    protocol_whitelist=self.config.security.ffmpeg_protocol_whitelist,
                )
                bundle.recorder.start()

        logger.info("Pipeline config updated: %s", _log_id(source_id))
        return {"status": "updated", "source_id": source_id}

    def restart_source(self, source_id: str) -> dict[str, Any]:
        """Stop + start the pipeline (and recorder) in place.

        Lives here rather than in the endpoint so it runs under `bundle.lock`
        like every other lifecycle transition — the endpoint used to reach into
        `_bundles` directly and could interleave with an unregister.
        """
        with self._registry_lock:
            bundle = self._bundles.get(source_id)
        if bundle is None:
            return {"status": "not_found", "source_id": source_id}
        with bundle.lock:
            bundle.pipeline.stop()
            bundle.pipeline.start()
            if bundle.recorder is not None:
                bundle.recorder.stop()
                bundle.recorder.start()
        logger.info("Restarted source: %s", _log_id(source_id))
        return {"status": "restarted", "source_id": source_id}

    def pause_source(self, source_id: str) -> dict[str, Any]:
        with self._registry_lock:
            bundle = self._bundles.get(source_id)
        if bundle is None:
            return {"status": "not_found", "source_id": source_id}
        with bundle.lock:
            if not bundle.pipeline.is_running:
                return {"status": "not_running", "source_id": source_id}
            bundle.pipeline.pause()
            if bundle.recorder is not None:
                bundle.recorder.pause()
        return {"status": "paused", "source_id": source_id}

    def resume_source(self, source_id: str) -> dict[str, Any]:
        with self._registry_lock:
            bundle = self._bundles.get(source_id)
        if bundle is None:
            return {"status": "not_found", "source_id": source_id}
        with bundle.lock:
            if not bundle.pipeline.is_running:
                return {"status": "not_running", "source_id": source_id}
            bundle.pipeline.resume()
            if bundle.recorder is not None:
                bundle.recorder.resume()
        return {"status": "online", "source_id": source_id}

    def keepalive_source(self, source_id: str) -> dict[str, Any]:
        """Refresh `last_keepalive_at` for a source.

        Returns `{"status": "not_found"}` if the source isn't registered, else
        `{"status": "ok", "source_id": ..., "last_keepalive_at": <iso>}`.
        """
        with self._registry_lock:
            bundle = self._bundles.get(source_id)
        if bundle is None:
            return {"status": "not_found", "source_id": source_id}
        # No `bundle.lock` here: this is the hot path (MCP pings every ~30s per
        # source) and a single float assignment is atomic. Taking the lock would
        # make keepalive queue behind a 20s teardown and time out for no reason.
        now = time.time()
        bundle.last_keepalive_at = now
        return {
            "status": "ok",
            "source_id": source_id,
            "last_keepalive_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        }

    def get_sources(self) -> list[dict[str, Any]]:
        """List all registered sources with their status."""
        with self._registry_lock:
            snapshot = list(self._bundles.items())
        # Describe outside the lock — reads plain fields off the pipeline and
        # must not block registrations.
        return [self._describe_bundle(sid, b) for sid, b in snapshot]

    def get_source_status(self, source_id: str) -> dict[str, Any] | None:
        with self._registry_lock:
            bundle = self._bundles.get(source_id)
        if bundle is None:
            return None
        return self._describe_bundle(source_id, bundle)

    def _describe_bundle(self, source_id: str, bundle: SourceBundle) -> dict[str, Any]:
        pipe = bundle.pipeline
        ts = bundle.last_keepalive_at
        last_keepalive_iso = (
            datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            if ts is not None
            else None
        )
        return {
            "source_id": source_id,
            "source_url": pipe.source.source_url,
            "data_dir": bundle.data_dir,
            "status": pipe.status,
            "running": pipe.is_running,
            "recording_enabled": bundle.recorder is not None,
            "health": pipe.health_info,
            "keepalive_enabled": bool(bundle.keepalive and bundle.keepalive.enabled),
            "last_keepalive_at": last_keepalive_iso,
        }

    def _watchdog_loop(self) -> None:
        """Daemon: periodically auto-pause sources whose keepalive went stale."""
        while self._watchdog_running:
            try:
                self._watchdog_check_once()
            except Exception as e:
                logger.warning("[watchdog] tick error: %s", e)
            # Event.wait returns early if a new source registers — important
            # when a fresh source with a smaller check_interval needs the
            # daemon to start ticking faster than the previous interval.
            self._watchdog_wakeup.wait(timeout=self._watchdog_check_interval())
            self._watchdog_wakeup.clear()

    def _watchdog_check_interval(self) -> float:
        """Tightest configured interval across enabled sources, fall back to default."""
        intervals: list[float] = []
        with self._registry_lock:
            bundles = list(self._bundles.values())
        for b in bundles:
            cfg = b.keepalive
            if cfg and cfg.enabled:
                intervals.append(cfg.check_interval_seconds)
        if intervals:
            return max(0.1, min(intervals))
        return max(0.1, self.config.defaults.keepalive.check_interval_seconds)

    def _watchdog_check_once(self) -> None:
        now = time.time()
        # Iterate over a snapshot — dict can mutate during register/unregister.
        # `pause_source` is called WITHOUT any lock held here so it is free to
        # take `bundle.lock` itself.
        with self._registry_lock:
            snapshot = list(self._bundles.items())
        for source_id, bundle in snapshot:
            cfg = bundle.keepalive
            if cfg is None or not cfg.enabled:
                continue
            if bundle.last_keepalive_at is None:
                continue
            # Don't re-pause an already-paused source — keepalive only expresses
            # liveness, not resume intent.
            if bundle.pipeline.status == "paused":
                continue
            elapsed = now - bundle.last_keepalive_at
            if elapsed > cfg.timeout_seconds:
                logger.warning(
                    "[%s] keepalive timeout (%.1fs > %.0fs), auto-pausing",
                    source_id,
                    elapsed,
                    cfg.timeout_seconds,
                )
                try:
                    self.pause_source(source_id)
                except Exception as e:
                    logger.warning(
                        "[%s] watchdog pause failed: %s", source_id, e
                    )

    def stop_all(self):
        self._watchdog_running = False
        self._watchdog_wakeup.set()  # break daemon out of wait() promptly
        # Detach everything first, then tear down outside the registry lock so a
        # slow shutdown cannot deadlock a request that is mid-registration.
        with self._registry_lock:
            bundles = list(self._bundles.items())
            self._bundles.clear()
        for source_id, bundle in bundles:
            with bundle.lock:
                self._teardown_bundle(source_id, bundle)
        self._default_sink.close()
        logger.info("All sources stopped")

    @property
    def _pipelines(self) -> dict[str, StreamPipeline]:
        """Backwards-compat shim — some tests/refs still use _pipelines."""
        with self._registry_lock:
            return {sid: b.pipeline for sid, b in self._bundles.items()}
