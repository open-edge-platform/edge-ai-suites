import subprocess
import sys
import time
import logging
from pathlib import Path
from typing import Optional
import signal
import requests
import zipfile
import atexit
from utils.config_loader import config


class MediaService:
    """Service to manage MediaMTX RTSP server"""

    # MediaMTX download URL
    MEDIAMTX_VERSION = "v1.15.3"
    MEDIAMTX_DOWNLOAD_URL = f"https://github.com/bluenviron/mediamtx/releases/download/{MEDIAMTX_VERSION}/mediamtx_{MEDIAMTX_VERSION}_windows_amd64.zip"

    def __init__(self):
        """
        Initialize MediaService
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        self.mediamtx_dir = Path(config.va_pipeline.mediamtx_path).resolve()
        self.mediamtx_exe = self.mediamtx_dir / "mediamtx.exe"
        self.process: Optional[subprocess.Popen] = None
        self.log_file = None

        # Download MediaMTX if not found
        if not self.mediamtx_exe.exists():
            self._download_mediamtx()

        # Register cleanup handler
        atexit.register(self._cleanup)

    def _download_mediamtx(self):
        """Download and extract MediaMTX"""
        try:
            self.logger.info(f"Downloading MediaMTX {self.MEDIAMTX_VERSION}...")

            response = requests.get(self.MEDIAMTX_DOWNLOAD_URL, stream=True)
            response.raise_for_status()

            zip_path = Path("mediamtx.zip")
            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            self.mediamtx_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(self.mediamtx_dir)
            zip_path.unlink()

            # Update mediamtx.yml configuration
            yml_path = self.mediamtx_dir / "mediamtx.yml"
            if yml_path.exists():
                with open(yml_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Update RTP and RTCP addresses
                import re
                content = re.sub(r'^rtpAddress:.*$', 'rtpAddress: :8500', content, flags=re.MULTILINE)
                content = re.sub(r'^rtcpAddress:.*$', 'rtcpAddress: :8501', content, flags=re.MULTILINE)

                with open(yml_path, "w", encoding="utf-8") as f:
                    f.write(content)

            self.logger.info(f"MediaMTX installed to {self.mediamtx_dir}")

        except Exception as e:
            self.logger.error(f"Failed to download MediaMTX: {e}")
            raise

    def is_running(self) -> bool:
        """Check if MediaMTX server is running"""
        if self.process is None:
            return False

        # Check if process is still alive
        if self.process.poll() is None:
            return True

        return False

    def get_status(self) -> dict:
        """Get server status information"""
        status = {
            "running": self.is_running(),
            "pid": self.process.pid if self.process else None,
            "executable": str(self.mediamtx_exe),
        }

        return status

    def launch_server(self, timeout: float = 10.0) -> bool:
        """
        Launch MediaMTX server

        Args:
            timeout: Maximum time to wait for server to be ready (seconds)

        Returns:
            True if server started successfully, False otherwise
        """
        if self.is_running():
            self.logger.warning("MediaMTX server is already running")
            return True

        try:
            self.logger.info(f"Starting MediaMTX server")

            # Build command
            command = [str(self.mediamtx_exe)]

            # Open log file for writing
            log_file_path = self.mediamtx_dir / "mediamtx.log"
            self.log_file = open(log_file_path, "w", encoding="utf-8")

            # Start the process
            self.process = subprocess.Popen(
                command,
                stdout=self.log_file,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                cwd=str(self.mediamtx_dir),
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32"
                    else 0
                ),
            )

            # Wait for server to be ready
            start_time = time.time()
            ready = False

            while time.time() - start_time < timeout:
                if not self.is_running():
                    self.logger.error("MediaMTX server process terminated unexpectedly")
                    return False

                try:
                    # Check log file for ready indicator
                    self.log_file.flush()
                    with open(self.log_file.name, "r", encoding="utf-8") as f:
                        content = f.read()
                        if "[RTSP] listener opened" in content:
                            ready = True
                            break
                except:
                    pass

                time.sleep(1)

            if ready:
                self.logger.info("MediaMTX server is ready")
                return True

            else:
                self.logger.warning(
                    f"Server started but ready check timed out after {timeout}s"
                )
                return False

        except Exception as e:
            self.logger.error(f"Failed to start MediaMTX server: {e}")
            return False

    def stop_server(self) -> bool:
        """
        Stop MediaMTX server

        Returns:
            True if server stopped successfully, False otherwise
        """
        if not self.is_running():
            self.logger.warning("MediaMTX server is not running")
            return True

        try:
            self.logger.info(f"Stopping MediaMTX server (PID: {self.process.pid})")

            # Try graceful shutdown first
            if sys.platform == "win32":
                # On Windows, send CTRL_BREAK_EVENT
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                # On Unix-like systems, send SIGTERM
                self.process.terminate()

            # Wait for process to terminate
            try:
                self.process.wait(timeout=10.0)
                self.logger.info("MediaMTX server stopped gracefully")
                return True
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Server did not stop within 10s, forcing kill...")
                self.process.kill()
                self.process.wait(timeout=5)
                self.logger.info("MediaMTX server killed")
                return True

        except Exception as e:
            self.logger.error(f"Error stopping MediaMTX server: {e}")
            return False
        finally:
            self.process = None
            if self.log_file:
                self.log_file.close()
                self.log_file = None

    def _cleanup(self):
        """Cleanup handler called on process exit"""
        if self.is_running():
            self.logger.info("Cleaning up MediaMTX server on exit...")
            self.stop_server()
        if self.log_file:
            self.log_file.close()
            self.log_file = None
