# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Live Video Captioning Analytics App shim.

Integrates the Intel Live Video Captioning application as a VMS analytics app.

Data flow:
  Camera RTSP ──► LVC stack (DLStreamer + gvagenai VLM)
                  ├─► captions via MQTT → SSE  → dashboard
                  └─► annotated video  → MediaMTX WebRTC → dashboard

Architecture
────────────
``LiveCaptioningAnalyticsAppShim`` is composed of two single-responsibility helpers:

* :class:`~.api_client.LvcApiClient`  — all HTTP calls to the LVC backend
* :class:`~.schema.LvcSchemaManager`  — OpenAPI fetch, $ref resolution, UI
  annotations, and Pydantic model building

This shim wires them together and implements :class:`~plugin.base.interfaces.IAnalyticsAppShim`
so the generic ``/v1/analytics-apps/{app_id}/…`` routes work without any LVC-specific code.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

import structlog
from pydantic import BaseModel

from plugin.core.models.domain import AnalysisResult, MetadataEvent
from plugin.base.interfaces import IAnalyticsAppShim
from .config import LiveCaptioningAnalyticsAppConfig
from .api_client import LvcApiClient
from .schema import LvcSchemaManager
from .mqtt_subscriber import LvcMqttSubscriber

if TYPE_CHECKING:
    from plugin.core.factory import VmsShimSet
    from plugin.core.pipeline.orchestrator import Orchestrator

logger = structlog.get_logger(__name__)


class LiveCaptioningAnalyticsAppShim(IAnalyticsAppShim):
    """IAnalyticsAppShim implementation for the Live Video Captioning app."""

    app_id = "live_captioning"
    display_name = "Live Video Captioning"

    def __init__(self, config: LiveCaptioningAnalyticsAppConfig) -> None:
        self._config = config
        self._api = LvcApiClient(base_url=config.base_url)
        self._schema_mgr = LvcSchemaManager()
        self._mqtt_subscriber: Optional[LvcMqttSubscriber] = None
        # run_id → camera_id mapping for Nx Witness write-back
        self._run_camera_map: dict[str, str] = {}
        self._vms_shim_sets: list[VmsShimSet] = []

    def set_vms_shims(self, vms_shim_sets: list[VmsShimSet]) -> None:
        """Inject VMS shim sets so LVC captions can be pushed to Nx Witness."""
        self._vms_shim_sets = vms_shim_sets

    def register_run(self, run_id: str, camera_id: str) -> None:
        """Record which camera a run belongs to for Nx Witness write-back."""
        self._run_camera_map[run_id] = camera_id
        logger.info("lvc_run_registered", run_id=run_id, camera_id=camera_id)

    def unregister_run(self, run_id: str) -> None:
        """Remove the run→camera mapping when a run stops."""
        self._run_camera_map.pop(run_id, None)

    # ── MQTT subscriber wiring (set by orchestrator) ──────────────────────────

    def set_subscriber(self, subscriber: LvcMqttSubscriber) -> None:
        """Inject the aiomqtt subscriber started by the orchestrator."""
        self._mqtt_subscriber = subscriber

    async def on_startup(self, orchestrator: Orchestrator) -> None:
        """Start LVC MQTT subscriber background task."""
        if not orchestrator.config.mqtt.host:
            logger.info("lvc_mqtt_not_configured_skipping", app_id=self.app_id)
            return
        subscriber = LvcMqttSubscriber()
        self.set_subscriber(subscriber)

        # Wire Nx Witness write-back if any VMS shims support bookmarks.
        if self._vms_shim_sets:
            subscriber.set_nx_write_back(self._push_caption_to_nx)

        task = asyncio.create_task(
            subscriber.run(
                mqtt_host=orchestrator.config.mqtt.host,
                mqtt_port=orchestrator.config.mqtt.port,
            ),
            name=f"lvc-mqtt-subscriber-{self.app_id}",
        )
        orchestrator.add_background_task(task)
        logger.info(
            "lvc_mqtt_subscriber_task_started",
            app_id=self.app_id,
            mqtt_host=orchestrator.config.mqtt.host,
            mqtt_port=orchestrator.config.mqtt.port,
        )

    async def _push_caption_to_nx(self, run_id: str, caption: str) -> None:
        """Push an LVC caption as a bookmark to the Nx Witness camera timeline."""
        camera_id = self._run_camera_map.get(run_id)
        if not camera_id:
            return

        for ss in self._vms_shim_sets:
            if not camera_id.startswith(ss.vms_shim.camera_id_prefix):
                continue
            if not hasattr(ss.vms_shim, "set_bookmark"):
                continue
            try:
                await ss.vms_shim.set_bookmark(camera_id, datetime.now(tz=timezone.utc), caption[:500])
                logger.info(
                    "lvc_caption_bookmark_pushed",
                    camera_id=camera_id,
                    run_id=run_id,
                    caption_len=len(caption),
                )
            except Exception as exc:
                logger.warning(
                    "lvc_caption_bookmark_failed",
                    camera_id=camera_id,
                    run_id=run_id,
                    error=str(exc),
                )
            return

    def subscribe_run(self, run_id: str) -> asyncio.Queue | None:
        """Return a per-run result queue, or None if MQTT is not connected."""
        if self._mqtt_subscriber is None:
            return None
        return self._mqtt_subscriber.subscribe_run(run_id)

    def release_run(self, run_id: str) -> None:
        """Release the per-run queue when the SSE client disconnects."""
        if self._mqtt_subscriber is not None:
            self._mqtt_subscriber.release_run(run_id)

    def get_broadcast_queue(self) -> asyncio.Queue | None:
        """Return the broadcast queue (all runs), or None if not connected."""
        if self._mqtt_subscriber is None:
            return None
        return self._mqtt_subscriber.broadcast_queue()

    # ── IAnalyticsAppShim — schema ─────────────────────────────────────────────────

    @property
    def param_model(self) -> type[BaseModel]:
        """Return the live dynamic Pydantic model built from LVC's OpenAPI spec.

        Raises ``RuntimeError`` if :meth:`fetch_schema` has not been called yet.
        """
        return self._schema_mgr.model

    def set_rtsp_resolver(self, resolver) -> None:
        """Kept for interface compatibility — not used in dynamic flow."""

    async def fetch_schema(self) -> dict[str, Any]:
        """Fetch the StartRunRequest JSON Schema from LVC's OpenAPI spec at runtime.

        Calls :meth:`~.schema.LvcSchemaManager.fetch`, which resolves ``$ref``s,
        adds UI annotations, and caches a dynamic Pydantic model.

        Raises ``httpx.HTTPError`` if LVC is unreachable.
        """
        return await self._schema_mgr.fetch(self._api)

    # ── IAnalyticsAppShim — lifecycle ──────────────────────────────────────────────

    async def is_reachable(self) -> bool:
        return await self._api.is_reachable()

    async def start(self, params: BaseModel) -> dict[str, Any]:
        """Validate params against the dynamic model and start a run.

        Called by ``POST /v1/analytics-apps/{app_id}/runs`` after Pydantic validation.
        ``rtspUrl`` is required and must be non-empty (validated by the dynamic model).
        All other fields are passed through as-is — LVC's own defaults apply for
        any omitted optional fields.
        """
        if not isinstance(params, self.param_model):
            params = self.param_model.model_validate(
                params if isinstance(params, dict) else params.model_dump()
            )

        rtsp_url: str = getattr(params, "rtspUrl", "") or ""
        if not rtsp_url:
            raise ValueError("rtspUrl is required but was empty")

        payload: dict[str, Any] = {}
        for field_name in self.param_model.model_fields:
            value = getattr(params, field_name, None)
            if value is not None:
                payload[field_name] = value

        run = await self._api.start_run(payload)
        if run is None:
            raise RuntimeError("LVC backend failed to start the run")

        # Enrich with relative WebRTC WHEP URL (same-origin → UI nginx /whep proxy).
        peer_id = run.get("peerId", "")
        if peer_id:
            run["webrtcUrl"] = f"/whep/{peer_id}/whep"

        return run

    async def deliver(
        self,
        event: MetadataEvent,
        clip_path: str,
    ) -> AnalysisResult | None:
        """Start a Live Captioning run triggered by a VMS event.

        ``clip_path`` is ignored — LVC works on live RTSP, not recorded clips.
        All parameter defaults are discovered dynamically from the live LVC schema.
        ``pipelineName`` is resolved by fetching the available pipelines if not
        present in the schema defaults.
        """
        rtsp_url = event.vendor_meta.get("stream_url") or event.vendor_meta.get("rtsp_url")
        if not rtsp_url:
            logger.warning(
                "lvc_no_rtsp_url",
                event_id=event.event_id,
                camera_id=event.camera_id,
            )
            return None

        # Merge all defaults discovered from the live LVC OpenAPI schema.
        discovered = self._schema_mgr.get_defaults()
        payload: dict[str, Any] = {**discovered}

        # Always set the required fields.
        payload["rtspUrl"] = rtsp_url
        payload["runName"] = f"vms-{event.camera_id}"

        # pipelineName has no schema default — fetch the first available pipeline.
        if "pipelineName" not in payload:
            pipelines = await self._api.get_pipelines()
            if pipelines:
                payload["pipelineName"] = pipelines[0]
                logger.info("lvc_deliver_pipeline_resolved", pipeline=pipelines[0])
        run = await self._api.start_run(payload)
        if not run:
            return None

        run_id = run.get("runId", "")
        peer_id = run.get("peerId", "")
        mqtt_topic = run.get("mqttTopic", "")
        webrtc_url = f"/whep/{peer_id}/whep" if peer_id else ""

        logger.info("lvc_run_started", run_id=run_id, peer_id=peer_id)
        return AnalysisResult(
            event_id=event.event_id,
            labels=["live_captioning"],
            status="running",
            vendor_meta={
                "run_id": run_id,
                "peer_id": peer_id,
                "webrtc_url": webrtc_url,
                "mqtt_topic": mqtt_topic,
                "rtsp_url": rtsp_url,
            },
        )

    # ── IAnalyticsAppShim — generic run management ─────────────────────────────────

    def _enrich_run(self, run: dict[str, Any]) -> dict[str, Any]:
        """Add webrtcUrl to a run dict using the peerId from LVC."""
        peer_id = run.get("peerId", "")
        if peer_id and "webrtcUrl" not in run:
            run["webrtcUrl"] = f"/whep/{peer_id}/whep"
        return run

    async def list_runs(self) -> list[dict[str, Any]]:
        # Raises httpx.HTTPError when LVC is unreachable — callers should NOT
        # treat that as "zero runs" and must not clean up _run_camera_map.
        runs = await self._api.list_runs()
        # Clean up stale run→camera mappings for runs no longer active in LVC.
        active_ids = {r.get("runId") or r.get("run_id") for r in runs}
        for stale_id in list(self._run_camera_map):
            if stale_id not in active_ids:
                self.unregister_run(stale_id)
        return [self._enrich_run(r) for r in runs]

    async def stop_run(self, run_id: str) -> bool:
        result = await self._api.stop_run(run_id)
        self.unregister_run(run_id)
        return result

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = await self._api.get_run(run_id)
        return self._enrich_run(run) if run else None

    async def results_stream_url(self) -> str:
        return self._api.results_stream_url

    async def get_options(self, option_type: str) -> list[Any]:
        """Return dropdown options for models or pipelines."""
        if option_type == "models":
            return await self._api.get_models()
        if option_type == "pipelines":
            return await self._api.get_pipelines()
        logger.warning("lvc_unknown_option_type", option_type=option_type)
        return []

    def camera_fields(self) -> list[str]:
        """Return fields annotated with ``x-vms-source: camera-id`` from the cached schema."""
        return [
            name
            for name, prop in self._schema_mgr.annotated_props.items()
            if prop.get("x-vms-source") == "camera-id"
        ]

    def mqtt_topic_prefix(self) -> str:
        """LVC publishes caption results to MQTT topic ``live-video-captioning/{run_id}``."""
        return "live-video-captioning"
