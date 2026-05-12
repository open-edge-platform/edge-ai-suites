# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import logging


def _bool(key: str, default: bool) -> bool:
    val = os.getenv(key, "")
    if not val:
        return default
    return val.strip().lower() in ("1", "true", "yes")


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


class Settings:
    PORT: int = _int("PORT", 9000)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    RTSP_URL: str = os.getenv("RTSP_URL", "")
    VLM_URL: str = os.getenv("VLM_URL", "http://ovms-vlm:8000/v3")
    OVMS_SOURCE_MODEL: str = os.getenv("OVMS_SOURCE_MODEL", "OpenVINO/Phi-3.5-vision-instruct-int4-ov")
    MODEL_NAME: str =OVMS_SOURCE_MODEL.split("/")[-1]  # e.g. "Phi-3.5-vision-instruct-int4-ov"
    VLM_IMAGE_MAX_DIM: int = _int("VLM_IMAGE_MAX_DIM", 224)
    VLM_JPEG_QUALITY: int = _int("VLM_JPEG_QUALITY", 60)
    VLM_TIMEOUT: float = _float("VLM_TIMEOUT", 45.0)
    VLM_MAX_RETRIES: int = _int("VLM_MAX_RETRIES", 1)
    VLM_MAX_TOKENS: int = _int("VLM_MAX_TOKENS", 128)
    VLM_MAX_CONCURRENCY: int = _int("VLM_MAX_CONCURRENCY", 1)
    VLM_ALERTS_PER_CALL: int = _int("VLM_ALERTS_PER_CALL", 1)  # max alerts batched per VLM call

    ACTION_WORKERS: int = _int("ACTION_WORKERS", 2)

    MAX_STREAMS: int = _int("MAX_STREAMS", 4)
    ANALYSIS_INTERVAL: float = _float("ANALYSIS_INTERVAL", 2.0)
    FRAME_BUFFER_SIZE: int = _int("FRAME_BUFFER_SIZE", 3)
    CAPTURE_FPS: float = _float("CAPTURE_FPS", 5)  # frames decoded per second
    CAPTURE_RESIZE_HEIGHT: int = _int("CAPTURE_RESIZE_HEIGHT", 0)  # 0 = skip; VLM client resizes
    
    USE_ADK: bool = _bool("USE_ADK", True)

    LLM_URL: str = os.getenv("LLM_URL", "http://ovms-llm:8000/v3")
    LLM_REPO: str = os.getenv("LLM_MODEL", "Openvino/Phi-4-mini-instruct-int4-ov")
    LLM_MODEL: str = LLM_REPO.split("/")[-1]  # e.g. "Phi-4-mini-instruct"
    LLM_TIMEOUT: float = _float("LLM_TIMEOUT", 10.0)

    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    # HMAC-SHA256 secret to sign webhook payloads (optional)
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")

    MQTT_BROKER: str = os.getenv("MQTT_BROKER", "")
    MQTT_PORT: int = _int("MQTT_PORT", 1883)
    MQTT_USERNAME: str = os.getenv("MQTT_USERNAME", "")
    MQTT_PASSWORD: str = os.getenv("MQTT_PASSWORD", "")
    MQTT_BASE_TOPIC: str = os.getenv("MQTT_BASE_TOPIC", "live-video-alerts")

    SNAPSHOT_DIR: str = os.getenv("SNAPSHOT_DIR", "snapshots")
    MCP_ENABLED: bool = _bool("MCP_ENABLED", True)
    MCP_CONFIG_FILE: str = os.getenv("MCP_CONFIG_FILE", "resources/mcp_servers.json")

     # Metrics Config
    METRICS_SERVICE_URL: str = os.getenv("METRICS_SERVICE_URL", "ws://localhost:9090")
    METRICS_NODEPORT: int = int(os.getenv("METRICS_NODEPORT", 9090))


settings = Settings()


def setup_logging():
    """Configure structured logging for production."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "multipart", "uvicorn.access", "paho"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
