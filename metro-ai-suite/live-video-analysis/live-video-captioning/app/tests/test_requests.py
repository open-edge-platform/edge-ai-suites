# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.models.requests, StartRunRequest validation."""

import pytest
from pydantic import ValidationError
from backend.models.requests import StartRunRequest


# ---------------------------------------------------------------------------
# Valid RTSP URLs
# ---------------------------------------------------------------------------
class TestStartRunRequestValid:
    """Happy-path validation for StartRunRequest."""

    def test_minimal_valid_request(self):
        """A request with only a valid RTSP URL uses all defaults."""
        req = StartRunRequest(rtspUrl="rtsp://192.168.1.10:554/stream")
        assert req.rtspUrl == "rtsp://192.168.1.10:554/stream"
        assert req.maxNewTokens == 70
        assert req.modelName == "OpenGVLab/InternVL2-2B"

    def test_rtsps_scheme_accepted(self):
        """rtsps:// scheme is accepted as valid."""
        req = StartRunRequest(rtspUrl="rtsps://10.0.0.1/cam")
        assert req.rtspUrl.startswith("rtsps://")

    def test_ipv4_host(self):
        """IPv4 addresses are valid hostnames."""
        req = StartRunRequest(rtspUrl="rtsp://10.0.0.1/stream")
        assert req.rtspUrl == "rtsp://10.0.0.1/stream"

    def test_ipv6_host(self):
        """IPv6 addresses (bracket-wrapped) are valid hostnames."""
        req = StartRunRequest(rtspUrl="rtsp://[::1]:554/stream")
        assert "::1" in req.rtspUrl

    def test_fqdn_host(self):
        """Fully qualified domain names are accepted."""
        req = StartRunRequest(rtspUrl="rtsp://camera.example.com/live")
        assert req.rtspUrl == "rtsp://camera.example.com/live"

    def test_custom_fields(self):
        """All optional fields can be customised."""
        req = StartRunRequest(
            rtspUrl="rtsp://10.0.0.1/stream",
            prompt="What is happening?",
            modelName="custom-model",
            maxNewTokens=200,
            detectionModelName="yolov5",
            detectionThreshold=0.8,
            pipelineName="my_pipe",
            runName="demo_run",
        )
        assert req.prompt == "What is happening?"
        assert req.modelName == "custom-model"
        assert req.maxNewTokens == 200
        assert req.detectionModelName == "yolov5"
        assert req.detectionThreshold == 0.8
        assert req.pipelineName == "my_pipe"
        assert req.runName == "demo_run"


# ---------------------------------------------------------------------------
# Invalid RTSP URLs
# ---------------------------------------------------------------------------
class TestStartRunRequestInvalidUrl:
    """Validation errors for malformed RTSP URLs."""

    def test_empty_url_rejected(self):
        """An empty string is rejected (min_length=1 + scheme check)."""
        with pytest.raises(ValidationError):
            StartRunRequest(rtspUrl="")

    def test_http_scheme_rejected(self):
        """HTTP scheme is not a valid RTSP URL."""
        with pytest.raises(ValidationError, match="rtsp://"):
            StartRunRequest(rtspUrl="http://example.com/stream")

    def test_no_hostname_rejected(self):
        """RTSP URL without a hostname is rejected."""
        with pytest.raises(ValidationError, match="hostname"):
            StartRunRequest(rtspUrl="rtsp:///no-host")

    def test_bare_hostname_without_dot_rejected(self):
        """Single-label hostnames (no dot) are rejected for domain names."""
        with pytest.raises(ValidationError, match="qualified domain"):
            StartRunRequest(rtspUrl="rtsp://localhost/stream")


# ---------------------------------------------------------------------------
# Field boundary checks
# ---------------------------------------------------------------------------
class TestStartRunRequestBoundaries:
    """Boundary and edge-case validation on numeric fields."""

    def test_max_new_tokens_minimum(self):
        """maxNewTokens must be >= 1."""
        with pytest.raises(ValidationError):
            StartRunRequest(rtspUrl="rtsp://10.0.0.1/s", maxNewTokens=0)

    def test_max_new_tokens_maximum(self):
        """maxNewTokens must be <= 4096."""
        with pytest.raises(ValidationError):
            StartRunRequest(rtspUrl="rtsp://10.0.0.1/s", maxNewTokens=5000)

    def test_detection_threshold_below_zero(self):
        """detectionThreshold must be >= 0.0."""
        with pytest.raises(ValidationError):
            StartRunRequest(rtspUrl="rtsp://10.0.0.1/s", detectionThreshold=-0.1)

    def test_detection_threshold_above_one(self):
        """detectionThreshold must be <= 1.0."""
        with pytest.raises(ValidationError):
            StartRunRequest(rtspUrl="rtsp://10.0.0.1/s", detectionThreshold=1.1)

    @pytest.mark.parametrize("threshold", [0.0, 0.5, 1.0])
    def test_detection_threshold_valid_range(self, threshold):
        """Valid thresholds within [0.0, 1.0] are accepted."""
        req = StartRunRequest(rtspUrl="rtsp://10.0.0.1/s", detectionThreshold=threshold)
        assert req.detectionThreshold == threshold
