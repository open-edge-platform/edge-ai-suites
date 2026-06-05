# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""VMS Plugin Microservice :FastAPI application."""

import logging
import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI

from plugin.core.api.middleware import install_api_key_middleware
from plugin.core.api.routes import (
    analysis,
    cameras,
    config as config_routes,
    analytics_apps as analytics_apps_routes,
    events,
    health,
    sessions as sessions_routes,
    vms as vms_routes,
)
from plugin.core.config import load_config
from plugin.core.pipeline.orchestrator import init_orchestrator


def _configure_logging(level: str) -> None:
    """Apply the log level to stdlib logging and structlog."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric)
    logging.getLogger().setLevel(numeric)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
    )


# Apply log level as early as possible — before any module-level loggers emit.
try:
    _configure_logging(load_config().logging.level)
except SystemExit:
    _configure_logging("info")


@asynccontextmanager
async def lifespan(application: FastAPI):
    orchestrator = await init_orchestrator()
    await orchestrator.startup()
    yield
    await orchestrator.shutdown()


def create_app() -> FastAPI:
    application = FastAPI(
        title="VMS Plugin Microservice",
        description="I/O Plugin for VMS/VMS Integration with Analytics Apps",
        version="0.1.0",
        lifespan=lifespan,
    )

    try:
        cfg = load_config()
        install_api_key_middleware(application, cfg.api.api_key)
    except SystemExit:
        pass

    application.include_router(health.router, prefix="/v1", tags=["Health"])
    application.include_router(cameras.router, prefix="/v1", tags=["Cameras"])
    application.include_router(events.router, prefix="/v1", tags=["Events"])
    application.include_router(analysis.router, prefix="/v1", tags=["Analysis"])
    application.include_router(config_routes.router, prefix="/v1", tags=["Config"])
    application.include_router(vms_routes.router, prefix="/v1", tags=["VMS"])
    application.include_router(analytics_apps_routes.router, prefix="/v1")
    application.include_router(sessions_routes.router, prefix="/v1")
    return application


app = create_app()
