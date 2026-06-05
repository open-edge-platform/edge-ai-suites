# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Abstract shim interfaces : single ``IVmsShim`` per VMS + optional ``IAnalyticsAppShim``.

Design decisions:

* **Single shim per VMS.** ``IVmsShim`` covers read + write + register;
  no separate command shim is needed.
* **RTSP-only.** No folder watchdog and no API polling are exposed by
  the interface. Apps consume RTSP directly via
  :meth:`get_live_stream_url`.
* **Plugin facilitates auth — never stores it.** No ``connect``-time
  session keep-alive is required; auth is per-request for vendors that
  need it.
* **App pulls; plugin does not push clips.** ``get_clip_url`` returns
  a URL — no file transfer.
* **Per-shim register API.** :meth:`register_analytics` is the explicit
  hook the plugin calls on startup, and the ``POST /v1/vms/{name}/register``
  endpoint exposes it externally.
* **``IAnalyticsAppShim`` is optional.** It is retained only as a thin
  glue path for Analytics Apps (e.g. Live Video Captioning) that need a
  bespoke pipeline ``start()`` flow.
"""

from __future__ import annotations

import asyncio
import copy
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from plugin.core.models.domain import AnalysisResult, Camera, CommandResult, MetadataEvent

if TYPE_CHECKING:
    from plugin.core.pipeline.orchestrator import Orchestrator


DEFAULT_VMS_MANIFEST: dict = {
    "engineId": "vms-adapter-plugin",
    "displayName": "VMS Adapter Plugin",
    "version": "1.0",
    "objectTypes": [{"id": "vms_plugin.detection", "name": "Detection"}],
    "eventTypes": [],
}


class IVmsShim(ABC):
    """Single per-VMS abstraction : read + write + register."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    async def discover_cameras(self) -> list[Camera]: ...

    @abstractmethod
    async def get_camera_metadata(self, camera_id: str) -> Camera | None: ...

    @abstractmethod
    async def get_live_stream_url(self, camera_id: str) -> str | None: ...

    @abstractmethod
    async def get_clip_url(
        self, camera_id: str, from_dt: datetime, to_dt: datetime,
    ) -> str | None: ...

    @abstractmethod
    async def register_analytics(self, manifest: dict[str, Any]) -> dict[str, Any]: ...

    @property
    @abstractmethod
    def camera_id_prefix(self) -> str:
        """Vendor-specific camera ID prefix (e.g. ``"nx:"``, ``"frigate:"``).

        Camera IDs stored in the DB are vendor-prefixed strings like
        ``"nx:abc123"`` or ``"frigate:front-door"``. This prefix is used by
        routing code to dispatch a camera_id to the correct shim.
        """
        ...

    async def find_integration_in_vms(self, manifest_id: str) -> dict[str, Any] | None:
        """Check if an analytics integration exists in the VMS by its manifest ID.

        Returns a dict with ``username``, ``password``, ``request_id`` if found,
        or ``None`` if not found or not applicable for this VMS vendor.
        Override in VMS shims that support analytics integration lookup.
        """
        return None

    def set_integration_credentials(self, username: str, password: str) -> None:
        """Store analytics integration user credentials for metadata push.

        Called after Nx integration registration. Override in VMS shims that
        support analytics metadata push (e.g. NxWitnessVmsShim).
        """

    async def on_startup(self, orchestrator: Orchestrator) -> None:
        """Vendor-specific startup hook called after connect().

        Default registers the generic analytics manifest. Override in shims that
        need richer startup logic (e.g. Nx autoregister with DB state tracking).
        Exceptions are handled by the caller; implementations may also catch
        internally to allow partial startup.
        """
        await self.register_analytics(copy.deepcopy(DEFAULT_VMS_MANIFEST))

    async def handle_register(self, body: dict[str, Any], db: Any, vms_name: str) -> Any:
        """Handle POST /vms/{name}/register for this vendor.

        Default: delegates directly to ``register_analytics(body["manifest"])``
        and returns the raw result dict.

        Override in shims that need richer registration logic (e.g. Nx Witness,
        which persists integration state to the DB and checks for conflicts).
        Implementations may raise ``fastapi.HTTPException`` to return HTTP errors.

        Args:
            body: Raw JSON request body as a dict.
            db: Active ``AsyncSession`` injected from FastAPI's dependency.
            vms_name: Name of the VMS instance being registered.
        """
        return await self.register_analytics(body.get("manifest", {}))

    async def push_analytics_objects(
        self,
        device_id: str,
        objects: list[dict[str, Any]],
        timestamp_ms: int,
    ) -> bool:
        """Push analytics object metadata to a VMS device.

        Args:
            device_id: Vendor-native device identifier (e.g. Nx device UUID without prefix).
            objects: List of Nx-format object dicts (trackId, typeId, boundingBox, confidence).
            timestamp_ms: Frame wall-clock timestamp in milliseconds.

        Returns True on success, False on failure. Default no-op for non-Nx shims.
        Override in VMS shims that support analytics metadata push.
        """
        return False

    @abstractmethod
    async def acknowledge_event(
        self, camera_id: str, event_id: str, message: str = "",
    ) -> CommandResult: ...

    @abstractmethod
    async def set_bookmark(
        self, camera_id: str, timestamp: datetime, label: str,
    ) -> CommandResult: ...

    @abstractmethod
    async def push_label(
        self, camera_id: str, event_id: str, labels: list[str],
        confidence: float | None = None,
    ) -> CommandResult: ...

    @abstractmethod
    async def trigger_recording(
        self, camera_id: str, duration_seconds: int = 30,
    ) -> CommandResult: ...


class IAnalyticsAppShim(ABC):
    """Optional thin App-Shim for Analytics Apps that need bespoke glue."""

    app_id: str = ""
    display_name: str = ""
    param_model: type[BaseModel] = BaseModel

    @abstractmethod
    async def fetch_schema(self) -> dict[str, Any]:
        """Fetch the JSON Schema for this app's start parameters from its own API.

        Implementations should:
        1. Call the analytics app's API (e.g. GET /openapi.json) to get the live schema.
        2. Build a dynamic Pydantic model via ``build_pydantic_from_schema()``.
        3. Cache the model so ``param_model`` returns it on subsequent calls.
        4. Return the raw JSON Schema dict (used as ``params_schema`` in discovery).

        If the app is unreachable, raise ``httpx.HTTPError`` or return the
        static fallback ``self.param_model.model_json_schema()``.
        """
        ...

    @abstractmethod
    async def deliver(
        self, event: MetadataEvent, clip_path: str,
    ) -> AnalysisResult | None: ...

    @abstractmethod
    async def is_reachable(self) -> bool: ...

    async def is_available(self) -> bool:
        return await self.is_reachable()

    @abstractmethod
    async def start(self, params: BaseModel) -> dict[str, Any]: ...

    # ── Generic run lifecycle (used by /v1/analytics-apps/{app_id}/runs routes) ────

    async def list_runs(self) -> list[dict[str, Any]]:
        """Return all active runs for this app. Override in concrete shims."""
        return []

    async def stop_run(self, run_id: str) -> bool:
        """Stop a run by ID. Return True on success. Override in concrete shims."""
        return False

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Return details for a single run, or None if not found."""
        return None

    async def results_stream_url(self) -> str:
        """Return the SSE/HTTP URL the plugin should proxy for live results.

        The generic ``GET /results/stream`` route streams bytes from this URL.
        Raise ``NotImplementedError`` if the app does not support streaming.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support result streaming")

    async def get_options(self, option_type: str) -> list[Any]:
        """Return a list of options for a named dropdown (e.g. 'models', 'pipelines').

        The generic ``GET /options/{option_type}`` route calls this method.
        Return an empty list for unknown option types.
        """
        return []

    def camera_fields(self) -> list[str]:
        """Return field names whose values are camera IDs that need RTSP resolution.

        The generic start-run route resolves each listed field's value from a
        ``camera_id`` (as sent by the UI) to a ``stream_url`` before Pydantic
        validation, so the downstream shim always receives a real RTSP URL.

        Override this in concrete shims to declare camera-bound fields.
        The default returns an empty list (no camera resolution needed).
        """
        return []

    # ── Per-app MQTT queue API ────────────────────────────────────────────────
    # Shims that own an aiomqtt subscriber override these to expose result queues
    # to the generic SSE route — no global MQTT client needed.

    def subscribe_run(self, run_id: str) -> asyncio.Queue | None:
        """Return a per-run asyncio.Queue for streaming results, or None if not supported."""
        return None

    def release_run(self, run_id: str) -> None:
        """Release the per-run queue when the SSE client disconnects."""

    def get_broadcast_queue(self) -> asyncio.Queue | None:
        """Return a broadcast queue for all runs, or None if not supported."""
        return None

    def mqtt_topic_prefix(self) -> str | None:
        """Return the MQTT topic prefix used by this Analytics App, or None if not using MQTT.

        The shim's own aiomqtt subscriber subscribes to ``{prefix}/#`` at startup
        and routes messages to per-run queues consumed by the SSE result stream.

        Example: ``"live-video-captioning"`` → subscribes to
        ``"live-video-captioning/#"`` and processes topics like
        ``"live-video-captioning/{run_id}"``.

        Return ``None`` (default) if the app does not publish results via MQTT;
        the SSE route will fall back to proxying the app's HTTP SSE endpoint.
        """
        return None

    async def on_startup(self, orchestrator: Orchestrator) -> None:
        """App-specific startup hook called after schema prefetch and dep injection.

        Default is a no-op. Override in shims that need to start background tasks
        (e.g. MQTT subscribers) or perform startup I/O.
        """
