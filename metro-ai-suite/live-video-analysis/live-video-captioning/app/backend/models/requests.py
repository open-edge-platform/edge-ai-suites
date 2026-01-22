# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator
from ..config import AGENT_MODE
import re
import ipaddress

# Default prompts based on mode
DEFAULT_PROMPT = (
    "Is there an accident in the stream? Just Answer with a Yes or No"
    if AGENT_MODE
    else "Describe what you see in one sentence."
)


class StartRunRequest(BaseModel):
    rtspUrl: str = Field(..., min_length=1, description="Valid RTSP URL")
    prompt: str = Field(default=DEFAULT_PROMPT)
    detectionModelName: Optional[str] = Field(default="yolov8s")
    detectionThreshold: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)
    modelName: str = Field(default="OpenGVLab/InternVL2-2B")
    maxNewTokens: int = Field(default=70, ge=1, le=4096)
    pipelineName: Optional[str] = Field(default=None)
    runName: Optional[str] = Field(default=None)

    @field_validator('rtspUrl')
    @classmethod
    def validate_rtsp_url(cls, v: str) -> str:
        try:
            # Basic format check first
            if not v.lower().startswith(('rtsp://', 'rtsps://')):
                raise ValueError('RTSP URL must start with rtsp:// or rtsps://')

            parsed = urlparse(v)

            # Check if hostname is present
            if not parsed.hostname:
                raise ValueError('RTSP URL must contain a valid hostname')

            hostname = parsed.hostname

            # Check if it's an IP address (IPv4 or IPv6)
            try:
                ipaddress.ip_address(hostname)
                # Valid IP address
                return v
            except ValueError:
                pass

            # For domain names, require at least one dot (FQDN)
            if '.' not in hostname:
                raise ValueError('Hostname must be a valid IP address or fully qualified domain name (e.g., camera.example.com)')

            # Basic domain name validation
            # Allow letters, numbers, hyphens, and dots
            if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$', hostname):
                raise ValueError('Invalid hostname format')

            # Check that it doesn't end with a dot
            if hostname.endswith('.'):
                raise ValueError('Hostname cannot end with a dot')

            return v
        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            raise ValueError(f'Invalid RTSP URL format: {str(e)}')