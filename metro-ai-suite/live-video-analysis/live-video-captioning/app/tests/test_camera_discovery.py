# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.camera_discovery."""

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.services import camera_discovery as cd


class TestRunV4L2Command:
    """Unit tests for _run_v4l2_command."""

    def test_returns_stdout_on_success(self):
        with patch(
            "backend.services.camera_discovery.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""),
        ):
            assert cd._run_v4l2_command(["--all"]) == "ok"

    def test_returns_none_when_v4l2ctl_not_found(self):
        with patch(
            "backend.services.camera_discovery.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            assert cd._run_v4l2_command(["--all"]) is None

    def test_returns_none_on_timeout(self):
        with patch(
            "backend.services.camera_discovery.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="v4l2-ctl", timeout=3),
        ):
            assert cd._run_v4l2_command(["--all"], timeout=3) is None

    def test_returns_none_on_generic_exception(self):
        with patch(
            "backend.services.camera_discovery.subprocess.run",
            side_effect=RuntimeError("boom"),
        ):
            assert cd._run_v4l2_command(["--all"]) is None

    def test_returns_none_on_non_zero_exit(self):
        with patch(
            "backend.services.camera_discovery.subprocess.run",
            return_value=SimpleNamespace(returncode=1, stdout="", stderr="err"),
        ):
            assert cd._run_v4l2_command(["--all"]) is None


class TestHelpers:
    """Unit tests for helper parsers and predicates."""

    def test_extract_device_name_from_card_type(self):
        out = "Driver Info:\n\tCard type    : USB Camera\n"
        assert cd._extract_device_name(out) == "USB Camera"

    def test_extract_device_name_returns_none_without_card_type(self):
        assert cd._extract_device_name("Driver Info:\n") is None

    def test_has_video_capture_capability_inline(self):
        out = "Device Caps: Video Capture\n"
        assert cd._has_video_capture_capability(out) is True

    def test_has_video_capture_capability_indented_section(self):
        out = "Device Caps\n\tVideo Capture\nFormat Video Capture\n"
        assert cd._has_video_capture_capability(out) is True

    def test_has_video_capture_capability_false_when_absent(self):
        out = "Device Caps\n\tStreaming\nDriver Info: abc\n"
        assert cd._has_video_capture_capability(out) is False

    def test_parse_pixel_formats_dedup_and_uppercase(self):
        out = """
        [0]: 'mjpg' (Motion-JPEG)
        [1]: 'YUYV' (YUYV 4:2:2)
        [2]: 'mjpg' (Motion-JPEG)
        """
        assert cd._parse_pixel_formats(out) == ["MJPG", "YUYV"]

    def test_normalize_format_alias_and_passthrough(self):
        assert cd._normalize_format("mjpg") == "MJPEG"
        assert cd._normalize_format("yuy2") == "YUYV"
        assert cd._normalize_format("nv12") == "NV12"


class TestDiscoverCaptureCameras:
    """Integration-style tests for discover_capture_cameras decision logic."""

    def test_filters_non_capture_and_failed_devices(self):
        nodes = [
            Path("/dev/video1"),
            Path("/dev/video0"),
            Path("/dev/videoX"),
            Path("/dev/video2"),
        ]

        side_effect = [
            # /dev/video0 --all
            "Card type: Cam0\nDevice Caps\n\tVideo Capture\n",
            # /dev/video0 --list-formats-ext
            "[0]: 'mjpg'\n[1]: 'NV12'\n",
            # /dev/video1 --all (no capture)
            "Card type: Meta\nDevice Caps\n\tMetadata Capture\n",
            # /dev/video2 --all (command failed)
            None,
        ]

        with patch(
            "backend.services.camera_discovery.Path.glob", return_value=nodes
        ), patch(
            "backend.services.camera_discovery._run_v4l2_command",
            side_effect=side_effect,
        ):
            cameras = cd.discover_capture_cameras()

        assert cameras == [
            {
                "device_path": "/dev/video0",
                "device_name": "Cam0",
                "pixel_formats": ["MJPG", "NV12"],
                "usable_formats": ["MJPEG", "NV12"],
                "has_usable_format": True,
            }
        ]

    def test_sorts_usable_first_then_device_path(self):
        nodes = [Path("/dev/video2"), Path("/dev/video0")]

        side_effect = [
            # /dev/video0 --all
            "Card type: Cam0\nDevice Caps\n\tVideo Capture\n",
            # /dev/video0 --list-formats-ext (not usable)
            "[0]: 'RGB3'\n",
            # /dev/video2 --all
            "Card type: Cam2\nDevice Caps\n\tVideo Capture\n",
            # /dev/video2 --list-formats-ext (usable)
            "[0]: 'YUY2'\n",
        ]

        with patch(
            "backend.services.camera_discovery.Path.glob", return_value=nodes
        ), patch(
            "backend.services.camera_discovery._run_v4l2_command",
            side_effect=side_effect,
        ):
            cameras = cd.discover_capture_cameras()

        assert [c["device_path"] for c in cameras] == ["/dev/video2", "/dev/video0"]
        assert cameras[0]["has_usable_format"] is True
        assert cameras[1]["has_usable_format"] is False
