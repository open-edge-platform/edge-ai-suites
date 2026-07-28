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
    merge_config,
)
from stream_monitor.rtsp_monitor import StreamPipeline
from stream_monitor.continuous_recorder import ContinuousRecorder
from sinks import EventSink, WebhookSink

logger = logging.getLogger(__name__)


@dataclass
class SourceBundle:
    """Per-source state: motion pipeline + optional continuous recorder + sink."""

    pipeline: StreamPipeline
    recorder: ContinuousRecorder | None
    sink: EventSink
    data_dir: str
    keepalive: KeepaliveConfig | None = None
    last_keepalive_at: float | None = None


class SourceManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self._default_sink: EventSink = WebhookSink(config.webhook)
        self._bundles: dict[str, SourceBundle] = {}
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

    def _resolve_data_dir(self, source: SourceConfig) -> str:
        if source.data_dir:
            return expand_path(source.data_dir)
        return os.path.join(expand_path(self.config.data_dir), source.source_id)

    def _build_sink(self, source: SourceConfig) -> EventSink:
        if source.webhook_url:
            return WebhookSink(WebhookConfig(url=source.webhook_url))
        return self._default_sink

    def register_source(self, source: SourceConfig) -> dict[str, Any]:
        """Register and start a new video source pipeline."""
        existing = self._bundles.get(source.source_id)
        if existing is not None:
            if existing.pipeline.is_running:
                return {"status": "already_running", "source_id": source.source_id}
            # Re-register: tear down old bundle so resources are released.
            self._teardown_bundle(source.source_id, existing)

        sink = self._build_sink(source)
        data_dir = self._resolve_data_dir(source)
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
        self._bundles[source.source_id] = bundle
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
                logger.warning("[%s] sink close error: %s", source_id, e)

    def unregister_source(self, source_id: str) -> dict[str, Any]:
        bundle = self._bundles.pop(source_id, None)
        if bundle is None:
            return {"status": "not_found", "source_id": source_id}
        self._teardown_bundle(source_id, bundle)
        logger.info("Unregistered source: %s", source_id)
        return {"status": "stopped", "source_id": source_id}

    def _handle_source_removed(self, source_id: str):
        """Callback: pipeline triggered 'remove' recovery strategy."""
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
        bundle = self._bundles.get(source_id)
        if bundle is None:
            return {"status": "not_found", "source_id": source_id}

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
                )
                bundle.recorder.start()

        logger.info("Pipeline config updated: %s", source_id)
        return {"status": "updated", "source_id": source_id}

    def pause_source(self, source_id: str) -> dict[str, Any]:
        bundle = self._bundles.get(source_id)
        if bundle is None:
            return {"status": "not_found", "source_id": source_id}
        if not bundle.pipeline.is_running:
            return {"status": "not_running", "source_id": source_id}
        bundle.pipeline.pause()
        if bundle.recorder is not None:
            bundle.recorder.pause()
        return {"status": "paused", "source_id": source_id}

    def resume_source(self, source_id: str) -> dict[str, Any]:
        bundle = self._bundles.get(source_id)
        if bundle is None:
            return {"status": "not_found", "source_id": source_id}
        if not bundle.pipeline.is_running:
            return {"status": "not_running", "source_id": source_id}
        bundle.pipeline.resume()
        if bundle.recorder is not None:
            bundle.recorder.resume()
        return {"status": "online", "source_id": source_id}

    def keepalive_source(self, source_id: str) -> dict[str, Any]:
        """Refresh `last_keepalive_at` for a source (Phase 8).

        Returns `{"status": "not_found"}` if the source isn't registered, else
        `{"status": "ok", "source_id": ..., "last_keepalive_at": <iso>}`.
        """
        bundle = self._bundles.get(source_id)
        if bundle is None:
            return {"status": "not_found", "source_id": source_id}
        now = time.time()
        bundle.last_keepalive_at = now
        return {
            "status": "ok",
            "source_id": source_id,
            "last_keepalive_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        }

    def get_sources(self) -> list[dict[str, Any]]:
        """List all registered sources with their status."""
        return [
            self._describe_bundle(sid, b) for sid, b in self._bundles.items()
        ]

    def get_source_status(self, source_id: str) -> dict[str, Any] | None:
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
        for b in list(self._bundles.values()):
            cfg = b.keepalive
            if cfg and cfg.enabled:
                intervals.append(cfg.check_interval_seconds)
        if intervals:
            return max(0.1, min(intervals))
        return max(0.1, self.config.defaults.keepalive.check_interval_seconds)

    def _watchdog_check_once(self) -> None:
        now = time.time()
        # Iterate over a snapshot — dict can mutate during register/unregister.
        for source_id, bundle in list(self._bundles.items()):
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
        for source_id, bundle in self._bundles.items():
            self._teardown_bundle(source_id, bundle)
        self._bundles.clear()
        self._default_sink.close()
        logger.info("All sources stopped")

    @property
    def _pipelines(self) -> dict[str, StreamPipeline]:
        """Backwards-compat shim — some tests/refs still use _pipelines."""
        return {sid: b.pipeline for sid, b in self._bundles.items()}
