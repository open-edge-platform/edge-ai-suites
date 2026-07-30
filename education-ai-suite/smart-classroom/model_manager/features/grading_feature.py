import logging
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from fastapi import APIRouter

from utils.config_loader import config

logger = logging.getLogger(__name__)

router = APIRouter()

_SC_ROOT = Path(__file__).resolve().parents[2]
_GRADING_DIR = _SC_ROOT / "components" / "grading"
_GRADING_SERVICE = _GRADING_DIR / "grading_service.py"
_LAYOUT_DIR = _GRADING_DIR / "providers" / "layout_detection_service"
_LAYOUT_SERVICE = _LAYOUT_DIR / "layout_detection_server.py"
_LOGS_DIR = _GRADING_DIR / "outputs" / "service_logs"


class GradingFeature:

    id: str = "grading"
    requires: List[str] = []
    depends_on: List[str] = []
    router: APIRouter = router

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._layout_process: Optional[subprocess.Popen] = None
        self._log_files: List = []

    def build(self) -> None:
        if self._process is not None and self._process.poll() is None:
            logger.info("GradingFeature already running; skipping launch.")
            return

        grading = getattr(config, "grading", None)
        provider = getattr(grading, "provider", None) if grading is not None else None
        layout_url = getattr(provider, "layout_detection", None) if provider is not None else None
        vlm_url = getattr(provider, "vlm_provider", None) if provider is not None else None
        if not layout_url or not vlm_url:
            raise RuntimeError(
                "grading.provider.layout_detection and grading.provider.vlm_provider "
                "must be configured in config.yaml"
            )

        if self._layout_process is None or self._layout_process.poll() is not None:
            self._layout_process = self._spawn("layout_detection", _LAYOUT_SERVICE, _LAYOUT_DIR)

        self._process = self._spawn("grading", _GRADING_SERVICE, _GRADING_DIR)

        threading.Thread(
            target=self._health_gate,
            name="grading-health-gate",
            daemon=True,
        ).start()

    def _spawn(self, name: str, script: Path, cwd: Path) -> subprocess.Popen:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = _LOGS_DIR / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}.log"
        log_file = log_path.open("w", encoding="utf-8", buffering=1)
        self._log_files.append(log_file)

        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )

        def _tee(pipe, lf) -> None:
            try:
                for raw in pipe:
                    line = raw.rstrip()
                    print(f"[{name}] {line}", flush=True)
                    try:
                        lf.write(line + "\n")
                        lf.flush()
                    except Exception:
                        pass
            except Exception:
                pass

        threading.Thread(target=_tee, args=(proc.stdout, log_file), name=f"{name}-tee", daemon=True).start()
        logger.info("GradingFeature launched %s service (pid=%s) logs=%s", name, proc.pid, log_path)
        return proc

    def teardown(self) -> None:
        for proc in (self._process, self._layout_process):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        for lf in self._log_files:
            try:
                lf.close()
            except Exception:
                pass
        self._process = None
        self._layout_process = None
        self._log_files = []
        logger.info("GradingFeature torn down.")

    def ui_descriptor(self) -> Dict:
        return {"id": self.id}

    def _health_gate(self, timeout: int = 300, interval: float = 3.0) -> None:
        grading = getattr(config, "grading", None)
        port = int(getattr(grading, "port", 9012)) if grading is not None else 9012
        host = str(getattr(grading, "host_addr", "127.0.0.1")) if grading is not None else "127.0.0.1"
        url = f"http://{host}:{port}/api/v1/health"

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if _http_up(url):
                logger.info("GradingFeature health-gate passed (%s).", url)
                return
            time.sleep(interval)
        logger.warning("GradingFeature health-gate timed out (%s).", url)


def _http_up(url: str) -> bool:
    try:
        resp = requests.get(url, timeout=5, proxies={"http": None, "https": None})
        return resp.status_code < 400
    except requests.RequestException:
        return False
