#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import subprocess
import time
import sys
import os
import yaml
import socket
import threading
from pathlib import Path
from typing import Dict, List

# --- Configuration & Paths ---
CONTENT_SEARCH_DIR: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = CONTENT_SEARCH_DIR.parent
LOGS_DIR: Path = CONTENT_SEARCH_DIR / "logs"

def load_config_to_env(config_path):
    if not os.path.exists(config_path):
        print(f"Config not found at {config_path}")
        return

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        cs = config.get('content_search', {})

        # MinIO
        minio = cs.get('minio', {})
        os.environ["MINIO_SERVER"] = str(minio.get('server', "127.0.0.1:9000"))
        os.environ["MINIO_ROOT_USER"] = str(minio.get('root_user', "minioadmin"))
        os.environ["MINIO_ROOT_PASSWORD"] = str(minio.get('root_password', "minioadmin"))

        # ChromaDB
        chroma = cs.get('chromadb', {})
        os.environ["CHROMA_HOST"] = str(chroma.get('host', "127.0.0.1"))
        os.environ["CHROMA_PORT"] = str(chroma.get('port', 9090))

        # File Ingest
        fi = cs.get('file_ingest', {})
        os.environ["FILE_INGEST_HOST"] = str(fi.get('host_addr', "127.0.0.1"))
        os.environ["FILE_INGEST_PORT"] = str(fi.get('port', 9990))

        # Video Preprocess
        vp = cs.get('video_preprocess', {})
        os.environ["VIDEO_PREPROCESS_HOST"] = str(vp.get('host_addr', "127.0.0.1"))
        os.environ["VIDEO_PREPROCESS_PORT"] = str(vp.get('port', 8001))

        print(f"Config loaded from: {os.path.abspath(config_path)}")
        print("Environment variables injected.")
    except Exception as e:
        print(f"Error parsing config: {e}")

def _build_isolated_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    paths = [str(REPO_ROOT)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)

    _no_proxy = "localhost,127.0.0.1,::1"
    for key in ("no_proxy", "NO_PROXY"):
        existing = env.get(key, "")
        env[key] = f"{existing},{_no_proxy}" if existing else _no_proxy
    return env

def _tee_log(name: str, pipe, log_file):
    try:
        for line in pipe:
            msg = f"[{name}] {line.rstrip()}"
            print(msg, flush=True)
            log_file.write(msg + "\n")
            log_file.flush()
    except Exception:
        pass

def spawn_service(name: str, cmd: List[str], procs: Dict, log_files: Dict):
    print(f"  [+] Launching {name}...")
    log_path = LOGS_DIR / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lf = log_path.open("w", encoding="utf-8", buffering=1)
    log_files[name] = lf

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=_build_isolated_env(),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )
    procs[name] = p
    threading.Thread(target=_tee_log, args=(name, p.stdout, lf), daemon=True).start()

def is_port_open(host, port):
    try:
        target = "127.0.0.1" if host == "localhost" else host
        with socket.create_connection((target, port), timeout=1):
            return True
    except:
        return False

def wait_for_service(name, host, port, timeout=60):
    print(f"  [?] Waiting for {name} on {host}:{port}...", end="", flush=True)
    for _ in range(timeout):
        if is_port_open(host, port):
            print(" [READY]")
            return True
        print(".", end="", flush=True)
        time.sleep(1)
    print(" [FAILED]")
    return False

def start_dev_environment():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    load_config_to_env(os.path.join(os.getcwd(), "..", "config.yaml"))
    
    procs = {}
    log_files = {}
    python_exe = sys.executable

    print("\nStarting Services with Dynamic Configuration...\n")

    try:
        # === STAGE 1: Infrastructure ===
        print("--- STAGE 1: Infrastructure ---")
        m_srv = os.getenv("MINIO_SERVER", "127.0.0.1:9000").split(':')
        spawn_service("MinIO", [
            os.path.abspath(r".\providers\minio_wrapper\minio.exe"), "server", 
            os.path.abspath(r".\providers\minio_wrapper\minio_data"), 
            "--address", os.getenv("MINIO_SERVER")
        ], procs, log_files)

        spawn_service("ChromaDB", [
            python_exe, "-m", "uvicorn", "chromadb.app:app", 
            "--host", os.getenv("CHROMA_HOST"), "--port", os.getenv("CHROMA_PORT")
        ], procs, log_files)

        if not wait_for_service("MinIO", m_srv[0], int(m_srv[1])): return
        if not wait_for_service("ChromaDB", os.getenv("CHROMA_HOST"), int(os.getenv("CHROMA_PORT"))): return

        # === STAGE 2: Core Sub-services ===
        print("\n--- STAGE 2: Core Sub-services ---")
        spawn_service("File Ingest Service", [
            python_exe, "-m", "uvicorn", "providers.file_ingest_and_retrieve.server:app", 
            "--host", os.getenv("FILE_INGEST_HOST"), "--port", os.getenv("FILE_INGEST_PORT")
        ], procs, log_files)

        spawn_service("Video Preprocess Service", [
            python_exe, "-m", "uvicorn", "providers.video_preprocess.server:app", 
            "--host", os.getenv("VIDEO_PREPROCESS_HOST"), "--port", os.getenv("VIDEO_PREPROCESS_PORT")
        ], procs, log_files)

        wait_for_service("File Ingest", os.getenv("FILE_INGEST_HOST"), int(os.getenv("FILE_INGEST_PORT")), timeout=120)
        wait_for_service("Video Preprocess", os.getenv("VIDEO_PREPROCESS_HOST"), int(os.getenv("VIDEO_PREPROCESS_PORT")), timeout=60)

        # === STAGE 3: Main App ===
        print("\n--- STAGE 3: Main App ---")
        spawn_service("MainApp", [python_exe, "main.py"], procs, log_files)

        print("\nAll systems managed. Monitoring status... (Ctrl+C to stop)\n")
        
        while True:
            time.sleep(2)
            for name, p in list(procs.items()):
                result = p.poll()
                if result is not None:
                    print(f"\n[!] NOTICE: Service [{name}] exited with code {result}")
                    procs.pop(name)

            if "MainApp" not in procs or not procs:
                print("\nMain application has finished or all services stopped. Cleaning up...")
                break

    except KeyboardInterrupt:
        print("\n\nShutdown signal received.")
    finally:
        print("\nCleaning up background processes...")
        for name, p in procs.items():
            try:
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], 
                               capture_output=True, timeout=5)
            except:
                pass
        for f in log_files.values():
            f.close()
        print("All background processes closed.")

if __name__ == "__main__":
    start_dev_environment()