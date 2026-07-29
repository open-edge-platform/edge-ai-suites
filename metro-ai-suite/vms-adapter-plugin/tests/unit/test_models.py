# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for Pydantic domain models."""

from datetime import datetime

from plugin.core.models.domain import (
    AnalysisResult,
    Camera,
    CameraEnableRequest,
    CommandResult,
    CameraView,
    MetadataEvent,
    MASKED_PASSWORD_PLACEHOLDER,
    mask_url_credentials,
)


def test_camera_defaults():
    cam = Camera(camera_id="frigate:front-door", name="Front Door", vendor="frigate")
    assert cam.status == "unknown"
    assert cam.enabled is False
    assert cam.vendor_meta == {}


def test_metadata_event():
    e = MetadataEvent(
        event_id="frigate:abc123",
        camera_id="frigate:front-door",
        event_type="recording_segment",
        started_at=datetime(2026, 3, 30, 12, 0, 0),
    )
    assert e.labels == []
    assert e.confidence is None


def test_analysis_result_with_labels():
    r = AnalysisResult(
        event_id="frigate:abc123", labels=["person", "car"],
        status="2 objects", bookmark=True,
    )
    assert len(r.labels) == 2
    assert r.bookmark is True
    assert r.trigger_recording is False


def test_command_result_unsupported():
    cr = CommandResult(
        command_id="cmd-1", camera_id="frigate:cam1",
        command_type="set_bookmark", status="unsupported",
    )
    assert cr.status == "unsupported"


def test_camera_enable_request():
    req = CameraEnableRequest(camera_ids=["frigate:cam1", "nx:cam2"], enabled=True)
    assert len(req.camera_ids) == 2


def test_mask_url_credentials_masks_password():
    url = "rtsp://admin:secret@localhost:7001/cam1"
    masked = mask_url_credentials(url)
    assert masked == f"rtsp://admin:{MASKED_PASSWORD_PLACEHOLDER}@localhost:7001/cam1"


def test_camera_view_masks_stream_url():
    cam = Camera(
        camera_id="nx:cam1",
        name="Cam 1",
        vendor="nx_witness",
        stream_url="rtsp://admin:secret@localhost:7001/cam1",
    )
    view = CameraView.from_camera(cam)
    assert view.stream_url == f"rtsp://admin:{MASKED_PASSWORD_PLACEHOLDER}@localhost:7001/cam1"
