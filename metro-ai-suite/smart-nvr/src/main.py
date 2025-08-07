# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from fastapi import FastAPI
from api.router import router  # your custom route logic (rules, results, etc.)
from service.mqtt_listener import start_mqtt
import asyncio
import logging
from config import REDIS_HOST, REDIS_PORT
import redis.asyncio as redis

# Configure global logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Create FastAPI app instance
app = FastAPI(
    title="NVR Event Router",
    version="1.0.0",
    description="FastAPI app to interface with Frigate and handle event routing",
)

# Register API routes
app.include_router(router)


# Run MQTT listener in background when FastAPI starts
@app.on_event("startup")
async def startup_event():
    app.state.redis_client = redis.from_url(
        f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True
    )
    logger.info("🚀 FastAPI starting up... launching MQTT listener")
    asyncio.create_task(start_mqtt())


@app.on_event("shutdown")
async def shutdown_event():
    await app.state.redis_client.close()


@app.get("/")
async def root():
    return {"message": "NVR Event Router is running!"}


# Optional: if running directly (not from Docker or uvicorn CLI)
if __name__ == "__main__":
    import uvicorn

    logger.info("🔥 Running FastAPI app via uvicorn...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="debug")
