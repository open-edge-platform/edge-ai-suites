# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Metrics Service - A reusable microservice for system metrics collection and relay.

This service provides:
1. WebSocket relay for metrics from collectors (Telegraf) to clients
2. REST API endpoints for health and status checks

The service is designed to be deployed alongside any application that needs
system metrics visualization.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import LOG_LEVEL, CORS_ORIGINS
from .relay import router as relay_router
from .routes import router as health_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("live-metrics-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    logger.info("Starting Metrics Service...")
    yield
    logger.info("Shutting down Metrics Service...")


app = FastAPI(
    title="Metrics Service",
    description="A reusable microservice for system metrics collection and relay",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(relay_router)
app.include_router(health_router)


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Metrics Service",
        "version": "1.0.0",
        "description": "A reusable microservice for system metrics collection and relay",
        "endpoints": {
            "websocket_collector": "/ws/collector",
            "websocket_clients": "/ws/clients",
            "health": "/health",
            "health_detailed": "/api/health",
        },
    }


if __name__ == "__main__":
    import uvicorn
    from .config import METRICS_PORT

    uvicorn.run("app.main:app", host="0.0.0.0", port=METRICS_PORT, reload=True)
