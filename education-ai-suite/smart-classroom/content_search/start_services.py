#!/usr/bin/env python3

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import os
import signal
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
                os.environ.setdefault(k, str(v))

        # ChromaDB
        chroma = cs.get("chromadb", {})
        _set("CHROMA_HOST", chroma.get("host", "127.0.0.1"))
        _set("CHROMA_PORT", chroma.get("port", "9090"))
        _set("CHROMA_DATA_DIR", chroma.get("data_dir", "./chroma_data"))
        _set("CHROMA_EXE", chroma.get("chroma_exe"))

        # MinIO
        minio = cs.get("minio", {})
        server_addr = str(minio.get("server", "127.0.0.1:9000"))
        port = server_addr.rsplit(':', 1)[-1]
        _set("MINIO_ADDRESS", f":{port}")
        _set("MINIO_CONSOLE_ADDRESS", minio.get("console_address", ":9001"))
        _set("MINIO_ROOT_USER", minio.get("root_user", "minioadmin"))
        _set("MINIO_ROOT_PASSWORD", minio.get("root_password", "minioadmin"))
        _set("MINIO_DATA_DIR", minio.get("data_dir", "./minio_data"))
        _set("MINIO_EXE", minio.get("minio_exe"))

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

        # Main App Portal
        _set("CS_HOST", cs.get("host_addr", "127.0.0.1"))
        _set("CS_PORT", cs.get("port", "9011"))

        print(f"[launcher] Config loaded from {config_path} and injected to env.")
    except Exception as e:
        print(f"[launcher] Error loading config: {e}")

def _split_services(values: List[str]) -> List[str]:
    flat = []
    for v in values:
        flat.extend(p.strip().lower() for p in v.split(",") if p.strip())
    return list(dict.fromkeys(flat))

def _build_env(extra: Optional[Dict[str, str]] = None,
               extra_pythonpath: Optional[List[str]] = None) -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    paths = [str(CONTENT_SEARCH_DIR), str(REPO_ROOT)] + [str(p) for p in (extra_pythonpath or [])]
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
    extra_env: Optional[Dict[str, str]] = None, extra_pythonpath: Optional[List[str]] = None,
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
        env=_build_env(extra_env, extra_pythonpath),
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

def main() -> None:
    _load_config_to_env()

    parser = argparse.ArgumentParser(description="Start services via Environment Variables.")
    parser.add_argument("--services", nargs="+", default=["chromadb", "minio", "vlm", "preprocess", "ingest", "main_app"])
    args = parser.parse_args()

    requested = _split_services(args.services)
    logs_dir = CONTENT_SEARCH_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    chroma_exe = os.environ.get("CHROMA_EXE")
    if not chroma_exe:
        venv_exe = CONTENT_SEARCH_DIR / "venv_content_search" / "Scripts" / "chroma.exe"
        chroma_exe = str(venv_exe) if venv_exe.exists() else "chroma"
    provider_minio = CONTENT_SEARCH_DIR / "providers" / "minio_wrapper" / "minio.exe"
    minio_exe = str(provider_minio) if provider_minio.exists() else "minio"

    services_meta = {
        "chromadb": {
            "cmd": [chroma_exe, "run", 
                    "--host", os.environ.get("CHROMA_HOST", "127.0.0.1"),
                    "--port", os.environ.get("CHROMA_PORT", "9090"),
                    "--path", os.environ.get("CHROMA_DATA_DIR", "./chroma_data")],
            "cwd": CONTENT_SEARCH_DIR,
        },
        "minio": {
            "cmd": [minio_exe, "server", os.environ.get("MINIO_DATA_DIR", "./minio_data"),
                    "--address", os.environ.get("MINIO_ADDRESS", ":9000"),
                    "--console-address", os.environ.get("MINIO_CONSOLE_ADDRESS", ":9001")],
            "cwd": CONTENT_SEARCH_DIR,
            "extra_env": {
                "MINIO_ROOT_USER": os.environ.get("MINIO_ROOT_USER", "minioadmin"),
                "MINIO_ROOT_PASSWORD": os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin")
            },
        },
        "vlm": {
            "cmd": [sys.executable, "-m", "uvicorn", "providers.vlm_openvino_serving.app:app", 
                    "--host", os.environ.get("VLM_HOST", "127.0.0.1"), 
                    "--port", os.environ.get("VLM_PORT", "9900")],
            "cwd": CONTENT_SEARCH_DIR,
            "extra_env": {
                "VLM_MODEL_NAME": os.environ.get("VLM_MODEL_NAME", "Qwen/Qwen2.5-VL-3B-Instruct"),
                "VLM_DEVICE": os.environ.get("VLM_DEVICE", "CPU"),
            },
        },
        "preprocess": {
            "cmd": [sys.executable, "-m", "uvicorn", "providers.video_preprocess.server:app", 
                    "--host", os.environ.get("PREPROCESS_HOST", "127.0.0.1"), 
                    "--port", os.environ.get("PREPROCESS_PORT", "8001")],
            "cwd": CONTENT_SEARCH_DIR,
        },
        "ingest": {
            "cmd": [sys.executable, "-m", "uvicorn", "providers.file_ingest_and_retrieve.server:app", 
                    "--host", os.environ.get("INGEST_HOST", "127.0.0.1"), 
                    "--port", os.environ.get("INGEST_PORT", "9990")],
            "cwd": CONTENT_SEARCH_DIR,
        },
        "main_app": {
            "cmd": [sys.executable, "-m", "uvicorn", "main:app", 
                    "--host", os.environ.get("CS_HOST", "127.0.0.1"), 
                    "--port", os.environ.get("CS_PORT", "9011")],
            "cwd": CONTENT_SEARCH_DIR, 
        },
    }

    print(f"[launcher] Starting services from: {CONTENT_SEARCH_DIR}")
    procs: Dict = {}
    log_files: Dict = {}

    for sname in requested:
        if sname in services_meta:
            meta = services_meta[sname]
            _spawn(sname, meta["cmd"], meta["cwd"], logs_dir, procs, log_files,
                   meta.get("extra_env"), meta.get("extra_pythonpath"))
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

    print("[launcher] All services started. Press Ctrl+C to stop.")
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