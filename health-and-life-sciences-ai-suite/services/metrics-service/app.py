import os
import glob
import json
import math
import platform
import shutil
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional, Dict, Any


# The prebuilt intel/retail-benchmark image writes metrics under /tmp/results
METRICS_DIR = Path(os.getenv("METRICS_DIR", "/tmp/results"))
CPU_LOG = METRICS_DIR / "cpu_usage.log"
NPU_CSV = METRICS_DIR / "npu_usage.csv"
MEM_LOG = METRICS_DIR / "memory_usage.log"


def read_last_nonempty_line(path: Path) -> Optional[str]:
    try:
        with path.open() as f:
            lines = [line.strip() for line in f if line.strip()]
        return lines[-1] if lines else None
    except FileNotFoundError:
        return None
    except Exception:
        return None


def parse_cpu_usage() -> Optional[Dict[str, Any]]:
    line = read_last_nonempty_line(CPU_LOG)
    if not line:
        return None
    parts = line.split()
    try:
        # sar output: last column is %idle; usage = 100 - idle
        idle = float(parts[-1])
        usage = max(0.0, min(100.0, 100.0 - idle))
        return {"usage_percent": usage, "raw": line}
    except Exception:
        return {"raw": line}


def parse_npu_usage() -> Optional[Dict[str, Any]]:
    try:
        with NPU_CSV.open() as f:
            lines = [line.strip() for line in f if line.strip()]
        if len(lines) <= 1:
            return None
        last = lines[-1]
        ts, usage = last.split(",", 1)
        try:
            usage_val = float(usage)
        except ValueError:
            usage_val = None
        return {"timestamp": ts, "usage_percent": usage_val}
    except FileNotFoundError:
        return None
    except Exception:
        return None


def parse_gpu_metrics() -> Optional[Dict[str, Any]]:
    # Files like qmassa1-*-tool-generated.json created by qmassa
    pattern = str(METRICS_DIR / "qmassa1-*-tool-generated.json")
    candidates = glob.glob(pattern)
    if not candidates:
        return None
    # Pick the most recently modified file
    latest_path = max(candidates, key=os.path.getmtime)
    try:
        with open(latest_path) as f:
            data = json.load(f)
        return {"source_file": os.path.basename(latest_path), "data": data}
    except Exception:
        return {"source_file": os.path.basename(latest_path)}


def parse_memory_usage() -> Optional[Dict[str, Any]]:
    """Parse memory usage from memory_usage.log (free -s 1 output).

    Returns a dict with total/used bytes and usage_percent, based on the
    last "Mem:" line in the log, or None if unavailable.
    """
    try:
        with MEM_LOG.open() as f:
            lines = [line.rstrip() for line in f if line.strip()]
    except FileNotFoundError:
        return None
    except Exception:
        return None

    mem_line = None
    for line in reversed(lines):
        if line.lstrip().startswith("Mem:"):
            mem_line = line
            break

    if not mem_line:
        return None

    parts = mem_line.split()
    # Typical: "Mem:  total used free shared buff/cache available"
    if len(parts) < 3:
        return {"raw": mem_line}

    try:
        total_kib = float(parts[1])
        used_kib = float(parts[2])
        usage_percent = (used_kib / total_kib) * 100.0 if total_kib > 0 else 0.0
        return {
            "total_kib": total_kib,
            "used_kib": used_kib,
            "usage_percent": usage_percent,
            "raw": mem_line,
        }
    except Exception:
        return {"raw": mem_line}


def build_metrics_payload() -> Dict[str, Any]:
    """Assemble a simplified metrics payload for the /metrics endpoint.

    Only include the key values needed by the UI, so the response stays
    small and focused:

      - cpu.usage_percent
      - npu.usage_percent (+ timestamp)
      - gpu.source_file (omit the large raw JSON payload)
    """

    cpu_raw = parse_cpu_usage()
    npu_raw = parse_npu_usage()
    gpu_raw = parse_gpu_metrics()

    cpu: Optional[Dict[str, Any]]
    if cpu_raw and "usage_percent" in cpu_raw:
        cpu = {"usage_percent": cpu_raw["usage_percent"]}
    else:
        cpu = None

    npu: Optional[Dict[str, Any]]
    if npu_raw:
        npu = {
            "timestamp": npu_raw.get("timestamp"),
            "usage_percent": npu_raw.get("usage_percent"),
        }
    else:
        npu = None

    gpu: Optional[Dict[str, Any]]
    if gpu_raw:
        gpu = {"source_file": gpu_raw.get("source_file")}
    else:
        gpu = None

    return {
        "cpu": cpu,
        "npu": npu,
        "gpu": gpu,
    }


def get_platform_info() -> Dict[str, Any]:
    """Return a high-level platform configuration summary.

    Shape is aligned with the desired UI:

        Processor: Intel® Core™ Ultra 7 155H
        NPU: Intel® AI Boost
        iGPU: Intel® Arc™ Graphics
        Memory: 32 GB
        Storage: 1 TB
    """

    def format_size_gb(size_bytes: int, is_storage: bool = False) -> str:
        gb = size_bytes / (1024 ** 3)
        if is_storage:
            # Match "1 TB" style like Windows logic: approximate TB from GB
            tb = gb / 931
            return f"{round(tb)} TB" if abs(tb - round(tb)) < 0.05 else f"{tb:.2f} TB"
        return f"{math.ceil(gb)} GB"

    def detect_cpu_model() -> str:
        # Best-effort from /proc/cpuinfo
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return platform.processor() or "Intel Processor"

    def detect_igpu() -> str:
        """Try to infer Intel iGPU name from lspci, fallback to generic."""
        try:
            out = subprocess.check_output(["lspci", "-nn"], text=True)
        except Exception:
            return "Intel Graphics"

        for line in out.splitlines():
            if "VGA compatible controller" in line and "Intel" in line:
                # Use the human-readable part after the device ID bracket, if present
                if "]" in line:
                    name = line.split("]", 1)[-1].strip(" :")
                    if name:
                        return name
                return "Intel Graphics"
        return "Intel Graphics"

    def detect_npu() -> str:
        """Best-effort detection of Intel NPU / AI Boost."""
        # Look for AI Boost / NPU in lspci output
        try:
            out = subprocess.check_output(["lspci", "-nn"], text=True)
            for line in out.splitlines():
                if "AI Boost" in line or "NPU" in line.upper():
                    # Return the descriptive part of the line
                    return line.split(":", 1)[-1].strip()
        except Exception:
            pass
        return "Intel AI Boost"

    # Processor
    processor = detect_cpu_model()

    # Memory (from /proc/meminfo)
    memory_str = "--"
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    mem_total_bytes = int(parts[1]) * 1024
                    memory_str = format_size_gb(mem_total_bytes)
                    break
    except Exception:
        pass

    # Storage (root filesystem size)
    storage_str = "--"
    try:
        disk = shutil.disk_usage("/")
        storage_str = format_size_gb(disk.total, is_storage=True)
    except Exception:
        pass

    return {
        "Processor": processor,
        "NPU": detect_npu(),
        "iGPU": detect_igpu(),
        "Memory": memory_str,
        "Storage": storage_str,
    }


class MetricsHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler exposing a /metrics JSON endpoint."""

    def do_GET(self):  # type: ignore[override]
        if self.path.startswith("/metrics"):
            payload = build_metrics_payload()
            status = 200
        elif self.path.startswith("/platform-info"):
            payload = get_platform_info()
            status = 200
        elif self.path.startswith("/memory"):
            payload = parse_memory_usage()
            status = 200 if payload is not None else 404
        else:
            self.send_response(404)
            self.end_headers()
            return

        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = "0.0.0.0", port: int = 9000) -> None:
    server = HTTPServer((host, port), MetricsHandler)
    print(f"Metrics HTTP server listening on {host}:{port}, serving /metrics")
    server.serve_forever()


if __name__ == "__main__":
    run_server()

