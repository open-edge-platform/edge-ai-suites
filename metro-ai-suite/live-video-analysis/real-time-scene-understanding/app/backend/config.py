# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Runtime configuration loaded from environment variables."""

import logging
import os
import re


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


def _bool(key: str, default: bool) -> bool:
    val = os.getenv(key, "")
    if not val:
        return default
    return val.strip().lower() in ("1", "true", "yes")


def _frame_size(key: str) -> tuple[int, int] | None:
    raw = os.getenv(key, "").strip()
    if not raw:
        return None

    match = re.fullmatch(r"(\d+)\s*[xX,]\s*(\d+)", raw)
    if not match:
        logging.getLogger(__name__).warning(
            "Invalid %s='%s'; expected WIDTHxHEIGHT (for example 640x360)",
            key,
            raw,
        )
        return None

    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        logging.getLogger(__name__).warning(
            "Invalid %s='%s'; width/height must be positive integers",
            key,
            raw,
        )
        return None
    return (width, height)


def _frame_size_default(key: str, default: tuple[int, int]) -> tuple[int, int]:
    parsed = _frame_size(key)
    return parsed if parsed is not None else default


class Settings:
    # ---- server ----
    DASHBOARD_PORT: int = _int("DASHBOARD_PORT", 9100)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ---- stream source ----
    # Socket open/read timeout in seconds for PyAV.
    RTSP_TIMEOUT: float = _float("RTSP_TIMEOUT", 15.0)

    # ---- WebRTC rendering (via MediaMTX relay) ----
    # When true, each source is remuxed (stream-copy) into MediaMTX with PyAV
    # so the browser can subscribe over WebRTC (WHEP).
    WEBRTC_AUTO_PUBLISH: bool = _bool("WEBRTC_AUTO_PUBLISH", True)

    # RTSP base URL of the MediaMTX server the relay publishes to.
    # The stream id is appended as the path, e.g. rtsp://mediamtx:8554/default.
    WEBRTC_RELAY_URL: str = os.getenv("WEBRTC_RELAY_URL", "rtsp://mediamtx:8554")

    # Public WebRTC (WHEP) signaling base the browser connects to. When empty
    # the UI derives it from the page host and WEBRTC_SIGNALING_PORT.
    WEBRTC_SIGNALING_URL: str = os.getenv("WEBRTC_SIGNALING_URL", "")
    WEBRTC_SIGNALING_PORT: int = _int("WEBRTC_SIGNALING_PORT", 8889)

    # Metrics-manager SSE port used by the UI device-usage panel.
    METRICS_SERVICE_PORT: int = _int("METRICS_SERVICE_PORT", 9090)

    # ---- VLM inference (OpenVINO GenAI) Configuration for Alert Pipeline ----
    # Each stream decodes sampled frames and captions them with the
    # OpenVINO GenAI VLM pipeline.

    # Root of the mounted model tree. Fixed to /models to match container
    # volume mounts and shared by both VLM and deep-analyzer pipelines.
    # Models are organised as
    # <VLM_MODELS_DIR>/<device>/<VLM_MODEL>, e.g. /models/cpu/InternVL2-1B.
    VLM_MODELS_DIR: str = "/models"
    ALERT_VLM_MODEL: str = os.getenv("ALERT_VLM_MODEL", "InternVL2-1B")

    # Inference device: CPU, GPU or NPU (selects the matching model subfolder).
    ALERT_VLM_DEVICE: str = os.getenv("ALERT_VLM_DEVICE", "NPU")

    # Seconds between inferences per stream and the token budget per caption.
    ALERT_VLM_INTERVAL: float = _float("ALERT_VLM_INTERVAL", 2.0)
    ALERT_VLM_MAX_TOKENS: int = _int("ALERT_VLM_MAX_TOKENS", 32)
    ALERT_VLM_DO_SAMPLE: bool = _bool("ALERT_VLM_DO_SAMPLE", False)

    # VLM NPU-specific configuration. Only used when runnning VLM inference on NPU device.
    NPU_MAX_PROMPT_LEN = _int("NPU_MAX_PROMPT_LEN", 1024)
    NPU_MIN_RESPONSE_LEN = _int("NPU_MIN_RESPONSE_LEN", 512)

    # Benchmarked segment recording (encode) dimensions per source aspect
    # ratio bucket; the closest bucket to the source's aspect ratio is used
    # (see _calculate_scaled_dimensions in stream_manager.py). This sets the
    # .mp4 encode resolution. Format: WIDTHxHEIGHT.
    SEGMENT_DIM_1_1: tuple[int, int] = _frame_size_default("SEGMENT_DIM_1_1", (448, 448))
    SEGMENT_DIM_4_3: tuple[int, int] = _frame_size_default("SEGMENT_DIM_4_3", (512, 384))
    SEGMENT_DIM_16_9: tuple[int, int] = _frame_size_default("SEGMENT_DIM_16_9", (576, 320))

    # Max number of concurrent streams the registry will accept.
    MAX_STREAMS: int = _int("MAX_STREAMS", 8)

    # Hard cap on finalized segments retained on disk per stream; oldest is
    # deleted once a new segment finalizes and pushes the count over this.
    # 0 disables the cap (unbounded). Retained video per stream is roughly
    # SEGMENT_MAX_ON_DISK * SEGMENT_TIME_SECONDS seconds (default: 50 * 15s = 750s / ~12.5 min).
    SEGMENT_MAX_ON_DISK: int = _int("SEGMENT_MAX_ON_DISK", 50)

    # ---- Segment writer + frame metadata registry (for deep-analysis handoff) ----
    # Directory where rolling .mp4 segments are written, per stream.
    SEGMENT_OUTPUT_DIR: str = os.getenv("SEGMENT_OUTPUT_DIR", "segments")

    # Length of each rolling segment file, in seconds.
    SEGMENT_TIME_SECONDS: int = _int("SEGMENT_TIME_SECONDS", 15)

    # Frames per second registered into the metadata registry, per stream.
    FRAME_SAMPLE_FPS: int = _int("FRAME_SAMPLE_FPS", 1)

    # Fixed per-stream cap on frame metadata records kept in memory; a stream's
    # own oldest record is evicted once it exceeds this, independent of other streams.
    # One record per sampled frame, so retained history is roughly
    # FRAME_REGISTRY_MAX_RECORDS_PER_STREAM / FRAME_SAMPLE_FPS seconds
    # (default: 500 / 1fps = 500s / ~8.3 min).
    FRAME_REGISTRY_MAX_RECORDS_PER_STREAM: int = _int("FRAME_REGISTRY_MAX_RECORDS_PER_STREAM", 500)

    # ---- Deep analyzer (multi-frame follow-up on a "Yes" alert verdict) ----
    # When true, a segment whose sampled frame gets a "Yes" verdict from the
    # fast VLM is handed to a second, video-capable model for a richer,
    # multi-frame confirmation. Independent pipeline/device from VLM_*.
    DEEP_ANALYZER_ENABLED: bool = _bool("DEEP_ANALYZER_ENABLED", True)

    # Model tree layout reuses VLM_MODELS_DIR:
    # <VLM_MODELS_DIR>/<device>/<DEEP_ANALYZER_MODEL>.
    DEEP_ANALYZER_MODEL: str = os.getenv("DEEP_ANALYZER_MODEL", "Qwen3.5-2B-int4-ov")
    DEEP_ANALYZER_DEVICE: str = os.getenv("DEEP_ANALYZER_DEVICE", "GPU")

    # Frames uniformly sampled from a finalized segment per deep-analysis run.
    DEEP_ANALYZER_MAX_FRAMES: int = _int("DEEP_ANALYZER_MAX_FRAMES", 8)
    DEEP_ANALYZER_MAX_TOKENS: int = _int("DEEP_ANALYZER_MAX_TOKENS", 128)

    # PyAV pixel format for sampled segment frames. Qwen3.5 (like every VLM
    # preprocessor) expects RGB; feeding BGR swaps red/blue and produces
    # confident but wrong descriptions.
    DEEP_ANALYZER_FRAME_FORMAT: str = os.getenv("DEEP_ANALYZER_FRAME_FORMAT", "rgb24")

    # ---- Deep analyzer decoding controls ----
    # Greedy decoding by default so the same segment yields the same summary.
    # Sampling params below only apply when DEEP_ANALYZER_DO_SAMPLE=true.
    DEEP_ANALYZER_DO_SAMPLE: bool = _bool("DEEP_ANALYZER_DO_SAMPLE", False)
    DEEP_ANALYZER_TEMPERATURE: float = _float("DEEP_ANALYZER_TEMPERATURE", 0.1)
    DEEP_ANALYZER_TOP_P: float = _float("DEEP_ANALYZER_TOP_P", 0.8)
    DEEP_ANALYZER_TOP_K: int = _int("DEEP_ANALYZER_TOP_K", 20)

    # Greedy decoding loops on repeated phrases without these (see
    # poc/ovms-deep-analyzer comparison notes).
    DEEP_ANALYZER_REPETITION_PENALTY: float = _float("DEEP_ANALYZER_REPETITION_PENALTY", 1.3)
    DEEP_ANALYZER_NO_REPEAT_NGRAM_SIZE: int = _int("DEEP_ANALYZER_NO_REPEAT_NGRAM_SIZE", 3)

    # Allow EOS as soon as the structured response is complete.
    DEEP_ANALYZER_MIN_TOKENS: int = _int("DEEP_ANALYZER_MIN_TOKENS", 0)
    DEEP_ANALYZER_STRUCTURED_OUTPUT: bool = _bool("DEEP_ANALYZER_STRUCTURED_OUTPUT", True)

    # Deep-analyzer NPU-specific configuration. Only used when
    # DEEP_ANALYZER_DEVICE=NPU (mirrors NPU_MAX_PROMPT_LEN/NPU_MIN_RESPONSE_LEN above).
    DEEP_ANALYZER_NPU_MAX_PROMPT_LEN = _int("DEEP_ANALYZER_NPU_MAX_PROMPT_LEN", 4096)
    DEEP_ANALYZER_NPU_MIN_RESPONSE_LEN = _int("DEEP_ANALYZER_NPU_MIN_RESPONSE_LEN", 512)

    # Bounded cache size for the dedup/finalized-segment tracking sets in
    # backend.services.deep_analyzer (per-process, not per-stream).
    DEEP_ANALYZER_DEDUP_CACHE_SIZE: int = _int("DEEP_ANALYZER_DEDUP_CACHE_SIZE", 500)

    # The "finalized" signal is a best-effort prediction (see
    # StreamManager._notify_segment_finalized) — the muxer may not have
    # flushed the segment's trailer to disk yet when it fires. Retries give
    # that a moment to catch up before giving up on the segment.
    DEEP_ANALYZER_SEGMENT_READ_MAX_RETRIES: int = _int("DEEP_ANALYZER_SEGMENT_READ_MAX_RETRIES", 5)
    DEEP_ANALYZER_SEGMENT_READ_RETRY_DELAY: float = _float("DEEP_ANALYZER_SEGMENT_READ_RETRY_DELAY", 1.0)

    # ---- SeaweedFS object storage (S3-compatible) ----
    # Deep-analyzer uploads finalized segment videos and stores
    # deep-analysis metadata on the uploaded object.
    SEAWEEDFS_ENDPOINT_URL: str = os.getenv("SEAWEEDFS_ENDPOINT_URL", "http://seaweedfs:8333")
    SEAWEEDFS_ACCESS_KEY: str = os.getenv("SEAWEEDFS_ACCESS_KEY", "sceneadmin")
    SEAWEEDFS_SECRET_KEY: str = os.getenv("SEAWEEDFS_SECRET_KEY", "sceneadmin123")
    SEAWEEDFS_BUCKET: str = os.getenv("SEAWEEDFS_BUCKET", "real-time-scene-understanding")
    SEAWEEDFS_USE_SSL: bool = _bool("SEAWEEDFS_USE_SSL", False)
    SEAWEEDFS_VERIFY_SSL: bool = _bool("SEAWEEDFS_VERIFY_SSL", False)
    # S3 lifecycle retention applies to SeaweedFS and AWS S3-compatible endpoints.
    S3_RETENTION_DAYS: int = _int("S3_RETENTION_DAYS", 10)
    SEAWEEDFS_UPLOAD_RETRIES: int = 3
    SEAWEEDFS_RETRY_DELAY_SECONDS: float = 1.0
    SEAWEEDFS_MAX_RETRY_DELAY_SECONDS: float = _float("SEAWEEDFS_MAX_RETRY_DELAY_SECONDS", 2.0)
    SEAWEEDFS_MAX_POOL_CONNECTIONS: int = _int("SEAWEEDFS_MAX_POOL_CONNECTIONS", 20)

    # ---- Alert index (in-memory, per-stream audit log of uploaded alerts) ----
    # Bounded per-stream history kept in memory; oldest entries are dropped
    # once exceeded. Rehydrated from SeaweedFS (analysis.json sidecars) on
    # first access per stream, since the index itself isn't persisted.
    ALERT_INDEX_MAX_PER_STREAM: int = _int("ALERT_INDEX_MAX_PER_STREAM", 200)


settings = Settings()


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("libav", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
