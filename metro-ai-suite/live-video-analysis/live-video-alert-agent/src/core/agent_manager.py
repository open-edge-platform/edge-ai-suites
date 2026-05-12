# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
AgentManager — central orchestrator for multi-camera alert processing.

Key improvements
----------------
- Concurrent stream analysis: all streams are analysed in parallel via
  asyncio.gather(), so cycle time = max(VLM latency) not sum(VLM latency).
- Per-stream independent analysis loops 
- AlertStateManager integration: deduplication, escalation.
- AlertActionAgent integration: Google ADK tool-calling (or rule-based fallback).
- Snapshot tool callback registration per stream.
- Proper AlertConfig (Pydantic) instead of raw dicts for alert configuration.
- Runtime metrics: per-stream analysis counters and inference latency.
- Graceful shutdown: cancels all per-stream tasks cleanly.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import ValidationError

from .stream_manager import LiveStreamManager
from .vlm_client import VLMClient
from .event_manager import EventManager
from .alert_state_manager import AlertStateManager
from src.agentic.alert_agent import AlertActionAgent
from src.agentic.tools.snapshot_tool import (
    register_frame_callback, unregister_frame_callback, capture_snapshot,
)
from src.schemas.monitor import AgentResult, AlertConfig
from src.config import settings

logger = logging.getLogger(__name__)

_RESOURCES = Path("resources")
_MAX_FRAME_AGE = 10.0  # seconds — skip analysis if newest frame is older than this


def _safe_broadcast(coro):
    """Fire-and-forget an async broadcast, logging any errors."""
    task = asyncio.create_task(coro)
    task.add_done_callback(_log_broadcast_error)


def _log_broadcast_error(task: asyncio.Task):
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error(f"Broadcast error: {exc}")


def _atomic_write_json(path: str | Path, data: object) -> None:
    """Write *data* as JSON to *path* atomically (write-tmp-then-rename).

    Prevents a corrupt file if the process is killed mid-write.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class StreamMetrics:
    """Runtime counters for a single stream."""
    __slots__ = ("analysis_count", "alert_count", "last_inference_ms")

    def __init__(self):
        self.analysis_count: int = 0
        self.alert_count: int = 0
        self.last_inference_ms: Optional[float] = None


class StreamPipeline:
    """Per-stream analysis pipeline that processes alerts in VLM-safe batches.

    When a stream monitors many alerts, packing them all into a single VLM
    call can exceed the model's token limit.  This pipeline splits alerts
    into batches of ``max_per_call``, runs them concurrently (bounded by the
    shared semaphore), and merges the results.

    Created via :meth:`AgentManager._create_pipeline` (factory method).
    """

    __slots__ = (
        "stream_id", "_vlm_client", "_vlm_semaphore",
        "_build_prompt", "_parse_response", "_max_per_call",
    )

    def __init__(
        self,
        stream_id: str,
        vlm_client: "VLMClient",
        vlm_semaphore: asyncio.Semaphore,
        build_prompt_fn,
        parse_response_fn,
        max_per_call: int,
    ):
        self.stream_id = stream_id
        self._vlm_client = vlm_client
        self._vlm_semaphore = vlm_semaphore
        self._build_prompt = build_prompt_fn
        self._parse_response = parse_response_fn
        self._max_per_call = max(1, max_per_call)

    async def analyse(
        self, frames: list, enabled: List[AlertConfig],
    ) -> Optional[dict]:
        """Run VLM inference for *enabled* alerts, batching to stay under token limits.

        Returns merged {alert_name: {answer, reason}} dict, or None if every
        batch failed.
        """
        if len(enabled) <= self._max_per_call:
            return await self._run_batch(frames, enabled)

        batches = [
            enabled[i : i + self._max_per_call]
            for i in range(0, len(enabled), self._max_per_call)
        ]
        tasks = [self._run_batch(frames, batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: dict = {}
        for batch, result in zip(batches, batch_results):
            if isinstance(result, Exception):
                names = [a.name for a in batch]
                logger.error(
                    f"[{self.stream_id}] Batch {names} failed: {result}"
                )
                continue
            if result:
                merged.update(result)

        return merged or None

    async def _run_batch(
        self, frames: list, alerts: List[AlertConfig],
    ) -> Optional[dict]:
        """Single VLM call for one batch of alerts."""
        prompt = self._build_prompt(alerts)
        async with self._vlm_semaphore:
            response = await self._vlm_client.analyze_stream_segment(
                frames,
                system_prompt="You are a precise video analytics AI. Always respond with valid JSON.",
                user_prompt=prompt,
            )
        if not response:
            return None
        return self._parse_response(response, alerts)


class AgentManager:
    """
    Manages all camera streams, VLM inference, alert state, and action dispatch.

    One AgentManager instance handles N camera streams concurrently.
    Each stream gets its own asyncio Task running an independent analysis loop.
    """

    def __init__(
        self,
        vlm_url: str,
        model_name: str,
        streams_config: str = str(_RESOURCES / "streams.json"),
        alerts_config: str = str(_RESOURCES / "alerts.json"),
    ):
        self._streams_config_file = streams_config
        self._alerts_config_file = alerts_config

        self.streams: Dict[str, LiveStreamManager] = {}

        self.vlm_client = VLMClient(
            base_url=vlm_url,
            model_name=model_name,
        )

        self._vlm_semaphore = asyncio.Semaphore(settings.VLM_MAX_CONCURRENCY)
        self.events = EventManager()
        self.alert_state = AlertStateManager()
        self.action_agent = AlertActionAgent()
        self._worker_agents: List[AlertActionAgent] = []
        self.latest_results: Dict[str, Dict] = {}
        self._metrics: Dict[str, StreamMetrics] = {}
        self._stream_tasks: Dict[str, asyncio.Task] = {}
        self._action_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._action_workers: List[asyncio.Task] = []
        self._dropped_actions: int = 0
        self.stream_tools: Dict[str, List[str]] = {}
        self.stream_alerts: Dict[str, List[str]] = {}
        self.stream_names: Dict[str, str] = {}
        self._pipelines: Dict[str, StreamPipeline] = {}
        self._stop_event: asyncio.Event = asyncio.Event()
        self._alerts_changed: asyncio.Event = asyncio.Event()

        self.running = False
        self._start_time: Optional[float] = None

        self.alerts: List[AlertConfig] = self._load_alerts_config()
        self._load_streams_config()

    async def start(self):
        """Start all registered stream managers and their analysis loops."""
        self.running = True
        self._stop_event.clear()
        self._start_time = time.monotonic()

        for stream_id, mgr in self.streams.items():
            mgr.start()
            self._launch_stream_task(stream_id)

        num_workers = max(settings.ACTION_WORKERS, len(self.streams))
        self._worker_agents = [AlertActionAgent() for _ in range(num_workers)]

        for i in range(num_workers):
            t = asyncio.create_task(
                self._action_worker(i), name=f"action-worker-{i}",
            )
            self._action_workers.append(t)

        logger.info(
            f"AgentManager started — {len(self.streams)} stream(s), "
            f"{len(self.alerts)} alert(s), "
            f"{num_workers} action worker(s), "
            f"ADK={'on' if settings.USE_ADK else 'off'}"
        )

        while self.running:
            await asyncio.sleep(5)

    def stop(self):
        """Signal all loops to stop and cancel their tasks."""
        self.running = False
        self._stop_event.set()  # wake any workers blocked on queue.get()
        for task in self._stream_tasks.values():
            task.cancel()
        for task in self._action_workers:
            task.cancel()
        self._action_workers.clear()
        for mgr in self.streams.values():
            mgr.stop()
        logger.info("AgentManager stopped")

    def reload_action_agent(self):
        """Rebuild the action agent so runtime tool registry changes take effect."""
        self.action_agent = AlertActionAgent()
        self._worker_agents = [AlertActionAgent() for _ in range(len(self._worker_agents))]
        logger.info("Action agent reloaded")

    @property
    def uptime_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.monotonic() - self._start_time

    def add_stream(self, stream_id: str, rtsp_url: str, name: str = "", tools: Optional[List[str]] = None, alerts: Optional[List[str]] = None, save: bool = True):
        if stream_id in self.streams:
            logger.warning(f"Stream '{stream_id}' already registered — ignoring")
            return

        if len(self.streams) >= settings.MAX_STREAMS:
            raise ValueError(
                f"Maximum number of streams ({settings.MAX_STREAMS}) reached. "
                f"Remove a stream before adding a new one."
            )

        mgr = LiveStreamManager(rtsp_url)
        self.streams[stream_id] = mgr
        self.latest_results[stream_id] = {}
        self._metrics[stream_id] = StreamMetrics()
        self.alert_state.register_stream(stream_id)
        self.stream_tools[stream_id] = tools or []
        self.stream_alerts[stream_id] = alerts or []
        self.stream_names[stream_id] = name or stream_id

        register_frame_callback(
            stream_id,
            lambda sid: self._get_latest_frame(sid),
        )

        if self.running:
            mgr.start()
            self._launch_stream_task(stream_id)

        if save:
            self._save_streams_config()

        logger.info(f"Stream added: {stream_id} → {rtsp_url}")

    def remove_stream(self, stream_id: str):
        task = self._stream_tasks.pop(stream_id, None)
        if task and not task.done():
            task.cancel()

        self.streams[stream_id].stop()
        del self.streams[stream_id]
        self.latest_results.pop(stream_id, None)
        self._metrics.pop(stream_id, None)
        self._pipelines.pop(stream_id, None)
        self.alert_state.unregister_stream(stream_id)
        self.stream_tools.pop(stream_id, None)
        self.stream_alerts.pop(stream_id, None)
        self.stream_names.pop(stream_id, None)
        unregister_frame_callback(stream_id)
        self._save_streams_config()
        logger.info(f"Stream removed: {stream_id}")

    def get_latest_frame(self, stream_id: str):
        return self._get_latest_frame(stream_id)

    def _get_latest_frame(self, stream_id: str):
        mgr = self.streams.get(stream_id)
        if mgr is None:
            return None
        frames = mgr.get_recent_frames(count=1)
        return frames[0] if frames else None

    def get_alerts_config(self) -> List[dict]:
        return [a.model_dump() for a in self.alerts]

    def _create_pipeline(self, stream_id: str) -> StreamPipeline:
        """Factory method — create an isolated analysis pipeline for one stream."""
        return StreamPipeline(
            stream_id=stream_id,
            vlm_client=self.vlm_client,
            vlm_semaphore=self._vlm_semaphore,
            build_prompt_fn=self._build_vlm_prompt,
            parse_response_fn=self._parse_vlm_response,
            max_per_call=settings.VLM_ALERTS_PER_CALL,
        )

    def update_stream_alerts(self, stream_id: str, alerts: List[str]) -> None:
        """Set the alert filter for a stream and persist it."""
        if stream_id not in self.streams:
            raise KeyError(f"Stream '{stream_id}' not found")
        self.stream_alerts[stream_id] = alerts
        self._save_streams_config()
        logger.info(f"Stream '{stream_id}' alert filter updated: {alerts or 'all'}")

    def save_alerts_config(self, config_data: List[dict]) -> None:
        """Validate, apply, and persist new alert configurations."""
        new_alerts: List[AlertConfig] = []
        for entry in config_data:
            try:
                new_alerts.append(AlertConfig(**entry))
            except ValidationError as exc:
                raise ValueError(f"Invalid alert config: {exc}") from exc

        # Identify which alert names actually changed (prompt, tools, escalation, enabled).
        old_by_name = {a.name: a for a in self.alerts}
        changed_alert_names: set = set()
        for new in new_alerts:
            old = old_by_name.get(new.name)
            if old is None or old.prompt != new.prompt or old.tools != new.tools or old.enabled != new.enabled or old.escalation != new.escalation:
                changed_alert_names.add(new.name)
        # Also treat deleted alerts as changed so their queued jobs are dropped
        new_names = {a.name for a in new_alerts}
        changed_alert_names |= {n for n in old_by_name if n not in new_names}

        self.alerts = new_alerts

        # Reset alert state only for changed alerts so unchanged streams are not disrupted.
        for alert_name in changed_alert_names:
            self.alert_state.reset_alert(alert_name)
        self.latest_results.clear()
        self._pipelines.clear()  # force pipeline recreation with new alerts

        # Wake all analysis loops so they immediately run with updated prompts
        self._alerts_changed.set()

        # Drain stale action-queue jobs that belong to changed alerts.
        if changed_alert_names:
            kept: list = []
            drained = 0
            while True:
                try:
                    job = self._action_queue.get_nowait()
                    self._action_queue.task_done()
                    if job["alert_cfg"].name in changed_alert_names:
                        drained += 1
                    else:
                        kept.append(job)
                except asyncio.QueueEmpty:
                    break
            for job in kept:
                try:
                    self._action_queue.put_nowait(job)
                except asyncio.QueueFull:
                    pass  # if somehow full, drop the overflow
            if drained:
                logger.info(
                    f"Drained {drained} stale action job(s) for changed alerts: "
                    f"{changed_alert_names}"
                )

            # Clear ADK sessions for any stream that had stale jobs drained,
            # plus all streams that are currently active (they will have new
            # detections from the updated prompt on the next cycle).
            affected_streams = set(self.streams.keys())
            for agent in [self.action_agent, *self._worker_agents]:
                agent.clear_sessions_for_streams(affected_streams)

        try:
            _RESOURCES.mkdir(parents=True, exist_ok=True)
            _atomic_write_json(self._alerts_config_file, [a.model_dump() for a in self.alerts])
            logger.info(f"Saved {len(self.alerts)} alert config(s)")
        except Exception as exc:
            logger.error(f"Failed to persist alert config: {exc}")

    def get_stream_metrics(self) -> List[dict]:
        results = []
        for sid, m in self._metrics.items():
            results.append({
                "stream_id": sid,
                "analysis_count": m.analysis_count,
                "alert_count": m.alert_count,
                "last_inference_ms": m.last_inference_ms,
            })
        return results

    async def subscribe(self) -> asyncio.Queue:
        return await self.events.subscribe()

    async def unsubscribe(self, queue: asyncio.Queue):
        await self.events.unsubscribe(queue)

    def _launch_stream_task(self, stream_id: str):
        """Create and track an independent asyncio Task for one stream."""
        if stream_id in self._stream_tasks:
            existing = self._stream_tasks[stream_id]
            if not existing.done():
                return  # already running

        task = asyncio.create_task(
            self._stream_analysis_loop(stream_id),
            name=f"analysis-{stream_id}",
        )
        task.add_done_callback(
            lambda t: self._on_task_done(stream_id, t)
        )
        self._stream_tasks[stream_id] = task

    def _on_task_done(self, stream_id: str, task: asyncio.Task):
        """Restart crashed analysis tasks while the manager is still running."""
        if task.cancelled():
            return
        if self._stream_tasks.get(stream_id) is not task:
            return  # stream was removed or task was replaced
        exc = task.exception()
        if exc:
            logger.error(f"Analysis task for '{stream_id}' crashed: {exc}")
            if self.running and stream_id in self.streams:
                logger.info(f"Restarting analysis task for '{stream_id}'")
                self._launch_stream_task(stream_id)

    async def _stream_analysis_loop(self, stream_id: str):
        """
        Independent analysis loop for a single stream.

        Runs at ANALYSIS_INTERVAL cadence.  Because each stream has its own
        task, streams are analysed concurrently — one slow VLM call does not
        delay other streams.
        """
        logger.info(f"Analysis loop started for stream '{stream_id}'")

        await asyncio.sleep(0.5)  # let stream buffer pre-fill

        while self.running and stream_id in self.streams:
            t_start = time.monotonic()
            self._alerts_changed.clear()
            await self._analyse_one_stream(stream_id)

            elapsed = time.monotonic() - t_start
            interval = settings.ANALYSIS_INTERVAL
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                # Wake immediately if alerts are updated during the sleep
                try:
                    await asyncio.wait_for(
                        self._alerts_changed.wait(), timeout=sleep_time
                    )
                    logger.debug(f"[{stream_id}] Alert config changed — skipping sleep")
                except asyncio.TimeoutError:
                    pass

        logger.info(f"Analysis loop exited for stream '{stream_id}'")

    async def _analyse_one_stream(self, stream_id: str):
        """Run one VLM inference cycle for a single stream."""
        mgr = self.streams.get(stream_id)
        if not mgr:
            return

        # Check frame freshness before committing to VLM inference
        health = mgr.get_health()
        if health.last_frame_ts is not None:
            frame_age = time.monotonic() - health.last_frame_ts
            if frame_age > _MAX_FRAME_AGE:
                logger.warning(
                    f"[{stream_id}] Skipping analysis — frame is {frame_age:.1f}s old"
                )
                return

        frames = mgr.get_recent_frames(count=1)
        if not frames:
            return

        frame_ref = frames[0]
        frame_captured_ts = health.last_frame_ts  # monotonic timestamp of capture

        enabled = [a for a in self.alerts if a.enabled]
        if not enabled:
            return

        stream_alert_filter = self.stream_alerts.get(stream_id)
        if stream_alert_filter:
            enabled = [a for a in enabled if a.name in stream_alert_filter]
        if not enabled:
            return

        # Get or create the per-stream pipeline (factory pattern)
        pipeline = self._pipelines.get(stream_id)
        if pipeline is None:
            pipeline = self._create_pipeline(stream_id)
            self._pipelines[stream_id] = pipeline

        logger.info(
            f"[{stream_id}] Inference cycle — frames={len(frames)} "
            f"alerts={[a.name for a in enabled]}"
        )

        parsed = await pipeline.analyse(frames, enabled)

        metrics = self._metrics.get(stream_id)
        if metrics:
            metrics.analysis_count += 1
            metrics.last_inference_ms = self.vlm_client.last_inference_ms

        if not parsed:
            return

        logger.info(f"[{stream_id}] VLM results: {list(parsed.keys())}")

        self.latest_results[stream_id] = parsed
        _safe_broadcast(self.events.broadcast("analysis", {
            "stream_id": stream_id,
            "stream_name": self.stream_names.get(stream_id, stream_id),
            "results": parsed,
            "inference_ms": self.vlm_client.last_inference_ms,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }))
        await self._process_alerts(stream_id, enabled, parsed, frame_ref, frame_captured_ts)

    async def _process_alerts(
        self,
        stream_id: str,
        enabled: List[AlertConfig],
        parsed: dict,
        frame_ref=None,
        frame_captured_ts: Optional[float] = None,
    ):
        """
        For each triggered alert: check escalation, then enqueue
        action dispatch to the background worker pool (non-blocking).
        """
        pinned_frame = None  # lazily copied only when a snapshot is needed

        for alert_cfg in enabled:
            result = parsed.get(alert_cfg.name)
            if not result:
                continue

            answer = result.get("answer", "NO")
            reason = result.get("reason", "")

            should_act, is_escalation, is_transition = self.alert_state.process(
                stream_id=stream_id,
                alert_cfg=alert_cfg,
                answer=answer,
                reason=reason,
            )

            consecutive_count = self.alert_state.get_consecutive_count(
                stream_id, alert_cfg.name
            )

            if answer == "YES":
                metrics = self._metrics.get(stream_id)
                if metrics and is_transition:
                    metrics.alert_count += 1

                logger.warning(
                    f"ALERT YES | stream={stream_id} | alert={alert_cfg.name} | "
                    f"act={should_act} | escalated={is_escalation}"
                )

            # Broadcast alert_cleared when the alert transitions from YES to NO
            if answer == "NO" and is_transition:
                _safe_broadcast(self.events.broadcast("alert_cleared", {
                    "stream_id": stream_id,
                    "stream_name": self.stream_names.get(stream_id, stream_id),
                    "alert_name": alert_cfg.name,
                    "reason": reason,
                    "consecutive_no": self.alert_state.get_consecutive_no(
                        stream_id, alert_cfg.name
                    ),
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                }))

            if not should_act:
                continue

            # Broadcast alert_fired immediately so the UI is notified
            # before any tool execution or action dispatch begins.
            if answer == "YES":
                frame_age_ms = None
                if frame_captured_ts is not None:
                    frame_age_ms = round((time.monotonic() - frame_captured_ts) * 1000)

                _safe_broadcast(self.events.broadcast("alert_fired", {
                    "stream_id": stream_id,
                    "stream_name": self.stream_names.get(stream_id, stream_id),
                    "alert_name": alert_cfg.name,
                    "answer": answer,
                    "reason": reason,
                    "escalated": is_escalation,
                    "consecutive_count": consecutive_count,
                    "is_transition": is_transition,
                    "frame_age_ms": frame_age_ms,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                }))

            stream_tools = self.stream_tools.get(stream_id) or []
            effective_tools = list(alert_cfg.tools)
            for t in stream_tools:
                if t not in effective_tools:
                    effective_tools.append(t)
            if "log_alert" not in effective_tools:
                effective_tools.insert(0, "log_alert")

            # Copy the frame only once, only when a snapshot tool is needed
            wants_snapshot = "capture_snapshot" in effective_tools or (
                is_escalation
                and alert_cfg.escalation
                and "capture_snapshot" in alert_cfg.escalation.additional_tools
            )
            if wants_snapshot and pinned_frame is None and frame_ref is not None:
                pinned_frame = frame_ref.copy()

            job = {
                "stream_id": stream_id,
                "alert_cfg": alert_cfg,
                "effective_tools": effective_tools,
                "answer": answer,
                "reason": reason,
                "consecutive_count": consecutive_count,
                "escalated": is_escalation,
                "is_transition": is_transition,
                "frame_age_ms": (
                    round((time.monotonic() - frame_captured_ts) * 1000)
                    if frame_captured_ts is not None else None
                ),
                "pinned_frame": pinned_frame if wants_snapshot else None,
            }
            try:
                self._action_queue.put_nowait(job)
            except asyncio.QueueFull:
                self._dropped_actions += 1
                logger.warning(
                    f"Action queue full — dropping action for "
                    f"[{stream_id}][{alert_cfg.name}] "
                    f"(total dropped: {self._dropped_actions})"
                )
                continue

    async def _action_worker(self, worker_id: int):
        """Background worker that processes alert action jobs."""
        agent = (
            self._worker_agents[worker_id]
            if worker_id < len(self._worker_agents)
            else self.action_agent
        )
        logger.info(f"Action worker {worker_id} started")

        while True:
            # Race: get next job OR receive shutdown signal
            get_task = asyncio.ensure_future(self._action_queue.get())
            stop_task = asyncio.ensure_future(self._stop_event.wait())
            try:
                done, pending = await asyncio.wait(
                    [get_task, stop_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
            except asyncio.CancelledError:
                get_task.cancel()
                stop_task.cancel()
                break

            # Clean up the losing future
            for t in pending:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

            if stop_task in done:
                # Shutdown signal received; if a job arrived simultaneously, discard it
                if get_task in done:
                    self._action_queue.task_done()
                break

            job = get_task.result()
            try:
                await self._execute_action_job(job, agent)
            except Exception as exc:
                logger.error(f"Action worker {worker_id} error: {exc}")
            finally:
                self._action_queue.task_done()

        logger.info(f"Action worker {worker_id} stopped")

    async def _execute_action_job(self, job: dict, agent: AlertActionAgent):
        """Execute snapshot + tool dispatch for one alert.

        Uses the pinned frame (captured at analysis time) for snapshots so
        the saved image matches the exact frame the VLM analysed.
        """
        stream_id = job["stream_id"]
        if stream_id not in self.streams:
            logger.debug(f"Skipping action for removed stream '{stream_id}'")
            return
        alert_cfg = job["alert_cfg"]
        effective_tools = job["effective_tools"]
        answer = job["answer"]
        reason = job["reason"]
        consecutive_count = job["consecutive_count"]
        escalated = job["escalated"]
        pinned_frame = job.get("pinned_frame")

        snapshot_path: Optional[str] = None
        wants_snapshot = "capture_snapshot" in effective_tools or (
            escalated
            and alert_cfg.escalation
            and "capture_snapshot" in alert_cfg.escalation.additional_tools
        )
        if wants_snapshot:
            try:
                if pinned_frame is not None:
                    snap_result = await capture_snapshot(
                        stream_id=stream_id,
                        alert_name=alert_cfg.name,
                        frame=pinned_frame,
                    )
                else:
                    snap_result = await capture_snapshot(
                        stream_id=stream_id,
                        alert_name=alert_cfg.name,
                    )
                snapshot_path = snap_result.get("path")
            except Exception as snap_exc:
                logger.error(
                    f"Snapshot capture failed for '{stream_id}': {snap_exc}"
                )

        dispatch_cfg = copy.copy(alert_cfg)
        dispatch_cfg.tools = [t for t in effective_tools if t != "capture_snapshot"]

        actions_taken = await agent.dispatch(
            stream_id=stream_id,
            alert_cfg=dispatch_cfg,
            answer=answer,
            reason=reason,
            consecutive_count=consecutive_count,
            escalated=escalated,
            snapshot_path=snapshot_path,
        )

        if snapshot_path and "capture_snapshot" not in actions_taken:
            actions_taken = ["capture_snapshot"] + actions_taken

        if answer == "YES":
            await self.events.broadcast("alert_action", {
                "stream_id": stream_id,
                "stream_name": self.stream_names.get(stream_id, stream_id),
                "alert_name": alert_cfg.name,
                "answer": answer,
                "reason": reason,
                "actions_taken": actions_taken,
                "effective_tools": job.get("effective_tools", []),
                "consecutive_count": job.get("consecutive_count", 0),
                "is_transition": job.get("is_transition", False),
                "escalated": escalated,
                "frame_age_ms": job.get("frame_age_ms"),
                "snapshot_path": snapshot_path,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            })

    def _build_vlm_prompt(self, enabled: List[AlertConfig]) -> str:
        """Build a compact multi-question JSON prompt for all enabled alerts."""
        questions = {a.name: a.prompt for a in enabled}
        return (
            "Answer each question about this image with YES or NO "
            "and a brief reason.\n"
            f"{json.dumps(questions)}\n"
            "Reply ONLY with valid JSON (no markdown). "
            "Each answer MUST be an object with \"answer\" and \"reason\" keys.\n"
            "Example: {\"Fire Detection\": {\"answer\": \"NO\", \"reason\": \"no flames or smoke visible\"}}\n"
            "Response:\n"
            "{" + ", ".join(
                f'"{a.name}": {{"answer": "YES or NO", "reason": "brief explanation"}}'
                for a in enabled
            ) + "}"
        )

    def _parse_vlm_response(
        self, response: str, enabled: List[AlertConfig]
    ) -> Optional[dict]:
        """
        Clean, extract, and Pydantic-validate the VLM JSON response.
        Returns None if parsing fails entirely.
        """
        try:
            clean = response.replace("```json", "").replace("```", "").strip()
            start = clean.find("{")
            end = clean.rfind("}")
            if start == -1 or end == -1:
                logger.error(f"No JSON object found in VLM response: {response[:200]}")
                return None

            data = json.loads(clean[start:end + 1])

            validated: dict = {}
            for alert_cfg in enabled:
                raw = data.get(alert_cfg.name)
                if raw is None:
                    logger.warning(f"VLM omitted answer for alert '{alert_cfg.name}'")
                    validated[alert_cfg.name] = {"answer": "NO", "reason": "No response from VLM"}
                    continue
                try:
                    if isinstance(raw.get("answer"), str):
                        raw["answer"] = raw["answer"].strip().upper()
                    result = AgentResult(**raw)
                    validated[alert_cfg.name] = result.model_dump()
                except ValidationError as exc:
                    logger.warning(f"Validation failed for '{alert_cfg.name}': {exc} | raw={raw}")
                    validated[alert_cfg.name] = {"answer": "NO", "reason": "Validation error"}

            return validated

        except json.JSONDecodeError as exc:
            logger.error(f"JSON decode error: {exc} | response={response[:300]}")
            return None
        except Exception as exc:
            logger.error(f"Unexpected parse error: {exc}")
            return None

    def _load_alerts_config(self) -> List[AlertConfig]:
        """Load alert configurations from JSON; return defaults on failure.

        Supports migration from the legacy ``agents.json`` filename: if the
        new ``alerts.json`` does not exist but ``agents.json`` does, the old
        file is loaded and then persisted under the new name.
        """
        path = self._alerts_config_file

        # Migration: fall back to legacy agents.json if alerts.json is missing
        legacy_path = Path(path).parent / "agents.json"
        if not os.path.exists(path) and os.path.exists(legacy_path):
            logger.info(
                f"Migrating legacy config {legacy_path} → {path}"
            )
            path = str(legacy_path)

        if os.path.exists(path):
            try:
                with open(path) as fh:
                    raw = json.load(fh)
                configs = []
                for entry in raw:
                    try:
                        configs.append(AlertConfig(**entry))
                    except ValidationError as exc:
                        logger.warning(f"Skipping invalid alert config entry: {exc}")
                if configs:
                    logger.info(f"Loaded {len(configs)} alert(s) from {path}")
                    # Persist under the canonical name so migration is one-time
                    if path != self._alerts_config_file:
                        try:
                            _atomic_write_json(
                                self._alerts_config_file,
                                [a.model_dump() for a in configs],
                            )
                            logger.info(
                                f"Persisted migrated config to {self._alerts_config_file}"
                            )
                        except Exception as exc:
                            logger.warning(f"Could not persist migrated config: {exc}")
                    return configs
            except Exception as exc:
                logger.error(f"Failed to load alert config: {exc}")

        logger.info("Using default alert configurations")
        return [
            AlertConfig(
                name="Fire Detection",
                prompt="Is there visible fire or smoke in the image?",
                enabled=True,
                tools=["log_alert", "capture_snapshot"],
            ),
            AlertConfig(
                name="Person Detection",
                prompt="Is there a person present in the frame?",
                enabled=True,
                tools=["log_alert"],
            ),
        ]

    def augment_alerts_with_mcp_tools(self):
        """Append newly-discovered MCP tools to every alert's tools list.

        Called after MCP servers are connected so that existing/persisted
        alert configs automatically gain access to MCP tools without
        manual editing.
        """
        from src.agentic.alert_agent import get_all_tools as _get_all_tools

        all_tools, _ = _get_all_tools()
        mcp_tool_names = [n for n in all_tools if n.startswith("mcp_")]
        if not mcp_tool_names:
            return

        changed = False
        for alert_cfg in self.alerts:
            existing = set(alert_cfg.tools)
            new_tools = [t for t in mcp_tool_names if t not in existing]
            if new_tools:
                alert_cfg.tools.extend(new_tools)
                changed = True
                logger.info(
                    f"Alert '{alert_cfg.name}': added MCP tools {new_tools}"
                )

        if changed:
            self.save_alerts_config(
                [a.model_dump() for a in self.alerts]
            )

    def _load_streams_config(self):
        path = self._streams_config_file
        if os.path.exists(path):
            try:
                with open(path) as fh:
                    streams = json.load(fh)
                if len(streams) > settings.MAX_STREAMS:
                    logger.warning(
                        f"Stream config has {len(streams)} streams but MAX_STREAMS={settings.MAX_STREAMS} "
                        f"— loading only the first {settings.MAX_STREAMS}"
                    )
                    streams = streams[:settings.MAX_STREAMS]
                for s in streams:
                    self.add_stream(
                        s["id"], s["url"],
                        name=s.get("name", ""),
                        tools=s.get("tools", []),
                        alerts=s.get("alerts", []),
                        save=False,
                    )
                logger.info(f"Loaded {len(streams)} stream(s) from {path}")
            except Exception as exc:
                logger.error(f"Failed to load stream config: {exc}")

    def _save_streams_config(self):
        try:
            _RESOURCES.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "id": sid,
                    "name": self.stream_names.get(sid, sid),
                    "url": m.rtsp_url,
                    "tools": self.stream_tools.get(sid, []),
                    "alerts": self.stream_alerts.get(sid, []),
                }
                for sid, m in self.streams.items()
            ]
            _atomic_write_json(self._streams_config_file, data)
        except Exception as exc:
            logger.error(f"Failed to save stream config: {exc}")
