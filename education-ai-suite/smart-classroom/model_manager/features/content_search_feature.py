import logging
import socket
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

# smart-classroom root: model_manager/features/content_search_feature.py -> parents[2]
_SC_ROOT = Path(__file__).resolve().parents[2]
_CONTENT_SEARCH_DIR = _SC_ROOT / "content_search"
_LAUNCHER = _CONTENT_SEARCH_DIR / "start_services.py"


class ContentSearchFeature:

    id: str = "content_search"
    requires: List[str] = ["text_gen"]
    depends_on: List[str] = []
    router: APIRouter = router

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        cs_cfg = getattr(config, "content_search", None)
        if cs_cfg is not None and bool(getattr(cs_cfg, "ocr_enabled", True)):
            self.requires = ["ocr", "text_gen"]

    def build(self) -> None:
        if self._process is not None and self._process.poll() is None:
            logger.info("ContentSearchFeature already running; skipping launch.")
            return

        self._process = subprocess.Popen(
            [sys.executable, str(_LAUNCHER)],
            cwd=str(_CONTENT_SEARCH_DIR),
            start_new_session=True,
        )
        logger.info(
            "ContentSearchFeature launched process group (pid=%s) using %s.",
            self._process.pid,
            sys.executable,
        )

        # Observe readiness off the startup path so the main app can finish its
        # lifespan startup and begin serving :8000 (which the launcher itself
        # waits for). This thread only logs; it never blocks build().
        threading.Thread(
            target=self._health_gate,
            name="content-search-health-gate",
            daemon=True,
        ).start()

    def teardown(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        logger.info("ContentSearchFeature torn down.")

    def ui_descriptor(self) -> Dict:
        return {
            "id": self.id,
        }

    def _health_gate(self, timeout: int = 300, interval: float = 3.0) -> None:
        cs = config.content_search
        chroma_host = getattr(cs.chromadb, "host", "127.0.0.1")
        chroma_port = int(getattr(cs.chromadb, "port", 9090))
        ingest_host = getattr(cs.file_ingest, "host_addr", "127.0.0.1")
        ingest_port = int(getattr(cs.file_ingest, "port", 9990))
        ingest_url = f"http://{ingest_host}:{ingest_port}/v1/dataprep/health"

        logger.info(
            "ContentSearchFeature health-gate: waiting for ChromaDB (%s:%s) "
            "and file-ingest (%s) up to %ss...",
            chroma_host, chroma_port, ingest_url, timeout,
        )

        started = time.monotonic()
        deadline = started + timeout
        chroma_ok = False
        ingest_ok = False
        next_progress = started + 60
        while time.monotonic() < deadline:
            if not chroma_ok:
                chroma_ok = _tcp_up(chroma_host, chroma_port)
            if not ingest_ok:
                ingest_ok = _http_up(ingest_url)
            if chroma_ok and ingest_ok:
                logger.info(
                    "ContentSearchFeature health-gate passed after %.0fs.",
                    time.monotonic() - started,
                )
                return
            # Without this the log goes quiet for the whole startup and the only
            # line ever printed is the timeout, with no way to tell a slow model
            # load from a service that is never going to answer.
            if time.monotonic() >= next_progress:
                logger.info(
                    "ContentSearchFeature health-gate still waiting after %.0fs "
                    "(chromadb=%s, ingest=%s).",
                    time.monotonic() - started, chroma_ok, ingest_ok,
                )
                next_progress += 60
            time.sleep(interval)

        logger.warning(
            "ContentSearchFeature health-gate timed out after %ss (chromadb=%s, "
            "ingest=%s). This is observational only - the services keep starting "
            "and may still come up; check content_search/logs/.",
            timeout, chroma_ok, ingest_ok,
        )


def _tcp_up(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except OSError:
        return False


# Explicitly bypass any system/corporate proxy for localhost calls, as the rest
# of the app does. NO_PROXY cannot be relied on: .proxy-config stores a
# Windows-style semicolon list, which Python splits on commas only, so the whole
# string reads as one bogus host and the proxy answers 403 for 127.0.0.1.
_NO_PROXY = {"http": None, "https": None}


def _http_up(url: str) -> bool:
    try:
        resp = requests.get(url, timeout=5, proxies=_NO_PROXY)
        return resp.status_code < 400
    except requests.RequestException:
        return False
