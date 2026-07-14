# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Nx Witness VMS shim - single class, standard REST API v4 only.

All endpoints used here are documented in the official Nx Meta API tool
(https://meta.nxvms.com/doc/developers/api-tool):

  * POST   /rest/v4/login/sessions               -> create session token
  * DELETE /rest/v4/login/sessions/{token}       -> invalidate session
  * GET    /rest/v4/servers/*/info               -> reachability probe (returns array)
  * GET    /rest/v4/devices                      -> list devices
  * GET    /rest/v4/devices/{deviceId}           -> device record
  * GET    /{deviceId}                           -> RTSP live stream URL (constructed, not called)
  * POST   /rest/v4/devices/{deviceId}/bookmarks -> create bookmark
  * GET    /rest/v4/analytics/engines            -> list engines
  * PATCH  /rest/v4/analytics/engines/{id}/deviceAgents/{id} -> enable device agent
  * POST   /rest/v4/analytics/engines/{id}/deviceAgents/{id}/manifest -> push device agent manifest
  * PATCH  /rest/v4/devices/{deviceId}           -> toggle recording

Live RTSP URLs are constructed client-side per the Nx v4 spec
(``/{deviceId}`` Utilities endpoint):

  rtsp://<host>:<port>/{deviceId}?onvif_replay=true

The media server serves RTSP on the same host and port as the REST API.
Credentials are embedded in the URL for third-party RTSP client compatibility
(VLC, FFmpeg, etc.) since those require Basic/Digest auth. Clip URLs are
built using the documented ``/rest/v4/devices/{id}/footage`` endpoint.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse,quote

# Bundled default analytics integration manifest, co-located with this shim.
# Used automatically when analytics_manifest_path is not set in config.
DEFAULT_MANIFEST_PATH = Path(__file__).parent / "nx_integration.json"

import httpx
import structlog

from plugin.base.interfaces import IVmsShim
from plugin.core.config import VmsInstanceConfig
from plugin.core.models.domain import Camera, CommandResult
from vms_shim.nxwitness.settings_factory import apply_settings_model

if TYPE_CHECKING:
    from plugin.core.pipeline.orchestrator import Orchestrator

logger = structlog.get_logger(__name__)


def _merge_label_types_into_manifest(
    manifests: dict,
    label_type_map: dict[str, str],
) -> None:
    """Merge typeIds from ``label_type_map`` into the Nx manifest dicts in-place.

    Adds any typeId that appears as a value in ``label_type_map`` (and is not
    already declared) to both ``engineManifest.typeLibrary.objectTypes`` and
    ``deviceAgentManifest.supportedTypes``.  This keeps the registered manifest
    in sync with whatever labels are configured without requiring manual JSON edits.
    """
    extra_type_ids = set(label_type_map.values())
    if not extra_type_ids:
        return

    # -- engineManifest.typeLibrary.objectTypes --
    engine = manifests.setdefault("engineManifest", {})
    type_library = engine.setdefault("typeLibrary", {})
    object_types: list[dict] = type_library.setdefault("objectTypes", [])
    existing_ids = {t.get("id") for t in object_types}
    for type_id in sorted(extra_type_ids):
        if type_id not in existing_ids:
            object_types.append({"id": type_id, "name": type_id})
            existing_ids.add(type_id)

    # -- deviceAgentManifest.supportedTypes --
    da_manifest = manifests.setdefault("deviceAgentManifest", {})
    supported: list[dict] = da_manifest.setdefault("supportedTypes", [])
    existing_supported = {t.get("objectTypeId") for t in supported}
    for type_id in sorted(extra_type_ids):
        if type_id not in existing_supported:
            supported.append({
                "objectTypeId": type_id,
                "attributes": ["boundingBox", "confidence"],
            })


class NxWitnessVmsShim(IVmsShim):
    """Single shim for Nx Witness using only standard /rest/v4 endpoints."""

    def __init__(self, config: VmsInstanceConfig):
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._connected = False
        self._token: str | None = None
        # Integration user credentials (set after analytics registration)
        self._integration_username: str | None = None
        self._integration_password: str | None = None
        # Cached per-session state for metadata push
        self._integration_client: httpx.AsyncClient | None = None
        self._integration_token: str | None = None
        self._engine_id: str | None = None
        # Device agents that have already been enabled for this session
        self._enabled_device_agents: set[str] = set()
        # Orchestrator reference (set in on_startup)
        self._orchestrator: Any = None
        # Per-device pipeline run tracking: device_id → instance_id
        self._device_pipeline_runs: dict[str, str] = {}
        # Previous settings per device for change detection
        self._device_prev_settings: dict[str, dict] = {}

    @property
    def camera_id_prefix(self) -> str:
        return "nx:"

    def _httpx_verify(self) -> bool | str:
        if self._config.tls_verify and self._config.tls_ca_bundle:
            return self._config.tls_ca_bundle
        return self._config.tls_verify

    # -- Lifecycle ------------------------------------------------------
    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=30.0,
            verify=self._httpx_verify(),
        )
        await self._login()

    async def _login(self) -> None:
        """POST /rest/v4/login/sessions to obtain a Bearer token."""
        if not self._client:
            return
        auth = self._config.auth
        if not auth.username:
            self._connected = False
            return
        try:
            resp = await self._client.post(
                "/rest/v4/login/sessions",
                json={"username": auth.username, "password": auth.password},
            )
            resp.raise_for_status()
            self._token = (resp.json() or {}).get("token")
            if self._token:
                self._client.headers["Authorization"] = f"Bearer {self._token}"
            # Probe reachability with a documented endpoint.
            info = await self._client.get("/rest/v4/servers/*/info")
            self._connected = info.status_code == 200
            logger.info("nx_connected", status=info.status_code)
        except httpx.HTTPError as e:
            logger.error("nx_connect_failed", error=str(e))
            self._connected = False

    async def disconnect(self) -> None:
        if self._client and self._token:
            try:
                await self._client.delete(f"/rest/v4/login/sessions/{self._token}")
            except httpx.HTTPError:
                pass
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False
        self._token = None

    def is_connected(self) -> bool:
        return self._connected

    # -- Discovery / metadata ------------------------------------------
    async def discover_cameras(self) -> list[Camera]:
        if not self._client:
            return []
        try:
            resp = await self._client.get("/rest/v4/devices")
            resp.raise_for_status()
            devices = resp.json()
        except httpx.HTTPError as e:
            logger.error("nx_discover_failed", error=str(e))
            return []

        cameras: list[Camera] = []
        for d in devices:
            if d.get("deviceType") != "Camera":
                continue
            device_id = d.get("id", "")
            vms_url = await self.get_live_stream_url(f"nx:{device_id}")
            cameras.append(_to_camera(d, stream_url=vms_url))
        logger.info("nx_cameras_discovered", count=len(cameras))
        return cameras

    async def get_camera_metadata(self, camera_id: str) -> Camera | None:
        if not self._client:
            return None
        device_id = camera_id.removeprefix("nx:")
        try:
            resp = await self._client.get(f"/rest/v4/devices/{device_id}")
            resp.raise_for_status()
            return _to_camera(resp.json())
        except httpx.HTTPError:
            return None

    # -- Stream / clip URLs --------------------------------------------
    async def get_live_stream_url(self, camera_id: str) -> str | None:
        """Build live RTSP URL per Nx Utilities with onvif_replay enabled."""
        device_id = camera_id.removeprefix("nx:")
        parsed = urlparse(self._config.base_url)
        host = parsed.hostname or self._config.base_url
        port = parsed.port or 7001
        auth = self._config.auth

        if auth.username:
            password = quote(str(auth.password), safe="")
            username = quote(str(auth.username), safe="")
            return f"rtsp://{username}:{password}@{host}:{port}/{device_id}?onvif_replay=true"
        else:
            return f"rtsp://{host}:{port}/{device_id}?onvif_replay=true"

    async def get_clip_url(
        self, camera_id: str, from_dt: datetime, to_dt: datetime,
    ) -> str | None:
        # The standard Nx REST API does not expose a single "clip URL"
        # endpoint. Footage retrieval is handled by /rest/v4/devices/{id}
        # /footage which returns segment metadata; clients then fetch
        # via HLS. We surface that endpoint URL for the caller.
        if not self._client:
            return None
        device_id = camera_id.removeprefix("nx:")
        return (
            f"{self._config.base_url.rstrip('/')}"
            f"/rest/v4/devices/{device_id}/footage"
            f"?startTimeMs={int(from_dt.timestamp() * 1000)}"
            f"&endTimeMs={int(to_dt.timestamp() * 1000)}"
        )

    # -- Register analytics manifest -----------------------------------
    async def register_analytics(self, manifest: dict[str, Any]) -> dict[str, Any]:
        """Phase 1 Nx Analytics Integration registration.

        If ``manifest`` contains the structured Nx keys (``integrationManifest``,
        ``engineManifest``), the full Phase 1 REST workflow is executed:
          1. POST /rest/v4/analytics/integrations/*/requests
          2. POST .../requests/{requestId}/approve

        If the manifest is empty or missing those keys, falls back to listing
        existing engines (backward-compatible behaviour for non-Nx callers).
        """
        if not self._client:
            return {"status": "error", "reason": "not_connected"}

        integration_manifest = manifest.get("integrationManifest")
        engine_manifest = manifest.get("engineManifest")

        if not integration_manifest or not engine_manifest:
            # Backward-compat: just list available engines.
            try:
                resp = await self._client.get("/rest/v4/analytics/engines")
                return {
                    "status": "ok" if resp.status_code == 200 else "error",
                    "http_status": resp.status_code,
                    "engines": resp.json() if resp.status_code == 200 else None,
                }
            except httpx.HTTPError as e:
                return {"status": "error", "reason": str(e)}

        device_agent_manifest = manifest.get("deviceAgentManifest")
        pin_code = manifest.get("pinCode", "1234")

        payload: dict[str, Any] = {
            "integrationManifest": integration_manifest,
            "engineManifest": engine_manifest,
            "pinCode": pin_code,
            "isRestOnly": True,
        }
        if device_agent_manifest:
            payload["deviceAgentManifest"] = device_agent_manifest

        # Try fresh registration first
        fresh = await self._post_integration_request(payload)
        if fresh:
            approved = await self._approve_integration_request(fresh["request_id"])
            if not approved:
                return {
                    "status": "registered",
                    "username": fresh["username"],
                    "password": fresh["password"],
                    "request_id": fresh["request_id"],
                    "reason": "approval_failed",
                }
            logger.info(
                "nx_integration_approved",
                username=fresh["username"],
                request_id=fresh["request_id"],
            )
            return {
                "status": "approved",
                "username": fresh["username"],
                "password": fresh["password"],
                "request_id": fresh["request_id"],
            }

        return {"status": "error", "reason": "create_integration_request_failed"}

    async def _post_integration_request(
        self, payload: dict[str, Any],
    ) -> dict[str, str] | None:
        """Single attempt at POST /rest/v4/analytics/integrations/*/requests."""
        try:
            resp = await self._client.post(  # type: ignore[union-attr]
                "/rest/v4/analytics/integrations/*/requests",
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()
            return {
                "username": result.get("username", ""),
                "password": result.get("password", ""),
                "request_id": result.get("requestId", ""),
            }
        except httpx.HTTPStatusError as e:
            logger.error(
                "nx_create_integration_failed",
                status_code=e.response.status_code,
                response_body=e.response.text,
                payload_keys=list(payload.keys()),
            )
            return None
        except httpx.HTTPError as e:
            logger.error("nx_create_integration_failed", error=str(e))
            return None

    async def find_integration_in_vms(
        self, manifest_id: str,
    ) -> dict[str, str] | None:
        """Check whether an integration with the given manifest ID exists in Nx.

        Checks both the approved integrations list and the Nx users list (to
        catch pending/unapproved requests). Returns a dict with ``username``,
        ``password`` (empty — not recoverable from Nx), and ``request_id`` if
        found, or ``None`` if the integration does not exist in Nx at all.
        """
        # 1. Check approved integrations list
        try:
            resp = await self._client.get("/rest/v4/analytics/integrations")  # type: ignore[union-attr]
            resp.raise_for_status()
            for item in resp.json():
                api_info = item.get("apiIntegrationInfo") or {}
                sdk_info = item.get("sdkIntegrationInfo") or {}
                if (
                    api_info.get("integrationId") == manifest_id
                    or sdk_info.get("integrationId") == manifest_id
                ):
                    return {
                        "username": manifest_id,
                        "password": "",  # not recoverable from Nx
                        "request_id": api_info.get("integrationUserId") or item.get("id", ""),
                    }
        except httpx.HTTPError as e:
            logger.error("nx_list_integrations_failed", error=str(e))
            return None  # can't determine state — treat as unknown

        # 2. Check users list for a pending (unapproved) integration
        try:
            resp = await self._client.get("/rest/v4/users")  # type: ignore[union-attr]
            resp.raise_for_status()
            for user in resp.json():
                if user.get("name") == manifest_id or user.get("login") == manifest_id:
                    return {
                        "username": manifest_id,
                        "password": "",  # not recoverable from Nx
                        "request_id": user.get("id", ""),
                    }
        except httpx.HTTPError as e:
            logger.error("nx_list_users_failed", error=str(e))

        return None

    async def _approve_integration_request(self, request_id: str) -> bool:
        """POST /rest/v4/analytics/integrations/*/requests/{requestId}/approve."""
        try:
            resp = await self._client.post(  # type: ignore[union-attr]
                f"/rest/v4/analytics/integrations/*/requests/{request_id}/approve",
                json={"requestId": request_id},
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error("nx_approve_integration_failed", error=str(e), request_id=request_id)
            return False

    # -- Analytics metadata push ----------------------------------------

    def set_integration_credentials(self, username: str, password: str) -> None:
        """Store integration user credentials for analytics metadata push.

        Called by the orchestrator after the Nx integration has been registered
        and approved. Required before ``push_analytics_objects()`` will work.
        """
        self._integration_username = username
        self._integration_password = password
        # Invalidate cached session so the new credentials are used.
        self._integration_token = None
        self._engine_id = None
        if self._integration_client:
            import asyncio
            try:
                asyncio.get_event_loop().run_until_complete(
                    self._integration_client.aclose()
                )
            except Exception:
                pass
            self._integration_client = None
        logger.info("nx_integration_credentials_set", username=username)

    async def on_startup(self, orchestrator: Orchestrator) -> None:
        """Register Nx analytics integration on startup if not already approved in DB."""
        from plugin.core.db.session import get_session_factory
        from vms_shim.nxwitness import repository as nx_repo

        try:
            factory = get_session_factory()
        except RuntimeError:
            logger.warning("autoregister_skipped_no_db", vms=self._config.name)
            return

        manifest_path = (
            Path(self._config.analytics_manifest_path)
            if self._config.analytics_manifest_path
            else DEFAULT_MANIFEST_PATH
        )
        if not manifest_path.exists():
            logger.error(
                "nx_manifest_file_not_found",
                vms=self._config.name,
                path=str(manifest_path),
            )
            return

        try:
            with open(manifest_path) as f:
                manifests = json.load(f)
        except Exception as exc:
            logger.error(
                "nx_manifest_file_parse_failed",
                vms=self._config.name,
                path=str(manifest_path),
                error=str(exc),
            )
            return

        analytics_app_id = manifests.get("integrationManifest", {}).get("id", "default")
        manifest_id = analytics_app_id

        async with factory() as db:
            db_record = await nx_repo.get_nx_integration(db, self._config.name, analytics_app_id)

        nx_record = await self.find_integration_in_vms(manifest_id)

        if db_record and nx_record:
            logger.info(
                "nx_integration_already_registered",
                vms=self._config.name,
                analytics_app_id=analytics_app_id,
                username=db_record.nx_username,
            )
            if db_record.nx_username and db_record.nx_password:
                self.set_integration_credentials(db_record.nx_username, db_record.nx_password)
                logger.info(
                    "nx_integration_credentials_restored",
                    vms=self._config.name,
                    username=db_record.nx_username,
                )
            else:
                logger.warning(
                    "nx_integration_no_password_in_db",
                    vms=self._config.name,
                    analytics_app_id=analytics_app_id,
                    detail="Metadata push unavailable — recreate the integration to store credentials.",
                )
            return

        if not db_record and nx_record:
            logger.error(
                "nx_integration_exists_in_vms_not_in_db",
                vms=self._config.name,
                analytics_app_id=analytics_app_id,
                detail=(
                    "The Nx VMS already has an integration with this manifest ID but the "
                    "VAP database has no record of it. Clean up the integration in Nx or "
                    "call POST /v1/vms/{name}/register to force re-registration."
                ),
            )
            return

        if db_record and not nx_record:
            logger.error(
                "nx_integration_exists_in_db_not_in_vms",
                vms=self._config.name,
                analytics_app_id=analytics_app_id,
                detail=(
                    "The VAP database has an integration record but it is missing from the "
                    "Nx VMS. The integration may have been deleted from Nx manually. "
                    "Delete the DB record and restart, or recreate the integration in Nx."
                ),
            )
            return

        # Merge any label_type_map typeIds from object_detection analytics apps into the manifest.
        from analytics_app_shim.object_detection.config import ObjectDetectionAnalyticsAppConfig
        for ca_cfg in orchestrator.config.analytics_apps:
            if isinstance(ca_cfg, ObjectDetectionAnalyticsAppConfig) and ca_cfg.label_type_map:
                _merge_label_types_into_manifest(manifests, ca_cfg.label_type_map)

        # Build the Nx device-agent settings panel from all configured apps so the
        # bundled manifest stays generic and any app added to config.yaml shows up.
        apply_settings_model(manifests, list(orchestrator.config.analytics_apps))

        try:
            result = await self.register_analytics(manifests)
        except Exception:
            logger.exception("nx_autoregister_failed", vms=self._config.name)
            return

        _VALID_STATUSES = {"pending", "registered", "approved", "failed"}
        nx_status = result.get("status", "failed")
        db_status = nx_status if nx_status in _VALID_STATUSES else "failed"
        async with factory() as db:
            await nx_repo.upsert_nx_integration(
                db,
                vms_name=self._config.name,
                analytics_app_id=analytics_app_id,
                integration_manifest=manifests.get("integrationManifest", {}),
                engine_manifest=manifests.get("engineManifest", {}),
                device_agent_manifest=manifests.get("deviceAgentManifest"),
                nx_username=result.get("username"),
                nx_password=result.get("password"),
                nx_request_id=result.get("request_id"),
                status=db_status,
            )

        logger.info(
            "nx_integration_autoregistered",
            vms=self._config.name,
            analytics_app_id=analytics_app_id,
            status=db_status,
            username=result.get("username"),
        )

        password = result.get("password") or ""
        username = result.get("username") or ""
        if username and password:
            self.set_integration_credentials(username, password)

        self._orchestrator = orchestrator
        task = asyncio.create_task(
            self._poll_device_agent_settings(),
            name=f"nx-settings-poll-{self._config.name}",
        )
        orchestrator.add_background_task(task)
        logger.info("nx_settings_poll_started", vms=self._config.name)

    async def _poll_device_agent_settings(self, interval: int = 5) -> None:
        """Poll device agent settings from Nx Witness every *interval* seconds."""
        while True:
            await asyncio.sleep(interval)
            try:
                cameras = await self.discover_cameras()
                for camera in cameras:
                    device_id = camera.camera_id.removeprefix("nx:")
                    settings = await self.get_device_agent_settings(device_id)
                    if settings:
                        logger.debug(
                            "nx_device_agent_settings_poll",
                            device_id=device_id,
                            camera_name=camera.name,
                            pipeline_enabled=settings["pipelineEnabled"],
                            device=settings["device"],
                        )
                        await self._reconcile_pipeline(camera, device_id, settings)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("nx_settings_poll_error", error=str(exc))

    async def _reconcile_pipeline(self, camera: Any, device_id: str, settings: dict) -> None:
        """Start or stop a DLStreamer pipeline based on current Nx client settings."""
        prev = self._device_prev_settings.get(device_id, {})
        self._device_prev_settings[device_id] = settings

        enabled = settings["pipelineEnabled"]
        device = settings["device"]

        settings_changed = (
            prev.get("pipelineEnabled") != enabled
            or prev.get("device") != device
        )

        run_id = self._device_pipeline_runs.get(device_id)

        if not enabled:
            if run_id:
                await self._stop_pipeline_for_device(device_id)
            return

        # enabled=True: start if not running or device changed
        if run_id and not settings_changed:
            return

        if run_id:
            await self._stop_pipeline_for_device(device_id)

        await self._start_pipeline_for_device(camera, device_id, device)

    async def _start_pipeline_for_device(
        self, camera: Any, device_id: str, device: str,
    ) -> None:
        """Start a DLStreamer pipeline using values from config."""
        if not self._orchestrator:
            logger.error("nx_start_pipeline_no_orchestrator", device_id=device_id)
            return

        od_shim = self._orchestrator.analytics_app_shims.get("dls_vision")
        if od_shim is None:
            logger.error("nx_start_pipeline_no_od_shim", device_id=device_id)
            return

        pipeline_name = od_shim._config.pipeline_name

        if not pipeline_name:
            logger.error("nx_poll_pipeline_name_not_configured", device_id=device_id)
            return

        rtsp_url = await self.get_live_stream_url(camera.camera_id)
        if not rtsp_url:
            logger.error("nx_start_pipeline_no_rtsp", device_id=device_id)
            return

        parameters: dict = {"detection-properties": {"device": device}}

        params = od_shim.param_model.model_validate({
            "pipeline_name": pipeline_name,
            "camera_id": rtsp_url,
            "camera_id_ref": camera.camera_id,
            "parameters": parameters,
        })

        try:
            result = await od_shim.start(params)
            run_id = result.get("run_id", "")
            self._device_pipeline_runs[device_id] = run_id
            logger.info(
                "nx_dls_pipeline_started",
                device_id=device_id,
                pipeline_name=pipeline_name,
                device=device,
                run_id=run_id,
            )
        except Exception as exc:
            logger.error("nx_dls_pipeline_start_failed", device_id=device_id, error=str(exc))

    async def _stop_pipeline_for_device(self, device_id: str) -> None:
        """Stop the running DLStreamer pipeline for the given device."""
        run_id = self._device_pipeline_runs.pop(device_id, None)
        if not run_id:
            return

        if not self._orchestrator:
            return

        od_shim = self._orchestrator.analytics_app_shims.get("dls_vision")
        if od_shim is None:
            return

        ok = await od_shim.stop_run(run_id)
        logger.info("nx_dls_pipeline_stopped", device_id=device_id, run_id=run_id, success=ok)

    async def handle_register(self, body: dict[str, Any], db: Any, vms_name: str) -> Any:
        """Handle POST /vms/{name}/register for Nx Witness.

        Resolves manifests from the request body or config, checks DB and Nx VMS
        state, performs registration if needed, persists credentials, and injects
        them into the live shim so metadata push works immediately.

        Raises ``fastapi.HTTPException`` for conflict (409), bad-request (422),
        and upstream-error (502) cases.
        """
        from fastapi import HTTPException
        from vms_shim.nxwitness import repository as nx_repo

        manifests = self._build_register_manifests(body)
        if manifests is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No analytics manifests provided. Supply integrationManifest + engineManifest "
                    "in the request body, or set analytics_manifest_path in config YAML."
                ),
            )

        analytics_app_id = body.get("analytics_app_id", "default")
        manifest_id = manifests.get("integrationManifest", {}).get("id", analytics_app_id)

        db_record = await nx_repo.get_nx_integration(db, vms_name, analytics_app_id)
        nx_record = await self.find_integration_in_vms(manifest_id)

        if db_record and nx_record:
            return db_record.model_dump(exclude={"id"})

        if not db_record and nx_record:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Integration '{manifest_id}' already exists in Nx VMS but has no DB record. "
                    "Delete the integration from Nx and retry, or contact your administrator."
                ),
            )

        if db_record and not nx_record:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Integration '{manifest_id}' is recorded in the DB but is missing from Nx VMS. "
                    "The integration may have been deleted from Nx manually. "
                    "Delete the DB record and retry registration."
                ),
            )

        result = await self.register_analytics(manifests)

        raw_status = result.get("status", "failed")
        _VALID_STATUSES = {"pending", "registered", "approved", "failed"}
        db_status = raw_status if raw_status in _VALID_STATUSES else "failed"

        integration = await nx_repo.upsert_nx_integration(
            db,
            vms_name=vms_name,
            analytics_app_id=analytics_app_id,
            integration_manifest=manifests.get("integrationManifest", {}),
            engine_manifest=manifests.get("engineManifest", {}),
            device_agent_manifest=manifests.get("deviceAgentManifest"),
            nx_username=result.get("username"),
            nx_password=result.get("password"),
            nx_request_id=result.get("request_id"),
            status=db_status,
        )

        if raw_status == "error":
            raise HTTPException(
                status_code=502,
                detail=f"Nx integration registration failed: {result.get('reason', 'unknown')}",
            )

        username = result.get("username") or ""
        password = result.get("password") or ""
        if username and password:
            self.set_integration_credentials(username, password)

        return integration.model_dump(exclude={"id"})

    def _build_register_manifests(self, body: dict[str, Any]) -> dict | None:
        """Resolve analytics manifests from the request body or config file."""
        integration_manifest = body.get("integration_manifest")
        engine_manifest = body.get("engine_manifest")

        if integration_manifest and engine_manifest:
            manifests: dict = {
                "integrationManifest": integration_manifest,
                "engineManifest": engine_manifest,
                "pinCode": body.get("pin_code", "1234"),
            }
            device_agent_manifest = body.get("device_agent_manifest")
            if device_agent_manifest:
                manifests["deviceAgentManifest"] = device_agent_manifest
            return manifests

        flat_manifest = body.get("manifest", {})
        if flat_manifest and "integrationManifest" in flat_manifest and "engineManifest" in flat_manifest:
            return flat_manifest

        manifest_path = self._config.analytics_manifest_path or str(DEFAULT_MANIFEST_PATH)
        path = Path(manifest_path)
        if not path.exists():
            from fastapi import HTTPException
            raise HTTPException(
                status_code=422,
                detail=f"analytics_manifest_path '{manifest_path}' not found",
            )
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as exc:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=422,
                detail=f"Failed to parse manifest file '{manifest_path}': {exc}",
            ) from exc

    async def _ensure_integration_session(self) -> bool:
        """Lazily login as the integration user and cache the bearer token.

        Returns True if a valid session is ready; False on failure.
        """
        if self._integration_token and self._integration_client:
            return True

        if not self._integration_username or not self._integration_password:
            logger.warning(
                "nx_push_skipped_no_credentials",
                detail="Call set_integration_credentials() after registration.",
            )
            return False

        parsed = urlparse(self._config.base_url)
        base_url = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or 7001}"
        client = httpx.AsyncClient(base_url=base_url, timeout=10.0, verify=self._httpx_verify())
        try:
            resp = await client.post(
                "/rest/v4/login/sessions",
                json={
                    "username": self._integration_username,
                    "password": self._integration_password,
                },
            )
            resp.raise_for_status()
            token = (resp.json() or {}).get("token")
            if not token:
                logger.error("nx_integration_login_no_token")
                await client.aclose()
                return False
            client.headers["Authorization"] = f"Bearer {token}"
            self._integration_client = client
            self._integration_token = token
            logger.info("nx_integration_session_ready", username=self._integration_username)
            return True
        except httpx.HTTPError as exc:
            logger.error("nx_integration_login_failed", error=str(exc))
            await client.aclose()
            return False

    async def _get_engine_id(self) -> str | None:
        """Return the engine ID for this integration (cached).

        Calls GET /rest/v4/analytics/engines via the integration client.  If
        multiple engines are returned (possible when the user can see engines
        from other integrations), the admin client is used to look up the Nx
        internal UUID of our integration and the result is filtered by
        ``integrationId``.
        """
        if self._engine_id:
            return self._engine_id
        if not self._integration_client:
            return None
        try:
            resp = await self._integration_client.get("/rest/v4/analytics/engines")
            resp.raise_for_status()
            engines = resp.json()
            if not engines or not isinstance(engines, list):
                return None

            if len(engines) == 1:
                self._engine_id = engines[0].get("id")
                return self._engine_id

            # Multiple engines visible — find the one owned by our integration.
            # Resolve integration UUID via the admin client.
            integration_uuid = await self._get_integration_uuid()
            if integration_uuid:
                for engine in engines:
                    if engine.get("integrationId") == integration_uuid:
                        self._engine_id = engine.get("id")
                        logger.info(
                            "nx_engine_resolved",
                            engine_id=self._engine_id,
                            integration_uuid=integration_uuid,
                        )
                        return self._engine_id
                logger.warning(
                    "nx_engine_not_found_for_integration",
                    integration_uuid=integration_uuid,
                    engines=[e.get("id") for e in engines],
                )

            # Fallback: first engine (may be wrong — log a warning)
            self._engine_id = engines[0].get("id")
            logger.warning(
                "nx_engine_fallback_to_first",
                engine_id=self._engine_id,
                total_engines=len(engines),
            )
            return self._engine_id
        except httpx.HTTPError as exc:
            logger.error("nx_get_engines_failed", error=str(exc))
        return None

    async def _get_integration_uuid(self) -> str | None:
        """Look up the Nx-internal UUID for our integration via the admin client.

        Matches the approved integration whose manifest integration ID equals
        our integration username (e.g. ``"DLStreamerAnalyticsIntegrationVMS"``).
        """
        if not self._client or not self._integration_username:
            return None
        try:
            resp = await self._client.get("/rest/v4/analytics/integrations")
            resp.raise_for_status()
            for item in resp.json():
                api_info = item.get("apiIntegrationInfo") or {}
                sdk_info = item.get("sdkIntegrationInfo") or {}
                if (
                    api_info.get("integrationId") == self._integration_username
                    or sdk_info.get("integrationId") == self._integration_username
                ):
                    return item.get("id")
        except httpx.HTTPError as exc:
            logger.warning("nx_get_integration_uuid_failed", error=str(exc))
        return None

    async def _ensure_device_agent_enabled(
        self, engine_id: str, device_id: str,
        device_agent_manifest: dict | None = None,
    ) -> bool:
        """Enable the device agent and push its manifest if not already done this session.

        Two steps are required before Nx will accept pushed metadata for a device:
          1. PATCH .../deviceAgents/{id}  → ``{"isEnabled": true}``
          2. POST  .../deviceAgents/{id}/manifest → declare supported object types

        Both calls are made once per device_id per process lifetime (cached in
        ``_enabled_device_agents``).
        """
        if device_id in self._enabled_device_agents:
            return True
        base_url = f"/rest/v4/analytics/engines/{engine_id}/deviceAgents/{device_id}"
        try:
            # Step 1: enable
            resp = await self._integration_client.patch(  # type: ignore[union-attr]
                base_url, json={"isEnabled": True},
            )
            if not resp.is_success:
                logger.warning(
                    "nx_device_agent_enable_failed",
                    status_code=resp.status_code,
                    device_id=device_id,
                    detail=resp.text[:200],
                )
                return False
            logger.info("nx_device_agent_enabled", engine_id=engine_id, device_id=device_id)

            # Step 2: push device agent manifest so Nx knows which types to expect
            manifest_payload = device_agent_manifest or {
                "supportedTypes": [{"objectTypeId": "python.detected.object"}],
            }
            resp = await self._integration_client.post(  # type: ignore[union-attr]
                f"{base_url}/manifest",
                json={"deviceAgentManifest": manifest_payload},
            )
            if resp.is_success:
                logger.info(
                    "nx_device_agent_manifest_pushed",
                    engine_id=engine_id,
                    device_id=device_id,
                )
            else:
                logger.warning(
                    "nx_device_agent_manifest_push_failed",
                    status_code=resp.status_code,
                    device_id=device_id,
                    detail=resp.text[:200],
                )
                # Non-fatal: proceed and let the push attempt reveal the true error.

            self._enabled_device_agents.add(device_id)
            return True
        except httpx.HTTPError as exc:
            logger.error("nx_device_agent_enable_error", error=str(exc), device_id=device_id)
            return False

    async def get_device_agent_settings(self, device_id: str) -> dict:
        """Read device agent settings set by the user in the Nx Witness client.

        Returns a dict with ``pipelineEnabled`` (bool) and ``pipelineName`` (str).
        """
        ready = await self._ensure_integration_session()
        if not ready:
            return {}

        engine_id = await self._get_engine_id()
        if not engine_id:
            return {}

        logger.debug("nx_get_device_agent_settings", device_id=device_id, engine_id=engine_id)
        try:
            resp = await self._integration_client.get(  # type: ignore[union-attr]
                f"/rest/v4/analytics/engines/{engine_id}/deviceAgents/{device_id}/settings"
            )
            resp.raise_for_status()
            data = resp.json()
            # Nx v4 wraps user-set values under "values"
            values = data.get("values", data)
            settings = {
                "pipelineEnabled": bool(values.get("pipelineEnabled", False)),
                "device": str(values.get("device", "CPU")),
            }
            logger.debug(
                "nx_device_agent_settings_read",
                device_id=device_id,
                pipeline_enabled=settings["pipelineEnabled"],
                device=settings["device"],
            )
            return settings
        except httpx.HTTPError as exc:
            logger.error("nx_get_device_agent_settings_failed", error=str(exc), device_id=device_id)
            return {}

    async def push_analytics_objects(
        self,
        device_id: str,
        objects: list[dict],
        timestamp_ms: int,
        duration_ms: int = 100,
    ) -> bool:
        """POST analytics objects to Nx for the given device.

        Authenticates as the integration user (lazily), discovers the engine ID
        (cached), enables the device agent for this device (once per session),
        then pushes the objects via the standard REST v4 endpoint.

        Args:
            device_id: Nx device UUID (without ``nx:`` prefix).
            objects: list of Nx object dicts (from ``translate_dls_metadata``).
            timestamp_ms: epoch milliseconds for the frame.
            duration_ms: frame duration hint (default 100 ms).

        Returns True on success, False on any failure.
        """
        if not objects:
            return True

        ready = await self._ensure_integration_session()
        if not ready:
            return False

        engine_id = await self._get_engine_id()
        if not engine_id:
            logger.error("nx_push_no_engine_id", device_id=device_id)
            return False

        await self._ensure_device_agent_enabled(engine_id, device_id)

        url = (
            f"/rest/v4/analytics/engines/{engine_id}"
            f"/deviceAgents/{device_id}/metadata/object"
        )
        payload: dict = {
            "flags": "none",
            "timestampMs": timestamp_ms,
            "durationMs": duration_ms,
            "objects": objects,
        }
        try:
            resp = await self._integration_client.post(url, json=payload)  # type: ignore[union-attr]
            if resp.is_success:
                return True
            logger.warning(
                "nx_push_objects_rejected",
                status_code=resp.status_code,
                device_id=device_id,
                detail=resp.text[:200],
            )
            # 401 → session expired; clear token so next call re-authenticates
            if resp.status_code == 401:
                self._integration_token = None
                self._integration_client = None
            return False
        except httpx.HTTPError as exc:
            logger.error("nx_push_objects_failed", error=str(exc), device_id=device_id)
            return False

    # -- Write-back -----------------------------------------------------
    async def acknowledge_event(
        self, camera_id: str, event_id: str, message: str = "",
    ) -> CommandResult:
        # Acknowledgement of analytics events is not part of the standard
        # /rest/v4 surface - it is plugin-specific in Nx. Return unsupported.
        return _unsupported("acknowledge_event", camera_id,
                            "Standard Nx v4 REST API has no event-acknowledgement endpoint")

    async def set_bookmark(
        self, camera_id: str, timestamp: datetime, label: str,
    ) -> CommandResult:
        if not self._client:
            return _unsupported("set_bookmark", camera_id, "Not connected")
        device_id = camera_id.removeprefix("nx:")
        try:
            resp = await self._client.post(
                f"/rest/v4/devices/{device_id}/bookmarks",
                json={
                    "name": label,
                    "description": f"VMS Plugin: {label}",
                    "startTimeMs": int(timestamp.timestamp() * 1000),
                    "durationMs": 30_000,
                },
            )
            return _result(camera_id, "set_bookmark",
                           "accepted" if resp.status_code in (200, 201, 204) else "rejected",
                           resp.text)
        except httpx.HTTPError as e:
            return _result(camera_id, "set_bookmark", "timeout", str(e))

    async def push_label(
        self, camera_id: str, event_id: str, labels: list[str],
        confidence: float | None = None,
    ) -> CommandResult:
        # The plugin maps labels to a bookmark - that is the only standard
        # storage surface available without an analytics engine plugin.
        return await self.set_bookmark(
            camera_id, datetime.utcnow(), ", ".join(labels),
        )

    async def trigger_recording(
        self, camera_id: str, duration_seconds: int = 30,
    ) -> CommandResult:
        if not self._client:
            return _unsupported("trigger_recording", camera_id, "Not connected")
        device_id = camera_id.removeprefix("nx:")
        try:
            # PATCH the device record to enable recording. Standard v4 surface.
            # v4 uses schedule.isEnabled rather than the v3 isRecording field.
            resp = await self._client.patch(
                f"/rest/v4/devices/{device_id}",
                json={"schedule": {"isEnabled": True}},
            )
            return _result(camera_id, "trigger_recording",
                           "accepted" if resp.status_code in (200, 204) else "rejected",
                           resp.text)
        except httpx.HTTPError as e:
            return _result(camera_id, "trigger_recording", "timeout", str(e))


# -- Helpers -------------------------------------------------------------

def _to_camera(d: dict, stream_url: str | None = None) -> Camera:
    nx_status = d.get("status", "")
    cam_status = "online" if nx_status in ("Online", "Recording") else "offline"
    # Nx Witness returns IDs with or without curly braces depending on version.
    # Normalise to bare UUID so camera_id is always nx:<uuid> without braces.
    raw_id = d.get("id", "")
    device_id = raw_id.strip("{}")
    return Camera(
        camera_id=f"nx:{device_id}",
        name=d.get("name", ""),
        vendor="nx_witness",
        status=cam_status,
        stream_url=stream_url or d.get("url"),
        enabled=False,
        vendor_meta=d,
    )


def _result(camera_id: str, ctype: str, status: str, msg: str) -> CommandResult:
    return CommandResult(
        command_id=str(uuid.uuid4()), camera_id=camera_id,
        command_type=ctype, status=status, vendor_message=msg,
    )


def _unsupported(ctype: str, camera_id: str, msg: str) -> CommandResult:
    return _result(ctype=ctype, camera_id=camera_id, status="unsupported", msg=msg)
