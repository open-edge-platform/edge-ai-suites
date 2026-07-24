"""
Metrics collection and parsing utilities for the metrics-collector service.

Reads metric files written by background OS-level collectors.
"""

import csv
import glob
import json
import math
import os
import platform
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

METRICS_DIR = Path(os.getenv("METRICS_DIR", "/tmp/results"))
CPU_LOG     = METRICS_DIR / "cpu_usage.log"
NPU_CSV     = METRICS_DIR / "npu_usage.csv"
MEM_LOG     = METRICS_DIR / "memory_usage.log"
PCM_CSV     = METRICS_DIR / "pcm.csv"


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

def read_last_nonempty_line(path: Path) -> Optional[str]:
    try:
        with path.open() as f:
            lines = [l.strip() for l in f if l.strip()]
        return lines[-1] if lines else None
    except (FileNotFoundError, OSError):
        return None


def parse_memory_usage() -> Optional[Dict[str, Any]]:
    """Return a single memory snapshot from the latest 'Mem:' line."""
    try:
        with MEM_LOG.open() as f:
            lines = [l.rstrip() for l in f if l.strip()]
    except (FileNotFoundError, OSError):
        return None

    for line in reversed(lines):
        if line.lstrip().startswith("Mem:"):
            parts = line.split()
            if len(parts) < 3:
                return {"raw": line}
            try:
                total_kib   = float(parts[1])
                used_kib    = float(parts[2])
                usage_pct   = (used_kib / total_kib * 100.0) if total_kib > 0 else 0.0
                return {
                    "total_kib":     total_kib,
                    "used_kib":      used_kib,
                    "usage_percent": usage_pct,
                    "raw":           line,
                }
            except ValueError:
                return {"raw": line}
    return None


# ---------------------------------------------------------------------------
# Time-series builders
# ---------------------------------------------------------------------------

def build_cpu_series() -> List[List]:
    """
    Parse cpu_usage.log (sar -u 1 output).
    Each data line ends with %idle; usage = 100 - idle.
    Returns [[timestamp_iso, usage_percent], ...]
    """
    try:
        with CPU_LOG.open() as f:
            raw_lines = [l.strip() for l in f if l.strip()]
    except (FileNotFoundError, OSError):
        return []

    samples: List[float] = []
    for line in raw_lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            idle  = float(parts[-1])
            usage = max(0.0, min(100.0, 100.0 - idle))
            samples.append(usage)
        except ValueError:
            continue   # header / label rows – skip

    if not samples:
        return []

    now   = datetime.now()
    start = now - timedelta(seconds=len(samples) - 1)
    return [
        [(start + timedelta(seconds=i)).isoformat(), v]
        for i, v in enumerate(samples)
    ]


def build_npu_series() -> List[List]:
    """
    Parse npu_usage.csv written by the Intel NPU tool.
    Format: header row + lines of  timestamp_iso,usage_percent
    Returns [[timestamp_iso, usage_percent], ...]
    """
    try:
        with NPU_CSV.open() as f:
            lines = [l.strip() for l in f if l.strip()]
    except (FileNotFoundError, OSError):
        return []

    if len(lines) <= 1:
        return []

    series: List[List] = []
    for line in lines[1:]:   # skip header
        try:
            ts, usage = line.split(",", 1)
            series.append([ts.strip(), float(usage)])
        except ValueError:
            continue
    return series


def build_memory_series() -> List[List]:
    """
    Parse memory_usage.log (free -s 1 output).
    Each entry: [timestamp_iso, total_gb, used_gb, free_gb, usage_percent]
    Timestamps are approximated assuming 1-second sampling.
    """
    try:
        with MEM_LOG.open() as f:
            lines = [l.rstrip() for l in f if l.strip()]
    except (FileNotFoundError, OSError):
        return []

    mem_lines = [l for l in lines if l.lstrip().startswith("Mem:")]
    if not mem_lines:
        return []

    samples: List[Dict[str, float]] = []
    for line in mem_lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            total_kib   = float(parts[1])
            used_kib    = float(parts[2])
            free_kib    = float(parts[3])
            usage_pct   = (used_kib / total_kib * 100.0) if total_kib > 0 else 0.0
            samples.append({
                "total_gb":      total_kib / 1024 ** 2,
                "used_gb":       used_kib  / 1024 ** 2,
                "free_gb":       free_kib  / 1024 ** 2,
                "usage_percent": usage_pct,
            })
        except ValueError:
            continue

    if not samples:
        return []

    now   = datetime.now()
    start = now - timedelta(seconds=len(samples) - 1)
    return [
        [
            (start + timedelta(seconds=i)).isoformat(),
            s["total_gb"],
            s["used_gb"],
            s["free_gb"],
            s["usage_percent"],
        ]
        for i, s in enumerate(samples)
    ]


def build_gpu_series() -> List[List]:
    """
    Parse qmassa JSON files written by the qmassa tool (from intel/retail-benchmark).

    Files are named: qmassa1-*-tool-generated.json under METRICS_DIR.

    qmassa JSON shape (abbreviated):
    {
        "args":   {"ms_interval": 1500, ...},
        "states": [
            {
                "devs_state": [
                    {
                        "clis_stats": [
                            {"eng_usage": {"compute": [...], ...}},
                            ...
                        ],
                        "dev_stats": {"eng_usage": {"compute": [...], ...}}
                    }
                ]
            },
            ...
        ]
    }

    For each state, sum compute engine usage across all per-process entries
    (clis_stats). Falls back to device-level eng_usage when clis_stats is empty.
    Timestamps are approximated backwards from now using ms_interval.

    Returns [[timestamp_iso, usage_percent], ...]
    """
    pattern    = str(METRICS_DIR / "qmassa1-*-tool-generated.json")
    candidates = glob.glob(pattern)
    if not candidates:
        return []

    latest_path = max(candidates, key=os.path.getmtime)
    try:
        with open(latest_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    states = data.get("states") or []
    if not isinstance(states, list) or not states:
        return []

    ms_interval = 1500
    try:
        ms_interval = int(data.get("args", {}).get("ms_interval", ms_interval))
    except (TypeError, ValueError):
        pass
    dt_seconds = max(ms_interval / 1000.0, 0.1)

    samples: List[float] = []
    for state in states:
        try:
            devs_state = state.get("devs_state") or []
            if not devs_state:
                continue
            dev = devs_state[0]

            clis_stats = dev.get("clis_stats") or []
            values: List[float] = []

            if clis_stats:
                for cli in clis_stats:
                    eng_usage = (cli.get("eng_usage") or {}).get("compute") or []
                    if not eng_usage:
                        continue
                    try:
                        values.append(float(eng_usage[-1]))
                    except (TypeError, ValueError):
                        continue
            else:
                # Fallback to device-level eng_usage
                dev_stats = dev.get("dev_stats") or {}
                eng_usage = dev_stats.get("eng_usage") or {}
                if isinstance(eng_usage, dict):
                    for _, arr in eng_usage.items():
                        if not arr:
                            continue
                        try:
                            values.append(float(arr[-1]))
                        except (TypeError, ValueError):
                            continue

            if not values:
                continue

            gpu_busy = sum(values)
            samples.append(max(0.0, min(100.0, gpu_busy)))
        except Exception:
            continue

    if not samples:
        return []

    now   = datetime.now()
    start = now - timedelta(seconds=dt_seconds * (len(samples) - 1))
    return [
        [(start + timedelta(seconds=dt_seconds * i)).isoformat(), usage]
        for i, usage in enumerate(samples)
    ]


def build_power_series() -> List[List]:
    """
    Parse pcm.csv (Intel PCM output, if present).
    Each entry: [timestamp_iso, package0_watts, package1_watts, ...]
    Power is derived by differentiating Joule energy counters.
    Returns [] if PCM data is unavailable.
    """
    try:
        with PCM_CSV.open() as f:
            reader = csv.reader(f)

            # PCM uses two header rows: long labels (row 1), short labels (row 2)
            header1 = next(reader, None)
            header2 = next(reader, None)
            if not header1 or not header2:
                return []

            date_idx = next(
                (i for i, c in enumerate(header2) if c.strip().lower() == "date"), 0
            )
            time_idx = next(
                (i for i, c in enumerate(header2) if c.strip().lower() == "time"),
                1 if len(header2) > 1 else 0,
            )

            energy_indices = [
                i for i, c in enumerate(header1)
                if "energy" in c.lower() and "joule" in c.lower()
            ]
            if not energy_indices:
                return []

            max_idx   = max(max(energy_indices), date_idx, time_idx)
            data_rows = [r for r in reader if r and len(r) > max_idx]

        if len(data_rows) < 2:
            return []

        def parse_ts(d: str, t: str) -> Optional[datetime]:
            ts_str = f"{d} {t}"
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(ts_str, fmt)
                except ValueError:
                    continue
            return None

        series: List[List] = []
        prev_row      = data_rows[0]
        prev_ts       = parse_ts(prev_row[date_idx].strip(), prev_row[time_idx].strip())
        prev_energies = [float(prev_row[i]) for i in energy_indices]

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
            except (ValueError, IndexError):
                prev_ts = cur_ts
                continue

            powers = [
                (ec - ep) / dt if ec >= ep else 0.0
                for ep, ec in zip(prev_energies, cur_energies)
            ]
            series.append([cur_ts.isoformat()] + powers)
            prev_ts       = cur_ts
            prev_energies = cur_energies

        return series

    except (FileNotFoundError, OSError):
        return []


# ---------------------------------------------------------------------------
# Platform info
# ---------------------------------------------------------------------------

def get_platform_info() -> Dict[str, Any]:
    """Return a hardware summary: Processor, iGPU, NPU, Memory, Storage."""

    def _format_gb(size_bytes: int, is_storage: bool = False) -> str:
        gb = size_bytes / 1024 ** 3
        if is_storage:
            tb = gb / 931
            return f"{round(tb)} TB" if abs(tb - round(tb)) < 0.05 else f"{tb:.2f} TB"
        return f"{math.ceil(gb)} GB"

    def _cpu_model() -> str:
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
        return platform.processor() or "Intel Processor"

    def _igpu() -> str:
        try:
            out = subprocess.check_output(["lspci", "-nn"], text=True, timeout=5)
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            return "Intel Graphics"
        for line in out.splitlines():
            if "VGA compatible controller" in line and "Intel" in line:
                if "]" in line:
                    name = line.split("]", 1)[-1].strip(" :")
                    if name:
                        return name
                return "Intel Graphics"
        return "Intel Graphics"

    def _npu() -> str:
        try:
            out = subprocess.check_output(["lspci", "-nn"], text=True, timeout=5)
            for line in out.splitlines():
                if "AI Boost" in line or "NPU" in line.upper():
                    return line.split(":", 1)[-1].strip()
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            pass
        return "Intel AI Boost"

    memory_str = "--"
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    memory_str = _format_gb(int(line.split()[1]) * 1024)
                    break
    except OSError:
        pass

    storage_str = "--"
    try:
        storage_str = _format_gb(shutil.disk_usage("/").total, is_storage=True)
    except OSError:
        pass

    return {
        "Processor": _cpu_model(),
        "iGPU":      _igpu(),
        "NPU":       _npu(),
        "Memory":    memory_str,
        "Storage":   storage_str,
    }


# ---------------------------------------------------------------------------
# Metrics payload
# ---------------------------------------------------------------------------

def build_metrics_payload() -> Dict[str, Any]:
    """
    Assemble the full metrics payload returned by GET /metrics.

    Shape:
    {
        "cpu_utilization": [[iso_ts, pct], ...],
        "gpu_utilization": [[iso_ts, pct], ...],
        "npu_utilization": [[iso_ts, pct], ...],
        "memory":          [[iso_ts, total_gb, used_gb, free_gb, pct], ...],
        "power":           [[iso_ts, watts, ...], ...]
    }
    """
    return {
        "cpu_utilization": build_cpu_series(),
        "gpu_utilization": build_gpu_series(),
        "npu_utilization": build_npu_series(),
        "memory":          build_memory_series(),
        "power":           build_power_series(),
    }
