# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger("camera_discovery")

_USABLE_PIXEL_FORMATS = {"NV12", "YUYV", "MJPEG"}
_FORMAT_ALIASES = {
    "MJPG": "MJPEG",
    "YUY2": "YUYV",
}


def _run_v4l2_command(args: list[str], timeout: int = 5) -> str | None:
    """Run a v4l2-ctl command and return stdout when successful."""
    try:
        result = subprocess.run(
            ["v4l2-ctl", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("v4l2-ctl not found; camera discovery is unavailable")
        return None
    except subprocess.TimeoutExpired:
        logger.debug("Timed out while running v4l2-ctl %s", " ".join(args))
        return None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.debug("Failed to run v4l2-ctl %s: %s", " ".join(args), exc)
        return None

    if result.returncode != 0:
        logger.debug(
            "v4l2-ctl command failed (%s): %s", " ".join(args), result.stderr.strip()
        )
        return None

    return result.stdout


def _extract_device_name(v4l2_all_output: str) -> str | None:
    """Extract a friendly device name from v4l2-ctl --all output."""
    for line in v4l2_all_output.splitlines():
        if line.strip().startswith("Card type"):
            _, _, value = line.partition(":")
            name = value.strip()
            return name or None
    return None


def _has_video_capture_capability(v4l2_all_output: str) -> bool:
    """Return True when Device Caps includes Video Capture."""
    in_device_caps_section = False

    for line in v4l2_all_output.splitlines():
        line_stripped = line.strip()

        if line_stripped.startswith("Device Caps"):
            in_device_caps_section = True
            if "Video Capture" in line:
                return True
            continue

        if in_device_caps_section:
            if line.startswith("\t") or line.startswith(" " * 4):
                if "Video Capture" in line:
                    return True
                continue

            if line_stripped and ":" in line_stripped:
                break

    return False


def _parse_pixel_formats(v4l2_formats_output: str) -> list[str]:
    """Parse fourcc formats from v4l2-ctl --list-formats-ext output."""
    format_re = re.compile(r"\[\d+\]\s*:\s*'([^']+)'")
    formats: list[str] = []

    for line in v4l2_formats_output.splitlines():
        match = format_re.search(line.strip())
        if match:
            fourcc = match.group(1).upper()
            if fourcc not in formats:
                formats.append(fourcc)

    return formats


def _normalize_format(format_name: str) -> str:
    """Normalize format names for compatibility checks."""
    return _FORMAT_ALIASES.get(format_name.upper(), format_name.upper())


def discover_capture_cameras() -> list[dict]:
    """Discover /dev/videoX devices that support Video Capture.

    Rules:
    - MUST: Include only devices where Device Caps contains Video Capture.
    - SHOULD: Mark devices that support usable formats (NV12, YUYV, MJPEG).
    - IGNORE: Metadata-only nodes without Video Capture capability.
    """
    cameras: list[dict] = []

    video_nodes = sorted(
        [
            path
            for path in Path("/dev").glob("video*")
            if re.fullmatch(r"video\d+", path.name)
        ]
    )

    for node in video_nodes:
        device_path = str(node)

        all_output = _run_v4l2_command(["-d", device_path, "--all"], timeout=3)
        if not all_output:
            continue

        if not _has_video_capture_capability(all_output):
            continue

        formats_output = _run_v4l2_command(
            ["--device", device_path, "--list-formats-ext"], timeout=3
        )
        pixel_formats = _parse_pixel_formats(formats_output) if formats_output else []

        usable_formats = sorted(
            {
                normalized
                for fmt in pixel_formats
                for normalized in [_normalize_format(fmt)]
                if normalized in _USABLE_PIXEL_FORMATS
            }
        )

        cameras.append(
            {
                "device_path": device_path,
                "device_name": _extract_device_name(all_output),
                "pixel_formats": pixel_formats,
                "usable_formats": usable_formats,
                "has_usable_format": bool(usable_formats),
            }
        )

    cameras.sort(key=lambda item: (not item["has_usable_format"], item["device_path"]))
    logger.debug("Discovered %d capture camera(s)", len(cameras))
    return cameras
