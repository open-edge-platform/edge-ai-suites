#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""media_service.py — MediaMTX RTSP/WebRTC server lifecycle manager (start, stop).

Assumes MediaMTX is already installed. Run ``python src/setup_mediamtx.py`` to
download and set up the binary before starting the application.
"""

from __future__ import annotations

import atexit
import logging
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


class MediaService:
    """Manages a MediaMTX RTSP/WebRTC server process.

    The MediaMTX binary must already exist at *mediamtx_exe*. To download and
    install it run ``python src/setup_mediamtx.py --dir <directory>``.
    """

    def __init__(self, mediamtx_exe: str, port: int = 8554,
                 instance_id: str = "") -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.mediamtx_exe = Path(mediamtx_exe).resolve()
        self.mediamtx_dir = self.mediamtx_exe.parent
        self.port = port
        self._instance_id = instance_id
        # Each instance gets its own runtime config and log file to avoid conflicts
        suffix = f"_{instance_id}" if instance_id else ""
        self._runtime_yml = self.mediamtx_dir / f"mediamtx_runtime{suffix}.yml"
        self._log_file_path = self.mediamtx_dir / f"mediamtx{suffix}.log"
        self.process: Optional[subprocess.Popen] = None
        self.log_file = None
        if not self.mediamtx_exe.exists():
            raise FileNotFoundError(
                f"MediaMTX executable not found: {self.mediamtx_exe}\n"
                "Run 'python src/setup_mediamtx.py' to download and install it."
            )
        atexit.register(self._cleanup)

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def get_status(self) -> dict:
        return {
            "running": self.is_running(),
            "pid": self.process.pid if self.process else None,
            "executable": str(self.mediamtx_exe),
            "port": self.port,
        }

    def _build_runtime_config(self, rtsp_enabled: bool, webrtc_enabled: bool) -> Path:
        """Write a per-instance runtime config with only the required protocol enabled.

        Disables rtmp, hls, and srt in every instance to prevent port conflicts
        when multiple MediaMTX instances run side-by-side.
        """
        text = (self.mediamtx_dir / "mediamtx.yml").read_text(encoding="utf-8")
        for proto, enabled in [
            ("rtsp",   rtsp_enabled),
            ("webrtc", webrtc_enabled),
            ("rtmp",   False),
            ("hls",    False),
            ("srt",    False),
        ]:
            text = re.sub(
                rf"^{proto}:\s*(yes|no)\s*$",
                f"{proto}: {'yes' if enabled else 'no'}",
                text, flags=re.MULTILINE,
            )
        self._runtime_yml.write_text(text, encoding="utf-8")
        return self._runtime_yml

    def launch_server(self, timeout: float = 10.0,
                      rtsp_enabled: bool = True, webrtc_enabled: bool = True) -> bool:
        if self.is_running():
            self.logger.warning("MediaMTX is already running")
            return True
        try:
            self.logger.info("Starting MediaMTX server (rtsp_enabled=%s, webrtc_enabled=%s)",
                             rtsp_enabled, webrtc_enabled)
            runtime_cfg = self._build_runtime_config(rtsp_enabled, webrtc_enabled)
            self.log_file = open(self._log_file_path, "w", encoding="utf-8")
            self.process = subprocess.Popen(
                [str(self.mediamtx_exe), str(runtime_cfg)],
                stdout=self.log_file, stderr=subprocess.STDOUT,
                universal_newlines=True, bufsize=1,
                cwd=str(self.mediamtx_dir),
                creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0),
            )
            deadline = time.time() + timeout
            while time.time() < deadline:
                if not self.is_running():
                    try:
                        self.log_file.flush()
                        output = self._log_file_path.read_text(encoding="utf-8").strip()
                        self.logger.error("MediaMTX terminated unexpectedly.%s", f"\n{output}" if output else "")
                    except OSError:
                        self.logger.error("MediaMTX terminated unexpectedly")
                    return False
                try:
                    self.log_file.flush()
                    log_text = self._log_file_path.read_text(encoding="utf-8")
                    rtsp_ready = not rtsp_enabled or "[RTSP] listener opened" in log_text
                    webrtc_ready = not webrtc_enabled or "[WebRTC] listener opened" in log_text
                    if rtsp_ready and webrtc_ready:
                        self.logger.info("MediaMTX server is ready")
                        return True
                except OSError:
                    pass
                time.sleep(0.5)
            self.logger.warning("MediaMTX ready-check timed out after %.0fs — continuing anyway", timeout)
            return self.is_running()
        except Exception as exc:
            self.logger.error("Failed to start MediaMTX: %s", exc)
            return False

    def stop_server(self) -> bool:
        if not self.is_running():
            return True
        try:
            self.logger.info("Stopping MediaMTX (PID %s)", self.process.pid)
            if sys.platform == "win32":
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=3.0)
                self.logger.info("MediaMTX stopped gracefully")
            except subprocess.TimeoutExpired:
                self.logger.warning("MediaMTX did not stop within 10 s — killing")
                self.process.kill()
                self.process.wait(timeout=2)
                self.logger.info("MediaMTX killed")
            return True
        except Exception as exc:
            self.logger.error("Error stopping MediaMTX: %s", exc)
            return False
        finally:
            self.process = None
            if self.log_file:
                self.log_file.close()
                self.log_file = None

    def _cleanup(self) -> None:
        if self.is_running():
            self.stop_server()
        if self.log_file:
            self.log_file.close()
            self.log_file = None