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

    # Alert Agent Service (external microservice for action dispatch)
    ALERT_AGENT_SERVICE_URL: str = os.getenv(
        "ALERT_AGENT_SERVICE_URL", "http://alert-agent-service:8000/api/v1"
    )
    ALERT_AGENT_SERVICE_TIMEOUT: float = _float("ALERT_AGENT_SERVICE_TIMEOUT", 30.0)

    ACTION_WORKERS: int = _int("ACTION_WORKERS", 2)

    MAX_STREAMS: int = _int("MAX_STREAMS", 4)
    ANALYSIS_INTERVAL: float = _float("ANALYSIS_INTERVAL", 2.0)
    FRAME_BUFFER_SIZE: int = _int("FRAME_BUFFER_SIZE", 3)
    CAPTURE_FPS: float = _float("CAPTURE_FPS", 5)  # frames decoded per second
    CAPTURE_RESIZE_HEIGHT: int = _int("CAPTURE_RESIZE_HEIGHT", 0)  # 0 = skip; VLM client resizes

    SNAPSHOT_DIR: str = os.getenv("SNAPSHOT_DIR", "snapshots")
    MCP_ENABLED: bool = _bool("MCP_ENABLED", True)
    MCP_CONFIG_FILE: str = os.getenv("MCP_CONFIG_FILE", "resources/mcp_servers.json")

     # Metrics Config
    METRICS_SERVICE_PORT: int = _int("METRICS_SERVICE_PORT", 9090)
    METRICS_NODEPORT: int = _int("METRICS_NODEPORT", 9090)


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
