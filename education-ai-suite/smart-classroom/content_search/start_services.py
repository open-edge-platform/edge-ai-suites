#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

CONTENT_SEARCH_DIR: Path = Path(__file__).resolve().parent   # …/content_search/
REPO_ROOT: Path          = CONTENT_SEARCH_DIR.parent         # …/smart-classroom/

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.chdir(REPO_ROOT)  # config_loader opens "config.yaml" relative to cwd
from utils.config_loader import config

def _split_services(values: List[str]) -> List[str]:
    """Accept space- or comma-separated service names, deduplicate, lowercase."""
    flat = []
    for v in values:
        flat.extend(p.strip().lower() for p in v.split(",") if p.strip())
    return list(dict.fromkeys(flat))

def _build_env(extra: Optional[Dict[str, str]] = None,
               extra_pythonpath: Optional[List[str]] = None) -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("TRANSFORMERS_CACHE", None)

    paths = [str(REPO_ROOT)] + [str(p) for p in (extra_pythonpath or [])]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)

    # Ensure localhost traffic is never routed through a corporate proxy.
    _no_proxy_locals = "localhost,127.0.0.1,::1"
    for key in ("no_proxy", "NO_PROXY"):
        existing = env.get(key, "")
        env[key] = f"{existing},{_no_proxy_locals}" if existing else _no_proxy_locals

    if extra:
        env.update(extra)
    return env

def _spawn(
    name: str,
    cmd: List[str],
    cwd: Path,
    logs_dir: Path,
    procs: Dict,
    log_files: Dict,
    extra_env: Optional[Dict[str, str]] = None,
    extra_pythonpath: Optional[List[str]] = None,
) -> None:
    log_path = logs_dir / name / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8", buffering=1)
    log_files[name] = log_file

    p = subprocess.Popen(
        cmd, cwd=str(cwd),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
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
                except Exception:
                    pass
        except Exception:
            pass

    threading.Thread(target=_tee, args=(p.stdout, log_file), daemon=True).start()
    print(f"[launcher] Started {name}: pid={p.pid}  logs: {log_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start content_search services (reads parameters from config.yaml)."
    )
    parser.add_argument(
        "--services", nargs="+",
        default=["chromadb", "minio", "vlm", "preprocess", "ingest"],
        help="Services to start. Choices: chromadb minio vlm preprocess ingest",
    )
    args = parser.parse_args()

    requested = _split_services(args.services)
    valid = {"chromadb", "minio", "vlm", "preprocess", "ingest"}
    if invalid := [s for s in requested if s not in valid]:
        raise SystemExit(f"Unknown service(s): {', '.join(invalid)}. Allowed: {', '.join(sorted(valid))}")

    # --- config aliases ---
    chroma_cfg = config.content_search.chromadb
    minio_cfg  = config.content_search.minio
    vlm_cfg    = config.content_search.vlm
    pre_cfg    = config.content_search.video_preprocess
    ingest_cfg = config.content_search.file_ingest

    logs_dir = CONTENT_SEARCH_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # --- minio exe ---
    minio_exe = ""
    if "minio" in requested:
        if not minio_cfg.minio_exe:
            raise SystemExit("Missing content_search.minio.minio_exe in config.yaml.")
        exe_path = Path(str(minio_cfg.minio_exe).strip().replace("\\", "/")).expanduser()
        if not exe_path.is_absolute():
            exe_path = CONTENT_SEARCH_DIR / exe_path
        if not exe_path.is_file():
            raise SystemExit(
                f"MinIO executable not found: {exe_path}\n"
                "Set content_search.minio.minio_exe in config.yaml."
            )
        minio_exe = str(exe_path.resolve())

    # --- minio data dir ---
    if not minio_cfg.data_dir:
        raise SystemExit("Missing content_search.minio.data_dir in config.yaml.")
    minio_data_path = Path(str(minio_cfg.data_dir)).expanduser().resolve()
    minio_data_path.mkdir(parents=True, exist_ok=True)

    # --- minio listen address: derive from server field (host:port → :port) ---
    minio_server  = str(minio_cfg.server or "").strip()
    minio_address = f":{minio_server.rsplit(':', 1)[-1]}" if minio_server else ":9000"
    minio_console = str(getattr(minio_cfg, "console_address", "") or ":9001").strip() or ":9001"

    # --- VLM HuggingFace cache ---
    hf_cache_raw = str(getattr(vlm_cfg, "hf_cache_dir", "") or "").strip()
    hf_cache = (
        Path(hf_cache_raw).expanduser().resolve()
        if hf_cache_raw
        else (CONTENT_SEARCH_DIR / ".cache" / "huggingface").resolve()
    )

    vlm_dir        = CONTENT_SEARCH_DIR / "vlm_openvino_serving"
    preprocess_dir = CONTENT_SEARCH_DIR / "video_preprocess"

    # --- chromadb exe and data dir ---
    chroma_exe = str((CONTENT_SEARCH_DIR / "venv_content_search" / "Scripts" / "chroma.exe").resolve())
    if not Path(chroma_exe).is_file():
        raise SystemExit(f"ChromaDB executable not found: {chroma_exe}")
    chroma_data_raw = str(getattr(chroma_cfg, "data_dir", "") or "").strip()
    if not chroma_data_raw:
        raise SystemExit("Missing content_search.chromadb.data_dir in config.yaml.")
    chroma_data_path = Path(chroma_data_raw).expanduser().resolve()
    chroma_data_path.mkdir(parents=True, exist_ok=True)

    services_meta = {
        "chromadb": {
            "cmd": [chroma_exe, "run",
                    "--host", str(chroma_cfg.host),
                    "--port", str(int(chroma_cfg.port)),
                    "--path", str(chroma_data_path)],
            "cwd": REPO_ROOT,
            "extra_env": None,
            "extra_pythonpath": None,
        },
        "minio": {
            "cmd": [minio_exe, "server", str(minio_data_path),
                    "--address", minio_address, "--console-address", minio_console],
            "cwd": REPO_ROOT,
            "extra_env": {"MINIO_ROOT_USER": str(minio_cfg.root_user),
                          "MINIO_ROOT_PASSWORD": str(minio_cfg.root_password)},
            "extra_pythonpath": None,
        },
        "vlm": {
            "cmd": [sys.executable, "-m", "uvicorn", "app:app",
                    "--host", str(vlm_cfg.host_addr), "--port", str(int(vlm_cfg.port))],
            "cwd": REPO_ROOT,
            "extra_env": {
                "VLM_MODEL_NAME":                str(vlm_cfg.model_name),
                "VLM_DEVICE":                    str(vlm_cfg.device),
                "VLM_COMPRESSION_WEIGHT_FORMAT": str(vlm_cfg.weight_format),
                "VLM_LOG_LEVEL":                 os.environ.get("VLM_LOG_LEVEL", "info"),
                "HF_HOME":                       str(hf_cache),
                "HUGGINGFACE_HUB_CACHE":         str(hf_cache / "hub"),
                "XDG_CACHE_HOME":                str(hf_cache),
            },
            "extra_pythonpath": [vlm_dir],
        },
        "preprocess": {
            "cmd": [sys.executable, "-m", "uvicorn", "server:app",
                    "--host", str(pre_cfg.host_addr), "--port", str(int(pre_cfg.port))],
            "cwd": REPO_ROOT,
            "extra_env": None,
            "extra_pythonpath": [preprocess_dir],
        },
        "ingest": {
            "cmd": [sys.executable, "-m", "uvicorn",
                    "content_search.file_ingest_and_retrieve.server:app",
                    "--host", str(ingest_cfg.host_addr), "--port", str(int(ingest_cfg.port))],
            "cwd": REPO_ROOT,
            "extra_env": None,
            "extra_pythonpath": None,
        },
    }

    for sname in requested:
        if not services_meta[sname]["cwd"].exists():
            raise SystemExit(f"Working directory not found: {services_meta[sname]['cwd']}")

    print(f"[launcher] Starting services: {', '.join(requested)}")

    procs:     Dict = {}
    log_files: Dict = {}

    for sname in requested:
        meta = services_meta[sname]
        _spawn(sname, meta["cmd"], meta["cwd"], logs_dir, procs, log_files,
               meta["extra_env"], meta["extra_pythonpath"])

    # ------------------------------------------------------------------ #
    # Signal handling and monitoring loop                                 #
    # ------------------------------------------------------------------ #

    def _terminate_all() -> None:
        for name, p in procs.items():
            if p.poll() is None:
                try:
                    print(f"[launcher] Terminating {name} (pid={p.pid})")
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
                except Exception:
                    try:
                        p.terminate()
                    except Exception:
                        pass

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
                rc = p.poll()
                if rc is None:
                    continue
                print(f"[launcher] {name} exited (code {rc})")
                procs.pop(name)
            if not procs:
                print("[launcher] All services have exited.")
                break
    except (KeyboardInterrupt, SystemExit):
        print("\n[launcher] Shutting down...")
        _terminate_all()
    finally:
        for lf in log_files.values():
            try:
                lf.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()
