"""Parent-side handle for a pipeline_runner child process.

Duck-types the subprocess.Popen surface VideoAnalyticsPipelineService already
uses (poll, pid, returncode, wait, terminate, kill), and provides typed
pipeline events delivered over a multiprocessing connection.
"""

import logging
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from multiprocessing.connection import Listener
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Repo root (smart-classroom/), the working directory `-m` resolves against.
_APP_ROOT = Path(__file__).resolve().parents[2]

RUNNER_MODULE = "components.va.pipeline_runner"

# Ceiling on the handshake: spawning python, importing gi and running
# Gst.init. Generous because a cold plugin registry rebuild lands here.
CONNECT_TIMEOUT_SEC = 90.0


class PipelineRunnerClient:
    """Spawns and supervises one pipeline_runner child."""

    def __init__(self, pipeline_name: str, description: str, log_handle):
        self.pipeline_name = pipeline_name
        self.description = description
        self._log_handle = log_handle

        self._listener: Optional[Listener] = None
        self._conn = None
        self._process: Optional[subprocess.Popen] = None
        self._authkey_path: Optional[str] = None

        self._lock = threading.Lock()
        self._events: List[Dict] = []
        self._playing = threading.Event()
        self._terminal = threading.Event()
        self._final_event: Optional[str] = None
        self._last_error: Optional[Dict] = None

    # ---- lifecycle ---------------------------------------------------------

    def start(self, ready_timeout: float) -> None:
        """Spawn the child and block until it reports PLAYING.

        Raises:
            RuntimeError: the child failed to start, errored during preroll, or
                did not reach PLAYING within ready_timeout.
        """
        authkey = secrets.token_bytes(32)
        fd, self._authkey_path = tempfile.mkstemp(prefix=f"va_{self.pipeline_name}_", suffix=".key")
        with os.fdopen(fd, "wb") as fh:
            fh.write(authkey)

        self._listener = Listener(authkey=authkey)

        command = [
            sys.executable,
            "-m",
            RUNNER_MODULE,
            "--name",
            self.pipeline_name,
            "--ipc",
            str(self._listener.address),
            "--authkey-file",
            self._authkey_path,
        ]
        logger.info(f"Launching runner for '{self.pipeline_name}': {' '.join(command)}")

        self._process = subprocess.Popen(
            command,
            cwd=str(_APP_ROOT),
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=os.environ.copy(),
        )

        try:
            self._accept_with_timeout(CONNECT_TIMEOUT_SEC)
            self._conn.send({"description": self.description})
            threading.Thread(
                target=self._read_events,
                daemon=True,
                name=f"runner-events-{self.pipeline_name}",
            ).start()
            self._await_playing(ready_timeout)
        except Exception:
            self._cleanup_transport()
            self.kill()
            raise

    def _accept_with_timeout(self, timeout: float) -> None:
        """Listener.accept() has no timeout of its own, so bound it here."""
        result = {}

        def _accept():
            try:
                result["conn"] = self._listener.accept()
            except Exception as e:
                result["error"] = e

        thread = threading.Thread(target=_accept, daemon=True, name=f"accept-{self.pipeline_name}")
        thread.start()
        thread.join(timeout)

        if "conn" in result:
            self._conn = result["conn"]
            return
        if "error" in result:
            raise RuntimeError(f"Runner connection failed: {result['error']}")
        raise RuntimeError(
            f"Runner for '{self.pipeline_name}' did not connect within {timeout:.0f}s "
            f"(exit code: {self._process.poll()})"
        )

    def _await_playing(self, timeout: float) -> None:
        """Wait for PLAYING, failing fast if the child errors or dies first."""
        deadline = time.monotonic() + timeout
        while True:
            if self._playing.wait(0.2):
                logger.info(f"Pipeline '{self.pipeline_name}' reached PLAYING")
                return
            if self._terminal.is_set():
                raise RuntimeError(self.error_text() or "Runner stopped before reaching PLAYING")
            if self._process.poll() is not None:
                raise RuntimeError(
                    self.error_text()
                    or f"Runner exited with code {self._process.returncode} before reaching PLAYING"
                )
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"Pipeline '{self.pipeline_name}' did not reach PLAYING within {timeout:.0f}s"
                )

    def _read_events(self) -> None:
        """Drain typed events from the child until the connection closes."""
        while True:
            try:
                event = self._conn.recv()
            except (EOFError, OSError):
                break
            except Exception as e:
                logger.warning(f"[{self.pipeline_name}] event channel error: {e}")
                break

            if not isinstance(event, dict):
                continue

            kind = event.get("ev")
            with self._lock:
                self._events.append(event)
                if kind == "error":
                    self._last_error = event

            if kind == "playing":
                self._playing.set()
            elif kind in ("eos", "error"):
                self._final_event = kind
                self._terminal.set()

        # Connection closed without a terminal event: the child died abruptly.
        self._terminal.set()

    def request_stop(self) -> bool:
        """Ask the child to send EOS so sinks finalise. False if unreachable."""
        if self._conn is None:
            return False
        try:
            self._conn.send({"cmd": "stop"})
            return True
        except Exception as e:
            logger.warning(f"[{self.pipeline_name}] could not send stop: {e}")
            return False

    def _cleanup_transport(self) -> None:
        for closeable in (self._conn, self._listener):
            try:
                if closeable is not None:
                    closeable.close()
            except Exception:
                pass
        self._conn = None
        self._listener = None
        if self._authkey_path and os.path.exists(self._authkey_path):
            try:
                os.unlink(self._authkey_path)
            except OSError:
                pass
        self._authkey_path = None

    # ---- reported state ----------------------------------------------------

    @property
    def final_event(self) -> Optional[str]:
        """'eos', 'error', or None when the child is still running."""
        return self._final_event

    def exited_normally(self) -> bool:
        return self._final_event == "eos"

    def error_text(self) -> Optional[str]:
        """Human-readable text for the last ERROR, or None."""
        with self._lock:
            error = self._last_error
        if not error:
            return None
        parts = [p for p in (error.get("element"), error.get("message")) if p]
        text = ": ".join(parts) if parts else "Pipeline error"
        debug = error.get("debug")
        return f"{text} | {debug}" if debug else text

    def events(self) -> List[Dict]:
        with self._lock:
            return list(self._events)

    # ---- Popen-compatible surface -----------------------------------------

    @property
    def pid(self) -> Optional[int]:
        return self._process.pid if self._process else None

    @property
    def returncode(self) -> Optional[int]:
        return self._process.returncode if self._process else None

    def poll(self) -> Optional[int]:
        return self._process.poll() if self._process else None

    def wait(self, timeout: Optional[float] = None) -> int:
        return self._process.wait(timeout=timeout)

    def terminate(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def kill(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.kill()

    def close(self) -> None:
        self._cleanup_transport()
