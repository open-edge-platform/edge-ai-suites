# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Application orchestrator : startup, shutdown, dependency wiring.

RTSP-only model: connect each VMS shim, register analytics manifest,
inject deps. Apps consume RTSP via /v1/cameras/{id}/live-stream and POST
results back to /v1/analysis/results.
"""

from __future__ import annotations

import asyncio

import structlog

from plugin.base.interfaces import IAnalyticsAppShim
from plugin.core.config import AppConfig, load_config
from plugin.core.db.session import close_db, init_db
from plugin.core.factory import VmsShimSet, ShimFactory

logger = structlog.get_logger(__name__)



class Orchestrator:
    def __init__(self, config: AppConfig):
        self.config = config
        self.vms_shim_sets: list[VmsShimSet] = []
        self.analytics_app_shims: dict[str, IAnalyticsAppShim] = {}
        self._shutdown_event = asyncio.Event()
        self._mqtt_tasks: list[asyncio.Task] = []

    async def startup(self) -> None:
        logger.info("orchestrator_starting")

        await init_db(self.config.database.url)
        logger.info("database_initialized")

        self.vms_shim_sets = ShimFactory.create_vms_shims(self.config)
        self.analytics_app_shims = ShimFactory.create_analytics_app_shims(self.config)

        # Wire VMS shims into analytics app shims that support Nx write-back (e.g. LVC).
        for shim in self.analytics_app_shims.values():
            if hasattr(shim, "set_vms_shims"):
                shim.set_vms_shims(self.vms_shim_sets)

        for ss in self.vms_shim_sets:
            try:
                await ss.vms_shim.connect()
            except Exception:
                logger.exception("vms_connect_failed", vms=ss.name)
                continue
            try:
                await ss.vms_shim.on_startup(self)
            except Exception:
                logger.exception("vms_startup_hook_failed", vms=ss.name)

        self._wire_analytics_app_resolvers()

        # Pre-fetch schemas so param_model is ready before the first /start call.
        for shim in self.analytics_app_shims.values():
            try:
                await shim.fetch_schema()
                logger.info("analytics_app_schema_fetched", app_id=shim.app_id)
            except Exception:
                logger.warning("analytics_app_schema_fetch_skipped", app_id=shim.app_id)

        from plugin.core.api.deps import set_shims
        set_shims(self.vms_shim_sets, self.analytics_app_shims, self.config)

        await self._reconcile_sessions()

        for shim in self.analytics_app_shims.values():
            try:
                await shim.on_startup(self)
            except Exception:
                logger.exception("analytics_app_startup_hook_failed", app_id=shim.app_id)

        logger.info("orchestrator_started", vms_count=len(self.vms_shim_sets))

    def add_background_task(self, task: asyncio.Task) -> None:
        """Register a background task for orderly cancellation on shutdown."""
        self._mqtt_tasks.append(task)

    def _wire_analytics_app_resolvers(self) -> None:
        """Inject an RTSP resolver that defers to IVmsShim.get_live_stream_url."""

        async def resolve_rtsp(camera_id: str) -> str | None:
            for ss in self.vms_shim_sets:
                if camera_id.startswith(ss.vms_shim.camera_id_prefix):
                    try:
                        url = await ss.vms_shim.get_live_stream_url(camera_id)
                        if url:
                            return url
                    except Exception:
                        logger.exception("rtsp_resolve_failed", camera_id=camera_id)
            return None

        for shim in self.analytics_app_shims.values():
            if hasattr(shim, "set_rtsp_resolver"):
                shim.set_rtsp_resolver(resolve_rtsp)

    async def _reconcile_sessions(self) -> None:
        """On startup, verify active sessions are still alive on their apps.

        Sessions whose app instance no longer exists are marked stopped.
        """
        from plugin.core.db.session import get_session_factory
        from plugin.core.db import repository as repo

        try:
            factory = get_session_factory()
        except RuntimeError:
            logger.warning("reconcile_skipped_no_db")
            return

        async with factory() as db:
            active = await repo.list_sessions(db, status="active")

        if not active:
            return

        logger.info("reconciling_sessions", count=len(active))

        for s in active:
            shim = self.analytics_app_shims.get(s.analytics_app_id)
            alive = False
            if shim and s.app_instance_id:
                try:
                    # Use get_run if available (LVC); fall back to is_reachable.
                    if hasattr(shim, "get_run"):
                        result = await shim.get_run(s.app_instance_id)
                        alive = result is not None
                    else:
                        alive = await shim.is_reachable()
                except Exception:
                    logger.exception("reconcile_check_failed", session_id=s.session_id)

            if not alive:
                async with factory() as db:
                    await repo.stop_session(db, s.session_id)
                logger.info(
                    "session_reconciled_stopped",
                    session_id=s.session_id,
                    camera_id=s.camera_id,
                    analytics_app_id=s.analytics_app_id,
                )
            else:
                logger.info(
                    "session_reconciled_active",
                    session_id=s.session_id,
                    camera_id=s.camera_id,
                )

    async def shutdown(self) -> None:
        logger.info("orchestrator_shutting_down")
        # Cancel all MQTT subscriber tasks (LVC + OD)
        for task in self._mqtt_tasks:
            task.cancel()
        if self._mqtt_tasks:
            await asyncio.gather(*self._mqtt_tasks, return_exceptions=True)
            logger.info("mqtt_subscribers_stopped", count=len(self._mqtt_tasks))
        for ss in self.vms_shim_sets:
            try:
                await ss.vms_shim.disconnect()
            except Exception:
                logger.exception("vms_disconnect_error", vms=ss.name)
        await close_db()
        logger.info("orchestrator_stopped")


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator | None:
    return _orchestrator


async def init_orchestrator(config_path: str | None = None) -> Orchestrator:
    global _orchestrator
    config = load_config(config_path)
    _orchestrator = Orchestrator(config)
    return _orchestrator
