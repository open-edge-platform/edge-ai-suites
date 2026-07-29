# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.cameras, camera discovery endpoint."""

from unittest.mock import patch


class TestListCameras:
    """GET /api/cameras endpoint."""

    def test_returns_empty_list_when_no_camera_devices(self, client):
        """Returns an empty list when discovery finds no capture cameras."""
        with patch("backend.routes.cameras.discover_capture_cameras", return_value=[]):
            resp = client.get("/api/cameras")

        assert resp.status_code == 200
        assert resp.json() == {"cameras": []}

    def test_returns_discovered_camera_devices(self, client):
        """Returns camera entries from discover_capture_cameras()."""
        discovered = [
            {
                "device_path": "/dev/video0",
                "device_name": "USB Camera",
                "pixel_formats": ["MJPEG", "YUYV"],
                "usable_formats": ["MJPEG", "YUYV"],
                "has_usable_format": True,
            },
            {
                "device_path": "/dev/video2",
                "device_name": "Virtual Cam",
                "pixel_formats": ["RGB3"],
                "usable_formats": [],
                "has_usable_format": False,
            },
        ]

        with patch(
            "backend.routes.cameras.discover_capture_cameras",
            return_value=discovered,
        ):
            resp = client.get("/api/cameras")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["cameras"] == discovered
