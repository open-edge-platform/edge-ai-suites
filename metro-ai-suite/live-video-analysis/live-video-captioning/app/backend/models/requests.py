# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator
from ..config import ALERT_MODE
import re
import ipaddress

# Default prompts based on mode
DEFAULT_PROMPT = (
    "Is there an accident in the stream? Just Answer with a Yes or No"
    if ALERT_MODE
    else "Describe what you see in one sentence."
)


class StartRunRequest(BaseModel):
    rtspUrl: str = Field(
        ...,
        min_length=1,
        description="Valid RTSP URL or Linux video device path (for example /dev/video0)",
    )
    streamSourceType: Optional[str] = Field(
        default=None,
        description="Optional stream source type selector from UI (rtsp or camera).",
    )
    pipelineType: Optional[str] = Field(
        default=None,
        description="Optional pipeline family selector from UI (detection or non-detection).",
    )
    modelName: str = Field(default="InternVL2-1B", description="Vision-language model name to use for caption generation.")
    vlmDevice: str = Field(default="CPU", description="Device target for the VLM inference backend (for example CPU, GPU, or NPU).")
    maxNewTokens: int = Field(default=70, ge=1, le=4096, description="Maximum number of tokens generated per caption response.")
    prompt: str = Field(default=DEFAULT_PROMPT, description="Prompt sent to the captioning model for each processed frame/chunk.")
    detectionModelName: Optional[str] = Field(default="yolov8s", description="Object detection model name used in the pipeline.")
    detectionThreshold: Optional[float] = Field(default=0.5, ge=0.0, le=1.0, description="Confidence threshold for filtering detection results.")
    runName: Optional[str] = Field(default=None, description="Optional human-readable name for the run/session.")
    frameRate: Optional[int] = Field(default=None, ge=0, description="Optional output frame rate limit in frames per second; 0 disables frame processing.")
    chunkSize: Optional[int] = Field(default=None, ge=1, description="Optional number of frames grouped together for a single captioning request.")
    frameWidth: Optional[int] = Field(
        default=None,
        ge=1,
        description="Optional output frame width. If omitted, source width is used."
    )
    frameHeight: Optional[int] = Field(
        default=None,
        ge=1,
        description="Optional output frame height. If omitted, source height is used."
    )
    detectionDevice: Optional[str] = Field(default=None, description="Optional device target for object detection inference (for example CPU, GPU, or NPU).")
    includeRoiBoundingBox: Optional[bool] = Field(default=False, description="Whether to include ROI bounding-box metadata in pipeline outputs.")
    @field_validator("rtspUrl")
    @classmethod
    def validate_rtsp_url(cls, v: str) -> str:
        source = (v or "").strip()

        # Allow Linux V4L2 camera devices, e.g. /dev/video0.
        if source.startswith("/dev/video") and source[len("/dev/video") :].isdigit():
            return source

        try:
            # Basic format check first
            if not source.lower().startswith(("rtsp://", "rtsps://")):
                raise ValueError(
                    "Source must be an RTSP URL (rtsp:// or rtsps://) or /dev/videoN"
                )

            parsed = urlparse(source)

            # Check if hostname is present
            if not parsed.hostname:
                raise ValueError("RTSP URL must contain a valid hostname")

            hostname = parsed.hostname

            # Check if it's an IP address (IPv4 or IPv6)
            try:
                ipaddress.ip_address(hostname)
                # Valid IP address
                return source
            except ValueError:
                pass

            # Accept valid DNS hostnames, including single-label service names
            if not re.match(
                r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$",
                hostname,
            ):
                raise ValueError("Invalid hostname format")

            # Check that it doesn't end with a dot
            if hostname.endswith("."):
                raise ValueError("Hostname cannot end with a dot")

            return source
        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            raise ValueError(f"Invalid RTSP URL format: {str(e)}")

    @field_validator("streamSourceType")
    @classmethod
    def validate_stream_source_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip().lower()
        if value not in {"rtsp", "camera"}:
            raise ValueError("streamSourceType must be either 'rtsp' or 'camera'")
        return value

    @field_validator("pipelineType")
    @classmethod
    def validate_pipeline_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip().lower()
        if value not in {"detection", "non-detection"}:
            raise ValueError("pipelineType must be either 'detection' or 'non-detection'")
        return value
