import os
import glob
import csv
import json
import math
import platform
import shutil
import subprocess
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional, Dict, Any, List


# The prebuilt intel/retail-benchmark image writes metrics under /tmp/results
METRICS_DIR = Path(os.getenv("METRICS_DIR", "/tmp/results"))
CPU_LOG = METRICS_DIR / "cpu_usage.log"
NPU_CSV = METRICS_DIR / "npu_usage.csv"
MEM_LOG = METRICS_DIR / "memory_usage.log"
PCM_CSV = METRICS_DIR / "pcm.csv"


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


def build_cpu_series() -> List[List[float]]:
    """Build a time series for CPU utilization from cpu_usage.log.

    Each entry: [timestamp_iso, usage_percent]. Timestamps are
    approximated assuming 1-second sampling (sar 1), counting backwards
    from the current time.
    """
    try:
        with CPU_LOG.open() as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []
    except Exception:
        return []

    samples: List[float] = []
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            idle = float(parts[-1])
            usage = max(0.0, min(100.0, 100.0 - idle))
            samples.append(usage)
        except Exception:
            continue

    if not samples:
        return []

    now = datetime.now()
    start = now - timedelta(seconds=len(samples) - 1)
    series: List[List[float]] = []
    for idx, usage in enumerate(samples):
        ts = (start + timedelta(seconds=idx)).isoformat()
        series.append([ts, usage])
    return series


def build_npu_series() -> List[List[float]]:
    """Build a time series for NPU utilization from npu_usage.csv.

    Each entry: [timestamp_iso, usage_percent].
    """
    try:
        with NPU_CSV.open() as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []
    except Exception:
        return []

    if len(lines) <= 1:
        return []

    series: List[List[float]] = []
    for line in lines[1:]:  # skip header
        try:
            ts, usage = line.split(",", 1)
            usage_val = float(usage)
        except Exception:
            continue
        series.append([ts, usage_val])
    return series


def build_memory_series() -> List[List[float]]:
    """Build a time series for memory usage from memory_usage.log.

    Each entry: [timestamp_iso, total_gb, used_gb, free_gb, usage_percent].
    Timestamps are approximated assuming 1-second sampling, counting
    backwards from the current time.
    """
    try:
        with MEM_LOG.open() as f:
            lines = [line.rstrip() for line in f if line.strip()]
    except FileNotFoundError:
        return []
    except Exception:
        return []

    mem_lines: List[str] = []
    for line in lines:
        if line.lstrip().startswith("Mem:"):
            mem_lines.append(line)

    if not mem_lines:
        return []

    samples: List[Dict[str, float]] = []
    for mem_line in mem_lines:
        parts = mem_line.split()
        if len(parts) < 4:
            continue
        try:
            total_kib = float(parts[1])
            used_kib = float(parts[2])
            free_kib = float(parts[3])
            usage_percent = (used_kib / total_kib) * 100.0 if total_kib > 0 else 0.0
            total_gb = total_kib / (1024 ** 2)
            used_gb = used_kib / (1024 ** 2)
            free_gb = free_kib / (1024 ** 2)
            samples.append(
                {
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "usage_percent": usage_percent,
                }
            )
        except Exception:
            continue

    if not samples:
        return []

    now = datetime.now()
    start = now - timedelta(seconds=len(samples) - 1)
    series: List[List[float]] = []
    for idx, s in enumerate(samples):
        ts = (start + timedelta(seconds=idx)).isoformat()
        series.append(
            [
                ts,
                s["total_gb"],
                s["used_gb"],
                s["free_gb"],
                s["usage_percent"],
            ]
        )
    return series


def build_gpu_series() -> List[List[float]]:
    """Build a time series for GPU utilization.

    Placeholder implementation: returns an empty list until the exact
    qmassa JSON schema and desired metrics are defined.
    """
    return []


def build_power_series() -> List[List[float]]:
    """Build a time series for power metrics from pcm.csv.

    Each entry is a list of the form:

        [timestamp, package0_watts, package1_watts, ...]

    We approximate power in watts by differentiating the energy counters
    (Joules) that PCM exports in the CSV. The Intel PCM CSV produced by
    the collector uses a two-row header: the first row contains labels
    like "Proc Energy (Joules)" and "Power Plane 0 Energy (Joules)",
    and the second row contains generic labels like "SKT0".

    This function:
    - Uses the *first* header row to find energy columns (those whose
      name contains both "energy" and "joule").
    - Uses the *second* header row to locate the Date/Time columns.
    - For each consecutive pair of samples, computes
        power = (energy_now - energy_prev) / dt_seconds
      for all detected energy columns.
    """

    try:
        with PCM_CSV.open() as f:
            reader = csv.reader(f)

            # PCM CSV uses two header rows: first has long labels with
            # "Energy (Joules)", second has short labels like "Date"/"Time".
            header1 = next(reader, None)
            header2 = next(reader, None)
            if not header1 or not header2:
                return []

            # Identify Date/Time columns from the second header row.
            date_idx = None
            time_idx = None
            for idx, col in enumerate(header2):
                col_l = col.lower()
                if date_idx is None and col_l == "date":
                    date_idx = idx
                elif time_idx is None and col_l == "time":
                    time_idx = idx

            # Fallback to the first two columns if not explicitly labeled.
            if date_idx is None:
                date_idx = 0
            if time_idx is None:
                time_idx = 1 if len(header2) > 1 else 0

            # Energy columns come from the first header row: look for
            # entries like "... Energy (Joules)".
            energy_indices: List[int] = []
            for idx, col in enumerate(header1):
                col_l = col.lower()
                if "energy" in col_l and "joule" in col_l:
                    energy_indices.append(idx)

            if not energy_indices:
                return []

            # Read all remaining rows and keep only those that have all
            # required columns present.
            data_rows: List[List[str]] = []
            max_idx = max(max(energy_indices), date_idx, time_idx)
            for row in reader:
                if not row or len(row) <= max_idx:
                    continue
                data_rows.append(row)

            if len(data_rows) < 2:
                return []

            series: List[List[float]] = []

            # Helper to parse timestamp
            def parse_ts(d: str, t: str) -> Optional[datetime]:
                ts_str = f"{d} {t}"
                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(ts_str, fmt)
                    except Exception:
                        continue
                return None

            # Prime with the first row's energies and timestamp
            prev_row = data_rows[0]
            prev_ts = parse_ts(prev_row[date_idx].strip(), prev_row[time_idx].strip())
            try:
                prev_energies = [float(prev_row[i]) for i in energy_indices]
            except Exception:
                # If the first row cannot be parsed, bail out
                return []

            for row in data_rows[1:]:
                cur_ts = parse_ts(row[date_idx].strip(), row[time_idx].strip())
                if cur_ts is None or prev_ts is None:
                    prev_ts = cur_ts
                    continue

                dt = (cur_ts - prev_ts).total_seconds()
                if dt <= 0:
                    prev_ts = cur_ts
                    continue

                try:
                    cur_energies = [float(row[i]) for i in energy_indices]
                except Exception:
                    prev_ts = cur_ts
                    continue

                # Compute power as delta energy / delta time
                powers: List[float] = []
                for e_prev, e_cur in zip(prev_energies, cur_energies):
                    if e_cur >= e_prev:
                        powers.append((e_cur - e_prev) / dt)
                    else:
                        # Counter wrapped or reset; skip negative deltas
                        powers.append(0.0)

                if powers:
                    series.append([cur_ts.isoformat()] + powers)

                prev_ts = cur_ts
                prev_energies = cur_energies

            return series
    except FileNotFoundError:
        return []
    except Exception:
        return []


def build_metrics_payload() -> Dict[str, Any]:
    """Assemble the metrics payload for the /metrics endpoint.

    Matches the desired shape:

        {
            "cpu_utilization": [[ts, value], ...],
            "gpu_utilization": [[ts, ...], ...],
            "memory": [[ts, total_gb, used_gb, free_gb, usage%], ...],
            "power": [],
            "npu_utilization": [[ts, value], ...]
        }
    """

    return {
        "cpu_utilization": build_cpu_series(),
        "gpu_utilization": build_gpu_series(),
        "memory": build_memory_series(),
        "power": build_power_series(),
        "npu_utilization": build_npu_series(),
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

