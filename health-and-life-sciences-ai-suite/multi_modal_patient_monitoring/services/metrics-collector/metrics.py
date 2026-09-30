"""
Metrics collection and parsing utilities for the metrics-collector service.

Reads metric files written by background OS-level collectors.
"""

import csv
import glob
import json
import logging
import math
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

METRICS_DIR = Path(os.getenv("METRICS_DIR", "/tmp/results"))
CPU_LOG     = METRICS_DIR / "cpu_usage.log"
NPU_CSV     = METRICS_DIR / "npu_usage.csv"
MEM_LOG     = METRICS_DIR / "memory_usage.log"
PCM_CSV     = METRICS_DIR / "pcm.csv"

# Intel GPU engine classes reported by qmassa (i915 / Xe drivers):
#   rcs  – render / 3D            ccs  – compute
#   bcs  – blitter (copy)         vcs  – video decode/encode
#   vecs – video enhancement
# "compute" is kept for drivers that expose a single aggregate engine.
# Empty (the default) means "consider every engine the device reports", which
# is what makes GPU utilisation reflect both render and compute work.
GPU_ENGINES = tuple(
    e.strip().lower()
    for e in os.getenv("METRICS_GPU_ENGINES", "").split(",")
    if e.strip()
)

# The qmassa JSON is rewritten in full on every qmassa update (~1.5 s), so the
# derived series must be cached rather than recomputed per poll.
#
# The original cache keyed on (path, mtime, size) alone, which looked correct
# but never hit in practice: qmassa rewrites the file continuously, so mtime
# and size change between every single poll. The result was a full json.load()
# of an ever-growing document on every request. Measured in production that
# reached 2.4 GB (596 MB/hour, unbounded), which pinned the container at 112%
# CPU / 4.2 GiB RSS and made every endpoint -- including ones that never touch
# qmassa -- take 20-40 s behind it.
#
# Two independent guards now bound that cost, because the file is written by an
# external tool this service does not control:
#
#   _GPU_MIN_REPARSE_SECONDS -- a wall-clock floor between parses. This is the
#       guard that actually works, since it does not depend on the file
#       appearing unchanged.
#   _GPU_MAX_JSON_BYTES      -- a hard ceiling. Refusing to parse an absurdly
#       large document is what prevents an OOM: json.load() needs roughly 6-8x
#       the file size in RAM, so a multi-GB file can take the whole host down.
#
# collect_gpu.sh now recycles the file on a bounded window, so the ceiling
# should never be reached; it is kept as a backstop for the case where that
# script is not the one running (e.g. an older base image).
_GPU_CACHE: Dict[str, Any] = {"key": None, "series": [], "parsed_at": 0.0}

_GPU_MIN_REPARSE_SECONDS = float(os.getenv("METRICS_GPU_MIN_REPARSE_SECONDS", "5"))
_GPU_MAX_JSON_BYTES = int(
    float(os.getenv("METRICS_GPU_MAX_JSON_MB", "256")) * 1024 * 1024
)

# Only the newest points are ever plotted; keeping a bounded rolling window
# means the series survives a qmassa restart (when the file is recreated empty)
# instead of collapsing to whatever the fresh file contains.
_GPU_MAX_POINTS = int(os.getenv("METRICS_GPU_MAX_POINTS", "300"))


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


def _engine_usage_max(eng_usage: Any) -> Optional[float]:
    """Return the busiest engine's latest utilisation from an ``eng_usage`` map.

    ``eng_usage`` maps an engine class (``rcs``, ``ccs``, ``bcs``, ``vcs``,
    ``vecs`` …) to a list of samples.  Engines are independent hardware units,
    so the busiest one — not their sum — represents how loaded the GPU is;
    summing would report >100 % whenever render and compute run concurrently.

    Returns None when no engine reports a usable sample.
    """
    if not isinstance(eng_usage, dict):
        return None
    values: List[float] = []
    for engine, samples in eng_usage.items():
        if GPU_ENGINES and str(engine).lower() not in GPU_ENGINES:
            continue
        if not isinstance(samples, list) or not samples:
            continue
        try:
            values.append(float(samples[-1]))
        except (TypeError, ValueError):
            continue
    return max(values) if values else None


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
                        "eng_names":  ["bcs", "ccs", "rcs", "vcs", "vecs"],
                        "clis_stats": [
                            {"eng_usage": {"rcs": [...], "ccs": [...], ...}},
                            ...
                        ],
                        "dev_stats": {"eng_usage": {"rcs": [...], "ccs": [...], ...}}
                    }
                ]
            },
            ...
        ]
    }

    Engine names are driver-specific (Intel i915/Xe report ``rcs``/``ccs``/
    ``bcs``/``vcs``/``vecs``; there is no engine literally named "compute").
    Every engine the device reports is therefore considered, unless
    ``METRICS_GPU_ENGINES`` restricts the set.

    Device-level ``dev_stats.eng_usage`` is preferred because it is already
    aggregated across clients; per-client ``clis_stats`` is summed per engine
    only as a fallback.

    The result is cached against the file's (mtime, size) because the JSON is
    large (~100 MB) and rewritten continuously.  A partially-flushed file
    raises JSONDecodeError; in that case the last good series is returned so
    the chart holds its data instead of blanking.

    Returns [[timestamp_iso, usage_percent], ...]
    """
    pattern    = str(METRICS_DIR / "qmassa1-*-tool-generated.json")
    candidates = glob.glob(pattern)
    if not candidates:
        return []

    latest_path = max(candidates, key=os.path.getmtime)
    try:
        stat = os.stat(latest_path)
        cache_key = (latest_path, stat.st_mtime_ns, stat.st_size)
    except OSError:
        return _GPU_CACHE["series"]

    if _GPU_CACHE["key"] == cache_key:
        return _GPU_CACHE["series"]

    # Wall-clock throttle. The (mtime, size) check above is nearly useless on
    # its own because qmassa rewrites the file every ~1.5 s; this is the guard
    # that actually bounds how often the document is parsed.
    now_ts = time.monotonic()
    if (now_ts - _GPU_CACHE["parsed_at"]) < _GPU_MIN_REPARSE_SECONDS:
        return _GPU_CACHE["series"]

    # Hard ceiling: never json.load() a document large enough to OOM the host.
    # Serving a slightly stale series is always preferable to killing the box.
    if stat.st_size > _GPU_MAX_JSON_BYTES:
        _GPU_CACHE["parsed_at"] = now_ts
        logger.warning(
            "qmassa JSON %s is %.1f MB, above the %.1f MB parse ceiling; "
            "serving the last good GPU series. Is collect_gpu.sh recycling it?",
            latest_path,
            stat.st_size / 1024 / 1024,
            _GPU_MAX_JSON_BYTES / 1024 / 1024,
        )
        return _GPU_CACHE["series"]

    try:
        with open(latest_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        # qmassa was mid-write. Serve the previous good series rather than
        # dropping the chart to "Waiting for data…".
        _GPU_CACHE["parsed_at"] = now_ts
        return _GPU_CACHE["series"]

    states = data.get("states") or []
    if not isinstance(states, list) or not states:
        _GPU_CACHE["parsed_at"] = now_ts
        return _GPU_CACHE["series"]

    # Only the tail is ever plotted, so discard the rest before the per-state
    # work below instead of building thousands of points to throw them away.
    if len(states) > _GPU_MAX_POINTS:
        states = states[-_GPU_MAX_POINTS:]

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

            usage = _engine_usage_max((dev.get("dev_stats") or {}).get("eng_usage"))

            if usage is None:
                # Fallback: aggregate per-client usage per engine, then take
                # the busiest engine.
                per_engine: Dict[str, float] = {}
                for cli in dev.get("clis_stats") or []:
                    cli_usage = cli.get("eng_usage")
                    if not isinstance(cli_usage, dict):
                        continue
                    for engine, arr in cli_usage.items():
                        if GPU_ENGINES and str(engine).lower() not in GPU_ENGINES:
                            continue
                        if not isinstance(arr, list) or not arr:
                            continue
                        try:
                            per_engine[engine] = per_engine.get(engine, 0.0) + float(arr[-1])
                        except (TypeError, ValueError):
                            continue
                usage = max(per_engine.values()) if per_engine else None

            if usage is None:
                continue

            samples.append(max(0.0, min(100.0, usage)))
        except Exception:
            continue

    if not samples:
        _GPU_CACHE["parsed_at"] = now_ts
        return _GPU_CACHE["series"]

    now   = datetime.now()
    start = now - timedelta(seconds=dt_seconds * (len(samples) - 1))
    series = [
        [(start + timedelta(seconds=dt_seconds * i)).isoformat(), usage]
        for i, usage in enumerate(samples)
    ]

    _GPU_CACHE["key"] = cache_key
    _GPU_CACHE["series"] = series[-_GPU_MAX_POINTS:]
    _GPU_CACHE["parsed_at"] = now_ts
    return _GPU_CACHE["series"]


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

def build_metrics_payload(window: int = 60) -> Dict[str, Any]:
    """
    Assemble the full metrics payload returned by GET /metrics.

    Only the last ``window`` samples of each series are returned so the
    JSON payload stays small (< 5 KB) and the UI 4-second fetch timeout
    is never hit.  The UI trims further to its own display window.

    Shape:
    {
        "cpu_utilization": [[iso_ts, pct], ...],
        "gpu_utilization": [[iso_ts, pct], ...],
        "npu_utilization": [[iso_ts, pct], ...],
        "memory":          [[iso_ts, total_gb, used_gb, free_gb, pct], ...],
        "power":           [[iso_ts, watts, ...], ...]
    }
    """
    def tail(series: List[List], n: int) -> List[List]:
        return series[-n:] if len(series) > n else series

    return {
        "cpu_utilization": tail(build_cpu_series(), window),
        "gpu_utilization": tail(build_gpu_series(), window),
        "npu_utilization": tail(build_npu_series(), window),
        "memory":          tail(build_memory_series(), window),
        "power":           tail(build_power_series(), window),
    }
