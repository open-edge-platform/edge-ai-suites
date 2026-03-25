# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path


def _read_non_negative_int(var_name: str, default: int) -> int:
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return default

APP_PORT = int(os.environ.get("DASHBOARD_PORT", "4173"))
PEER_ID = os.environ.get("WEBRTC_PEER_ID", "genai_pipeline")
SIGNALING_URL = os.environ.get("SIGNALING_URL", "http://localhost:8889")
WEBRTC_BITRATE = int(os.environ.get("WEBRTC_BITRATE", "2048"))
ALERT_MODE = os.environ.get("ALERT_MODE", "false").lower() in ("true", "1", "yes")
DEFAULT_RTSP_URL = os.environ.get("DEFAULT_RTSP_URL", "")
ENABLE_DETECTION_PIPELINE = os.environ.get(
    "ENABLE_DETECTION_PIPELINE", "false"
).lower() in ("true", "1", "yes")
CAPTION_HISTORY = _read_non_negative_int("CAPTION_HISTORY", 3)

# Metrics Service Configuration
METRICS_SERVICE_PORT = os.environ.get("METRICS_SERVICE_PORT", "9090")

# MQTT Configuration
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "mqtt-broker")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "live-video-captioning")

PIPELINE_SERVER_URL = os.environ.get(
    "PIPELINE_SERVER_URL", "http://dlstreamer-pipeline-server:8080"
)
PIPELINE_NAME = os.environ.get("PIPELINE_NAME", "genai_pipeline")

BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = Path(os.environ.get("MODELS_DIR", str(BASE_DIR / "ov_models")))
DETECTION_MODELS_DIR = Path(
    os.environ.get("DETECTION_MODELS_DIR", str(BASE_DIR / "ov_detection_models"))
)
UI_DIR = BASE_DIR / "ui"

# Host Server Configuration
LIVE_VIDEO_RAG_HOST_PORT = int(os.environ.get("LIVE_VIDEO_RAG_HOST_PORT", "4172"))
EMBEDDING_API_URL = os.environ.get(
    "EMBEDDING_API_URL", f"http://live-video-captioning-rag:{LIVE_VIDEO_RAG_HOST_PORT}/api/embedding"
)

# Embedding/Vector Database Configuration
VDMS_HOST = os.getenv("VDMS_HOST", "localhost")
VDMS_PORT = int(os.getenv("VDMS_PORT", "5555"))
EMBEDDING_HOST = os.getenv("EMBEDDING_HOST", "localhost")
EMBEDDING_HOST_PORT = int(os.getenv("EMBEDDING_HOST_PORT", "5000"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "")
ENABLE_EMBEDDING = os.environ.get("ENABLE_EMBEDDING", "false").lower() in ("true", "1", "yes")
EMBEDDING_LENGTH: int = 0

# Proxy settings
NO_PROXY_ENV = os.environ.get("no_proxy", "")  # Comma-separated domains for no-proxy
HTTP_PROXY = os.environ.get("http_proxy", "")
HTTPS_PROXY = os.environ.get("https_proxy", "")