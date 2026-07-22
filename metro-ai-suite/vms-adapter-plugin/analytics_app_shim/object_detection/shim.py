# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Object Detection Analytics App shim.

Integrates a DLStreamer Pipeline Server–based object detection application
(e.g. DLStreamer Vision) as a VAP analytics app.

Data flow:
  Camera RTSP ──► DLStreamer Pipeline Server
                  └─► inference metadata via MQTT → MqttSubscriber
                                                      └─► Nx analytics push

Architecture
────────────
``ObjectDetectionAnalyticsAppShim`` is composed of:

* :class:`~.api_client.ObjectDetectionApiClient`  — HTTP calls to the Pipeline Server
* :class:`~.mqtt_subscriber.MqttSubscriber`        — started externally by the orchestrator

This shim implements :class:`~plugin.base.interfaces.IAnalyticsAppShim` so the
generic ``/v1/analytics-apps/{app_id}/…`` routes work without app-specific code.
"""

from __future__ import annotations

import asyncio
import copy
import ssl
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import BaseModel, create_model

from plugin.base.interfaces import IAnalyticsAppShim
from plugin.core.models.domain import AnalysisResult, MetadataEvent
from .config import ObjectDetectionAnalyticsAppConfig
from .api_client import ObjectDetectionApiClient

if TYPE_CHECKING:
    from plugin.core.pipeline.orchestrator import Orchestrator

logger = structlog.get_logger(__name__)


def _make_tls_context(cfg) -> ssl.SSLContext | None:
    """Build an SSLContext from ObjectDetectionAnalyticsAppConfig MQTT TLS fields, or None when disabled."""
    if not cfg.mqtt_tls_enabled:
        return None
    ctx = ssl.create_default_context(cafile=cfg.mqtt_ca_bundle or None)
    if cfg.mqtt_client_cert and cfg.mqtt_client_key:
        ctx.load_cert_chain(certfile=cfg.mqtt_client_cert, keyfile=cfg.mqtt_client_key)
    return ctx


class ObjectDetectionAnalyticsAppShim(IAnalyticsAppShim):
    """IAnalyticsAppShim implementation for DLStreamer Pipeline Server–based apps."""

    def __init__(self, config: ObjectDetectionAnalyticsAppConfig) -> None:
        self._config = config
        self._api = ObjectDetectionApiClient(
            base_url=config.base_url,
            tls_verify=config.tls_verify,
            tls_ca_bundle=config.tls_ca_bundle,
        )
        self._param_model: type[BaseModel] = BaseModel
        # Maps pipeline version (user-facing name) → pipeline root (URL path segment)
        # e.g. "dls_vision_pipeline" → "user_defined_pipelines"
        self._pipeline_root_map: dict[str, str] = {}
        # Tracks active runs: run_id (= instance_id hex) → run metadata
        self._runs: dict[str, dict[str, Any]] = {}

    @property
    def app_id(self) -> str:  # type: ignore[override]
        return self._config.app_id

    @property
    def display_name(self) -> str:  # type: ignore[override]
        return self._config.display_name

    async def on_startup(self, orchestrator: Orchestrator) -> None:
        """Start object detection MQTT subscriber background task."""
        from analytics_app_shim.object_detection.mqtt_subscriber import MqttSubscriber
        subscriber = MqttSubscriber()
        task = asyncio.create_task(
            subscriber.run(
                mqtt_host=self._config.mqtt_host,
                mqtt_port=self._config.mqtt_port,
                vms_shim_sets=orchestrator.vms_shim_sets,
                analytics_app_id=self.app_id,
                label_type_map=self._config.label_type_map,
                timestamp_offset_ms=self._config.metadata_timestamp_offset_ms,
                tls_context=_make_tls_context(self._config),
            ),
            name=f"mqtt-subscriber-{self.app_id}",
        )
        orchestrator.add_background_task(task)
        logger.info(
            "mqtt_subscriber_task_started",
            app_id=self.app_id,
            mqtt_host=self._config.mqtt_host,
            mqtt_port=self._config.mqtt_port,
        )

    @property
    def param_model(self) -> type[BaseModel]:
        return self._param_model

    # ── IAnalyticsAppShim — schema ─────────────────────────────────────────────────

    async def fetch_schema(self) -> dict[str, Any]:
        """Build a JSON Schema from the available pipeline templates.

        Calls ``GET /pipelines``. Each entry has:
          - ``name``:    pipeline root directory (e.g. "user_defined_pipelines")
          - ``version``: user-facing pipeline identifier (e.g. "dls_vision_pipeline")

        The UI ``pipeline_name`` field shows the ``version`` values.  The root
        is stored in ``_pipeline_root_map`` so ``start()`` can construct the
        correct POST URL: ``/pipelines/{root}/{version}``.
        """
        pipelines = await self._api.list_pipelines()

        self._pipeline_root_map = {}
        pipeline_names: list[str] = []
        for p in pipelines:
            if not isinstance(p, dict):
                continue
            root = p.get("name", "user_defined_pipelines")
            version = p.get("version", "")
            if version:
                self._pipeline_root_map[version] = root
                pipeline_names.append(version)

        schema: dict[str, Any] = {
            "type": "object",
            "title": f"{self.display_name} Start Parameters",
            "required": ["pipeline_name", "camera_id"],
            "properties": {
                "pipeline_name": {
                    "type": "string",
                    "title": "Pipeline",
                    "description": "Pipeline template to run",
                    "enum": pipeline_names or [],
                    "x-vms-source": "pipeline",
                },
                "camera_id": {
                    "type": "string",
                    "title": "Camera",
                    "description": "Camera to process (RTSP URL resolved automatically)",
                    "x-vms-source": "camera-id",
                },
                "parameters": {
                    "type": "object",
                    "title": "Pipeline parameters",
                    "description": (
                        "Extra parameters forwarded to the Pipeline Server payload. "
                        "E.g. {\"detection-properties\": {\"device\": \"CPU\"}}"
                    ),
                    "default": {},
                    "additionalProperties": True,
                    "x-format": "textarea",
                },
            },
        }

        self._param_model = create_model(
            "OdStartParams",
            pipeline_name=(str, ...),
            camera_id=(str, ...),
            camera_id_ref=(str, ""),   # original camera_id before RTSP resolution (e.g. "nx:abc123")
            parameters=(dict, {}),
        )

        return schema

    # ── IAnalyticsAppShim — lifecycle ──────────────────────────────────────────────

    def _build_mqtt_topic(self, camera_id_ref: str) -> str:
        """Build the MQTT publish topic from the original camera_id.

        Format: ``{vendor_prefix}/{app_id}/{device_id}``
        Example: ``nx/dls_vision/e3e9a385-7fe0-3ba5-5482-a86cde7faf48``

        The subscriber listens on ``+/{app_id}/+`` and uses prefix-match on
        the first segment to find the right VMS shim (e.g. ``nx`` → ``nx-main``).
        """
        if ":" in camera_id_ref:
            vendor_prefix, device_id = camera_id_ref.split(":", 1)
        else:
            vendor_prefix, device_id = "vap", camera_id_ref or "unknown"
        return f"{vendor_prefix}/{self._config.app_id}/{device_id}"

    async def is_reachable(self) -> bool:
        return await self._api.is_reachable()

    async def start(self, params: BaseModel) -> dict[str, Any]:
        """Start a pipeline run for the given camera.

        The ``camera_id`` field is resolved to an RTSP URL by the generic
        run route before this method is called (see ``camera_fields()``).

        Payload sent to Pipeline Server::

            {
              "source": {"uri": "<rtsp_url>", "type": "uri"},
              "parameters": { ...extra_params from the ``parameters`` field }
            }
        """
        data = params.model_dump() if hasattr(params, "model_dump") else dict(params)

        pipeline_name: str = data.get("pipeline_name", "")
        stream_url: str = data.get("camera_id", "")
        extra_params: dict = data.get("parameters", {}) or {}
        camera_id_ref: str = data.get("camera_id_ref", "")

        if not pipeline_name:
            raise ValueError("pipeline_name is required")
        if not stream_url:
            raise ValueError("camera_id / stream URL is required")

        pipeline_root = self._pipeline_root_map.get(pipeline_name, "user_defined_pipelines")

        # Build MQTT topic from the original camera_id (e.g. "nx:abc123")
        # Topic format: "{vendor_prefix}/{app_id}/{device_id}" → matches subscriber filter "+/{app_id}+"
        # e.g. "nx/dls_vision/e3e9a385-7fe0-3ba5-5482-a86cde7faf48"
        mqtt_topic = self._build_mqtt_topic(camera_id_ref)

        payload: dict[str, Any] = {
            "source": {
                "uri": stream_url,
                "type": "uri",
                "properties": {
                    "protocols": "tcp",
                    "add-reference-timestamp-meta": True,
                    "latency": 100,
                },
            },
            "destination": {
                "metadata": {
                    "type": "mqtt",
                    "host": f"{self._config.pipeline_server_mqtt_host}:{self._config.pipeline_server_mqtt_port}",
                    "topic": mqtt_topic,
                },
            },
            "parameters": extra_params,
        }
        logger.info("-"*100)
        # log payload with rtsp url redacted
        redacted_payload = copy.deepcopy(payload)
        if "source" in redacted_payload:
            if "uri" in redacted_payload["source"]:
                redacted_payload["source"]["uri"] = "REDACTED_RSTP_URL"
        logger.info(redacted_payload)
        logger.info("-"*100)

        result = await self._api.start_run(pipeline_root, pipeline_name, payload)
        if result is None:
            raise RuntimeError(
                f"Pipeline Server failed to start pipeline '{pipeline_root}/{pipeline_name}'"
            )

        # instance_id is a hex UUID string returned by the Pipeline Server
        instance_id: str = str(result.get("instance_id") or result.get("id") or "")
        run_id = instance_id  # already URL-safe hex string

        self._runs[run_id] = {
            "run_id": run_id,
            "pipeline_name": pipeline_name,
            "pipeline_root": pipeline_root,
            "stream_url": stream_url,
        }

        logger.info("od_run_started", run_id=run_id, pipeline=f"{pipeline_root}/{pipeline_name}")
        return {
            "run_id": run_id,
            "pipeline_name": pipeline_name,
            "pipeline_root": pipeline_root,
        }

    # ── IAnalyticsAppShim — run management ─────────────────────────────────────────

    async def list_runs(self) -> list[dict[str, Any]]:
        return await self._api.list_runs()

    async def stop_run(self, run_id: str) -> bool:
        """Stop a pipeline instance by its hex UUID run_id."""
        ok = await self._api.stop_run(run_id)
        if ok:
            self._runs.pop(run_id, None)
        return ok

    # ── VMS-driven pipeline control ─────────────────────────────────────────────

    def control_params(self) -> list[dict]:
        """Declare VMS-neutral control knobs for this app (delegates to config)."""
        return self._config.control_params()

    async def start_for_camera(self, camera_id: str, stream_url: str, controls: dict) -> str | None:
        """Start a DLStreamer pipeline for one camera from VMS control values."""
        pipeline_name = self._config.pipeline_name
        if not pipeline_name:
            logger.error("od_pipeline_name_not_configured", app_id=self.app_id)
            return None
        # _param_model is bare BaseModel until fetch_schema() runs; guard against
        # the unlikely race where the polling task fires before schema fetch completes.
        if not self._pipeline_root_map:
            logger.warning("od_schema_not_ready", app_id=self.app_id)
            return None
        device = controls.get("device", "CPU")
        params = self._param_model.model_validate({
            "pipeline_name": pipeline_name,
            "camera_id": stream_url,
            "camera_id_ref": camera_id,
            "parameters": {"detection-properties": {"device": device}},
        })
        try:
            result = await self.start(params)
            return result.get("run_id") or None
        except Exception as exc:
            logger.error("od_start_for_camera_failed", app_id=self.app_id, error=str(exc))
            return None

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get status of a pipeline instance by its hex UUID run_id."""
        return await self._api.get_run(run_id)

    # ── IAnalyticsAppShim — deliver (not used — push model) ────────────────────────

    async def deliver(
        self, event: MetadataEvent, clip_path: str,
    ) -> AnalysisResult | None:
        """Not used: object detection uses MQTT push model, not event-triggered pull."""
        logger.debug("od_deliver_noop", event_id=event.event_id)
        return None

    def camera_fields(self) -> list[str]:
        """Return the field that holds camera IDs, triggering RTSP resolution."""
        return ["camera_id"]
