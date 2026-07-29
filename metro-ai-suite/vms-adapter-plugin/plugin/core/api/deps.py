# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""API dependencies for FastAPI dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from plugin.core.db.session import get_session_factory

if TYPE_CHECKING:
    from plugin.core.config import AppConfig
    from plugin.core.factory import VmsShimSet
    from plugin.base.interfaces import IAnalyticsAppShim

# Module-level state set by the orchestrator at startup
_vms_shim_sets: list["VmsShimSet"] = []
_analytics_app_shims: dict[str, "IAnalyticsAppShim"] = {}
_app_config: "AppConfig | None" = None


def set_shims(
    vms_shim_sets: list["VmsShimSet"],
    analytics_app_shims: "dict[str, IAnalyticsAppShim] | IAnalyticsAppShim | None",
    app_config: "AppConfig",
) -> None:
    """Called by the orchestrator at startup to inject shim instances."""
    global _vms_shim_sets, _analytics_app_shims, _app_config
    _vms_shim_sets = vms_shim_sets
    if analytics_app_shims is None:
        _analytics_app_shims = {}
    elif isinstance(analytics_app_shims, dict):
        _analytics_app_shims = analytics_app_shims
    else:
        _analytics_app_shims = {analytics_app_shims.app_id: analytics_app_shims}
    _app_config = app_config


async def get_db_session():
    """Yield an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_vms_shim_sets():
    """Return the list of VMS shim sets."""
    return _vms_shim_sets


async def get_analytics_app_shims() -> "dict[str, IAnalyticsAppShim]":
    """Return the full ``{app_id: shim}`` Analytics App registry."""
    return _analytics_app_shims


def require_analytics_app_shim(app_id: str) -> "IAnalyticsAppShim":
    """Look up an Analytics App shim by id or raise 404."""
    shim = _analytics_app_shims.get(app_id)
    if shim is None:
        raise HTTPException(
            status_code=404,
            detail=f"Analytics app '{app_id}' is not registered",
        )
    return shim


async def get_app_config():
    """Return the application configuration."""
    return _app_config

