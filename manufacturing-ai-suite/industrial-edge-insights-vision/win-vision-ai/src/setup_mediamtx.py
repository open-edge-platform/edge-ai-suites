#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""setup_mediamtx.py — Download and install the MediaMTX binary.

Usage::

    python utils/setup_mediamtx.py [--dir mediamtx] [--version v1.15.3]

Run this once before starting the application. The script downloads the
MediaMTX release archive, extracts the binary to *--dir*, and patches the
default ``mediamtx.yml`` to use non-conflicting RTP/RTCP ports (8500/8501).
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

import requests

MEDIAMTX_DEFAULT_VERSION = "v1.15.3"
_PLATFORM_ZIP = {
    "win32":  "windows_amd64",
    "darwin": "darwin_amd64",
    "linux":  "linux_amd64",
}


def _zip_name(version: str, platform_tag: str) -> str:
    return f"mediamtx_{version}_{platform_tag}.zip"


def download_mediamtx(target_dir: Path, version: str = MEDIAMTX_DEFAULT_VERSION) -> Path:
    """Download and extract MediaMTX *version* into *target_dir*.

    Returns the path to the extracted ``mediamtx`` (or ``mediamtx.exe``) binary.
    Raises ``RuntimeError`` if the current platform is not supported.
    """
    platform_tag = _PLATFORM_ZIP.get(sys.platform)
    if platform_tag is None:
        raise RuntimeError(
            f"Unsupported platform: {sys.platform!r}. "
            f"Supported: {list(_PLATFORM_ZIP)}"
        )

    zip_name = _zip_name(version, platform_tag)
    url = f"https://github.com/bluenviron/mediamtx/releases/download/{version}/{zip_name}"

    print(f"Downloading MediaMTX {version} from {url} …")
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()

    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / zip_name
    with open(zip_path, "wb") as fh:
        for chunk in response.iter_content(chunk_size=8192):
            fh.write(chunk)

    print(f"Extracting to {target_dir} …")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)
    zip_path.unlink()

    # Patch default mediamtx.yml to avoid RTP/RTCP port conflicts with other services.
    yml_path = target_dir / "mediamtx.yml"
    if yml_path.exists():
        text = yml_path.read_text(encoding="utf-8")
        text = re.sub(r"^rtpAddress:.*$",  "rtpAddress: :8500",  text, flags=re.MULTILINE)
        text = re.sub(r"^rtcpAddress:.*$", "rtcpAddress: :8501", text, flags=re.MULTILINE)
        yml_path.write_text(text, encoding="utf-8")
        print("Patched mediamtx.yml (rtpAddress=:8500, rtcpAddress=:8501)")

    exe_name = "mediamtx.exe" if sys.platform == "win32" else "mediamtx"
    exe_path = target_dir / exe_name
    if not exe_path.exists():
        raise FileNotFoundError(
            f"Extraction succeeded but binary not found at {exe_path}. "
            "Check the release archive contents."
        )

    print(f"MediaMTX installed: {exe_path}")
    return exe_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and install MediaMTX.")
    parser.add_argument(
        "--dir", default="mediamtx", metavar="DIR",
        help="Directory to install MediaMTX into (default: mediamtx/)",
    )
    parser.add_argument(
        "--version", default=MEDIAMTX_DEFAULT_VERSION, metavar="VER",
        help=f"MediaMTX release version (default: {MEDIAMTX_DEFAULT_VERSION})",
    )
    args = parser.parse_args()

    target_dir = Path(args.dir).resolve()
    exe_path = download_mediamtx(target_dir, version=args.version)
    print(f"\nSetup complete. Pass the following path in your config:\n  mediamtx_exe: {exe_path}")


if __name__ == "__main__":
    main()
