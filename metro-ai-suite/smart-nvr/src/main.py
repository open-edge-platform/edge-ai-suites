# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from service.directory_watcher import restore_camera_watchers_from_redis
from utils.utils import upload_videos_to_dataprep
from fastapi import FastAPI
from api.router import router  # your custom route logic (rules, results, etc.)
from service.mqtt_listener import start_mqtt_clients
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
    await start_mqtt_clients()

    # Start the camera watcher manager (restore from Redis)
    logger.info("[Watcher] Restoring camera watchers from Redis and starting directory watcher(s)...")
    try:
        # Provide action callback so restored watcher can process files
        await restore_camera_watchers_from_redis(action=upload_videos_to_dataprep, debounce_time=5, request=None)
        logger.info("[Watcher] Camera watcher manager started successfully.")
    except Exception as e:
        logger.error(f"[Watcher] Failed to start camera watcher manager: {e}")


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
