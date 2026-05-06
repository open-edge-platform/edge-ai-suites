#!/usr/bin/env python3

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional

CONTENT_SEARCH_DIR: Path = Path(__file__).resolve().parent   # …/content_search/
REPO_ROOT: Path          = CONTENT_SEARCH_DIR.parent         # …/smart-classroom/

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.chdir(CONTENT_SEARCH_DIR)

def _load_config_to_env(config_path: str = "config.yaml") -> None:
    path = REPO_ROOT / config_path
    if not path.exists():
        print(f"[launcher] Warning: {config_path} not found at {path}")
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        cs = data.get("content_search", {})

        def _set(k, v):
            if v is not None:
                os.environ[k] = str(v)

        # ChromaDB
        chroma = cs.get("chromadb", {})
        _set("CHROMA_HOST", chroma.get("host", "127.0.0.1"))
        _set("CHROMA_PORT", chroma.get("port", "9090"))
        _set("CHROMA_DATA_DIR", chroma.get("data_dir", "./data/chroma_data"))
        _set("CHROMA_EXE", chroma.get("chroma_exe"))

        # Local Storage
        storage = cs.get("storage", {})
        _set("STORAGE_DATA_DIR", storage.get("data_dir", "./data/local_storage"))
        _set("STORAGE_BUCKET", storage.get("bucket", "content-search"))

        # VLM
        vlm = cs.get("vlm", {})
        _set("VLM_HOST", vlm.get("host_addr", "127.0.0.1"))
        _set("VLM_PORT", vlm.get("port", "9900"))
        _set("VLM_MODEL_NAME", vlm.get("model_name", "Qwen/Qwen2.5-VL-3B-Instruct"))
        _set("VLM_DEVICE", vlm.get("device", "CPU"))

        # Video Preprocess
        pre = cs.get("video_preprocess", {})
        _set("PREPROCESS_HOST", pre.get("host_addr", "127.0.0.1"))
        _set("PREPROCESS_PORT", pre.get("port", "8001"))

        # File Ingest
        ingest = cs.get("file_ingest", {})
        _set("INGEST_HOST", ingest.get("host_addr", "127.0.0.1"))
        _set("INGEST_PORT", ingest.get("port", "9990"))
        _set("FRAME_EXTRACT_INTERVAL", str(ingest.get("frame_extract_interval", 15)))
        _set("DO_DETECT_AND_CROP", str(ingest.get("do_detect_and_crop", False)).lower())
        _set("INGEST_DEVICE", ingest.get("doc_embedding_device", "CPU"))

        # Document Parser
        doc_parser = ingest.get("document_parser", {})
        _set("DOC_CHUNK_METHOD", doc_parser.get("chunk_method", "fixed"))
        _set("DOC_CHUNK_SIZE", doc_parser.get("chunk_size", 250))
        _set("DOC_CHUNK_OVERLAP", doc_parser.get("chunk_overlap", 50))
        _set("DOC_SEMANTIC_BREAKPOINT_PERCENTILE", doc_parser.get("semantic_breakpoint_percentile", 85))
        _set("DOC_SEMANTIC_BUFFER_SIZE", doc_parser.get("semantic_buffer_size", 2))
        _set("DOC_SEMANTIC_MIN_CHUNK_SIZE", doc_parser.get("semantic_min_chunk_size", 250))

        # Reranker
        reranker = ingest.get("reranker", {})
        _set("RERANKER_MODEL", reranker.get("model", "BAAI/bge-reranker-large"))
        _set("RERANKER_DEVICE", reranker.get("device", "CPU"))
        _set("RERANKER_DEDUP_TIME_THRESHOLD", str(reranker.get("dedup_time_threshold", 5)))
        _set("RERANKER_OVERFETCH_MULTIPLIER", str(reranker.get("overfetch_multiplier", 3)))

        # Video Summarization
        _set("VIDEO_SUMMARIZATION_ENABLED", str(cs.get("video_summarization_enabled", True)).lower())

        # Q&A
        qa = cs.get("qa", {})
        _set("QA_MAX_CONTEXT", str(qa.get("max_context", 5)))
        _set("QA_MAX_TOKENS", str(qa.get("max_tokens", 1024)))
        _set("QA_MAX_HISTORY_TURNS", str(qa.get("max_history_turns", 3)))
        _set("VLM_CONTEXT_WINDOW", str(qa.get("context_window", 16384)))

        # Main App Portal
        _set("CS_HOST", cs.get("host_addr", "127.0.0.1"))
        _set("CS_PORT", cs.get("port", "9011"))

        print(f"[launcher] Config loaded from {config_path} and injected to env.")
    except Exception as e:
        print(f"[launcher] Error loading config: {e}")

def _build_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    paths = [str(CONTENT_SEARCH_DIR), str(REPO_ROOT)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)

    _no_proxy_locals = "localhost,127.0.0.1,::1"
    for key in ("no_proxy", "NO_PROXY"):
        existing = env.get(key, "")
        env[key] = f"{existing},{_no_proxy_locals}" if existing else _no_proxy_locals

    if extra:
        env.update(extra)
    return env

def _spawn(
    name: str, cmd: List[str], cwd: Path, logs_dir: Path, procs: Dict, log_files: Dict,
    extra_env: Optional[Dict[str, str]] = None,
) -> None:
    log_path = logs_dir / name / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8", buffering=1)
    log_files[name] = log_file

    p = subprocess.Popen(
        cmd, cwd=str(cwd),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
        encoding="utf-8", errors="replace",
        env=_build_env(extra_env),
        start_new_session=True,
    )
    procs[name] = p

    def _tee(pipe, lf) -> None:
        try:
            for raw in pipe:
                msg = f"[{name}] {raw.rstrip()}"
                print(msg, flush=True)
                try:
                    lf.write(msg + "\n"); lf.flush()
                except Exception: pass
        except Exception: pass

    threading.Thread(target=_tee, args=(p.stdout, log_file), daemon=True).start()
    print(f"[launcher] Started {name}: pid={p.pid}  logs: {log_path}")

def _check_health(host: str, port: int, path: str = "") -> bool:
    """Check service health. If path is given, do HTTP GET; otherwise just TCP connect."""
    try:
        s = socket.create_connection((host, port), timeout=5)
        if not path:
            s.close()
            return True
        s.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n".encode())
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\r\n" in data:
                break
        s.close()
        text = data.decode("utf-8", errors="replace")
        return text.startswith("HTTP/") and int(text.split()[1]) < 400
    except Exception:
        return False

def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)

def main() -> None:
    _load_config_to_env()

    parser = argparse.ArgumentParser(description="Start services via Environment Variables.")
    parser.add_argument("--services", nargs="+", default=["chromadb", "vlm", "preprocess", "ingest", "main_app"])
    args = parser.parse_args()

    requested = []
    for v in args.services:
        requested.extend(p.strip().lower() for p in v.split(",") if p.strip())
    requested = list(dict.fromkeys(requested))

    # Skip VLM and video preprocess services when video summarization is globally disabled
    vs_enabled = _env("VIDEO_SUMMARIZATION_ENABLED", "true").lower() in ("true", "1", "yes")
    if not vs_enabled:
        skipped = [s for s in ("vlm", "preprocess") if s in requested]
        if skipped:
            print(f"[launcher] VIDEO_SUMMARIZATION_ENABLED=false, skipping: {', '.join(skipped)}")
            requested = [s for s in requested if s not in ("vlm", "preprocess")]

    logs_dir = CONTENT_SEARCH_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    chroma_exe = _env("CHROMA_EXE", "")
    if not chroma_exe:
        venv_exe = CONTENT_SEARCH_DIR / "venv_content_search" / "Scripts" / "chroma.exe"
        chroma_exe = str(venv_exe) if venv_exe.exists() else "chroma"

    # Each service: cmd, cwd, extra_env, health check (host, port, path), timeout
    # health path="" means TCP-only check
    services_meta = {
        "chromadb": {
            "cmd": [chroma_exe, "run",
                    "--host", _env("CHROMA_HOST", "127.0.0.1"),
                    "--port", _env("CHROMA_PORT", "9090"),
                    "--path", _env("CHROMA_DATA_DIR", "./data/chroma_data")],
            "cwd": CONTENT_SEARCH_DIR,
            "health": (_env("CHROMA_HOST", "127.0.0.1"), int(_env("CHROMA_PORT", "9090")), ""),
            "health_timeout": 60,
        },
        "vlm": {
            "cmd": [sys.executable, "-m", "uvicorn", "providers.vlm_openvino_serving.app:app",
                    "--host", _env("VLM_HOST", "127.0.0.1"),
                    "--port", _env("VLM_PORT", "9900")],
            "cwd": CONTENT_SEARCH_DIR,
            "extra_env": {
                "VLM_MODEL_NAME": _env("VLM_MODEL_NAME", "Qwen/Qwen2.5-VL-3B-Instruct"),
                "VLM_DEVICE": _env("VLM_DEVICE", "CPU"),
            },
            "health": (_env("VLM_HOST", "127.0.0.1"), int(_env("VLM_PORT", "9900")), "/health"),
            "health_timeout": 600,
        },
        "preprocess": {
            "cmd": [sys.executable, "-m", "uvicorn", "providers.video_preprocess.server:app",
                    "--host", _env("PREPROCESS_HOST", "127.0.0.1"),
                    "--port", _env("PREPROCESS_PORT", "8001")],
            "cwd": CONTENT_SEARCH_DIR,
            "health": (_env("PREPROCESS_HOST", "127.0.0.1"), int(_env("PREPROCESS_PORT", "8001")), "/health"),
            "health_timeout": 120,
        },
        "ingest": {
            "cmd": [sys.executable, "-m", "uvicorn", "providers.file_ingest_and_retrieve.server:app",
                    "--host", _env("INGEST_HOST", "127.0.0.1"),
                    "--port", _env("INGEST_PORT", "9990")],
            "cwd": CONTENT_SEARCH_DIR,
            "health": (_env("INGEST_HOST", "127.0.0.1"), int(_env("INGEST_PORT", "9990")), "/v1/dataprep/health"),
            "health_timeout": 300,
        },
        "main_app": {
            "cmd": [sys.executable, "-m", "uvicorn", "main:app",
                    "--host", _env("CS_HOST", "127.0.0.1"),
                    "--port", _env("CS_PORT", "9011")],
            "cwd": CONTENT_SEARCH_DIR,
            "health": (_env("CS_HOST", "127.0.0.1"), int(_env("CS_PORT", "9011")), "/api/v1/system/health"),
            "health_timeout": 120,
        },
    }

    start_time = time.monotonic()
    print(f"[launcher] Starting services from: {CONTENT_SEARCH_DIR}")
    procs: Dict = {}
    log_files: Dict = {}

    for sname in requested:
        if sname in services_meta:
            meta = services_meta[sname]
            _spawn(sname, meta["cmd"], meta["cwd"], logs_dir, procs, log_files, meta.get("extra_env"))
            time.sleep(0.5)

    def _terminate_all() -> None:
        for name, p in procs.items():
            if p.poll() is None:
                try:
                    if os.name == 'nt': subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], capture_output=True)
                    else: os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                except: p.terminate()

    def _handle_sig(signum, frame) -> None:
        _terminate_all()
        raise SystemExit(0)

    signal.signal(signal.SIGINT,  _handle_sig)
    signal.signal(signal.SIGTERM, _handle_sig)

    # --- Health check: poll each service in parallel ---
    print("[launcher] Waiting for services to become ready...")
    results: Dict[str, bool] = {}

    def _wait_healthy(name: str) -> None:
        meta = services_meta[name]
        host, port, path = meta["health"]
        timeout = meta.get("health_timeout", 60)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if procs[name].poll() is not None:
                break
            if _check_health(host, port, path):
                results[name] = True
                return
            time.sleep(3)
        rc = procs[name].poll()
        results[name] = f"exited (code {rc})" if rc is not None else f"not ready after {timeout}s"

    threads = [threading.Thread(target=_wait_healthy, args=(s,), daemon=True) for s in procs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed = time.monotonic() - start_time
    failed = {s: reason for s, reason in results.items() if reason is not True}
    print()
    if failed:
        details = ", ".join(f"{s} ({reason})" for s, reason in failed.items())
        print(f"[launcher] WARNING: {len(failed)} service(s) failed: {details}")
        print(f"[launcher] Check logs in: {logs_dir}/")
    else:
        print(f"[launcher] All {len(results)} services are ready. (startup took {elapsed:.1f}s)")
    print(f"[launcher] You can use Ctrl+C to stop all services.\n")

    try:
        while True:
            time.sleep(1.0)
            for name, p in list(procs.items()):
                if p.poll() is not None:
                    print(f"[launcher] {name} exited (code {p.returncode})")
                    procs.pop(name)
            if not procs: break
    except (KeyboardInterrupt, SystemExit):
        _terminate_all()
    finally:
        for lf in log_files.values():
            try: lf.close()
            except: pass

if __name__ == "__main__":
    main()
