import threading
import os
import time
from utils.config_loader import config 
from monitoring.scripts.common.collect_cpu import start_cpu_monitoring
from monitoring.scripts.windows.collect_gpu import start_gpu_monitoring
from monitoring.scripts.common.collect_memory import start_memory_monitoring
from monitoring.scripts.windows.collect_power import start_power_monitoring
from monitoring.scripts.windows.collect_npu import start_npu_monitoring
import logging
import platform

logger = logging.getLogger(__name__)
INTERVAL_SECONDS = config.monitoring.interval
OUTPUT_DIR = config.monitoring.logs_dir
monitoring_threads=[]
os_name = platform.system()
stop_event = None

collector_scripts = {
    "cpu_collector": start_cpu_monitoring,
    "gpu_collector": start_gpu_monitoring if os_name == "Windows" else None,
    "memory_collector": start_memory_monitoring,
    "power_collector":start_power_monitoring if os_name == "Windows" else None,
    "npu_collector": start_npu_monitoring if os_name == "Windows" else None
}

# /metrics is polled for the whole length of a session, so re-reading each CSV
# from byte zero would make every call cost O(session length). Instead we keep
# the parsed rows per file and resume from the byte offset we stopped at.
#   _read_state: {abs_path: {"offset": int, "rows": list}}
#   _metrics_cache: {metrics_logs_dir: (monotonic_ts, payload)}
_read_state = {}
_read_lock = threading.Lock()
_metrics_cache = {}
_metrics_cache_lock = threading.Lock()

def _reset_caches():
    """Drop all incremental-read state (called when a new monitoring run starts)."""
    with _read_lock:
        _read_state.clear()
    with _metrics_cache_lock:
        _metrics_cache.clear()

def read_log_file(file_path, indices):
    """Return every parsed row of a collector CSV, reading only what's new.

    Rows are [timestamp, *floats at `indices`]. A malformed row is skipped on
    its own rather than discarding the file, and a partially written trailing
    line is left unconsumed so it gets picked up once complete.
    """
    key = os.path.abspath(file_path)
    with _read_lock:
        try:
            size = os.path.getsize(key)
        except OSError as e:
            logger.debug(f"Cannot stat log file {key}: {e}")
            return []

        state = _read_state.get(key)
        # A shrinking file means it was truncated or replaced - start over.
        if state is None or size < state["offset"]:
            state = {"offset": 0, "rows": []}
            _read_state[key] = state

        if size > state["offset"]:
            try:
                # Binary mode: text-mode tell()/seek() offsets are opaque and
                # would not line up with the byte counts we track here.
                with open(key, "rb") as f:
                    f.seek(state["offset"])
                    chunk = f.read()
            except OSError as e:
                logger.error(f"Error reading log file {key}: {e}")
                return list(state["rows"])

            # Collectors flush per row, but a read can still land mid-write.
            end = chunk.rfind(b"\n") + 1
            if end:
                lines = chunk[:end].decode("utf-8", errors="replace").splitlines()
                if state["offset"] == 0 and lines:
                    lines = lines[1:]  # header
                for line in lines:
                    values = line.strip().split(",")
                    try:
                        state["rows"].append(
                            [values[0]] + [float(values[i]) for i in indices]
                        )
                    except (IndexError, ValueError):
                        logger.debug(f"Skipping malformed row in {key}: {line!r}")
                state["offset"] += end

        # Copy: the caller serializes this while later polls may append.
        return list(state["rows"])

def monitor_logs(metrics_logs):
    latest_utilization = {
        "cpu_utilization": [],
        "gpu_utilization": [],
        "memory": [],
        "power": [],
        "npu_utilization": []
    }

    log_files = {
        "cpu_utilization": (os.path.join(metrics_logs, "cpu_utilization.csv"), [1]),
        "gpu_utilization": (os.path.join(metrics_logs, "gpu_metrics.csv"), [1, 2, 3, 4, 5, 6,7,8,9]),
        "memory": (os.path.join(metrics_logs, "memory_metrics.csv"), [1, 2, 3,4]),
        "power": (os.path.join(metrics_logs, "power_metrics.csv"), [1]),
        "npu_utilization": (os.path.join(metrics_logs, "npu_metrics.csv"), [1])
    }

    for key, (file_path, indices) in log_files.items():
        if os.path.exists(file_path):
            latest_utilization[key] = read_log_file(file_path, indices)
        else:
            # Polled once per /metrics call, so keep it off the console.
            logger.debug(f"Log file {file_path} does not exist.")
    return latest_utilization

def is_monitoring_active():
    """Check if monitoring is currently active"""
    global stop_event
    return stop_event is not None and not stop_event.is_set()

def start_monitoring(metrics_logs="./logs"):
    global stop_event,monitoring_threads

    if is_monitoring_active():
        logger.info("Stopping existing monitoring before starting new one...")
        stop_monitoring()

    stop_event = threading.Event()
    _reset_caches()
    logger.info("Starting monitoring processes")
    monitoring_threads=[]
    for k,v in collector_scripts.items():
        if v is not None:
            monitoring_threads.append(threading.Thread(name=k,target=v, args=(INTERVAL_SECONDS,stop_event,metrics_logs), daemon=True))
    for mt in monitoring_threads:
        try:
            mt.start()
            logger.info(f'{mt.name} started')
        except Exception as e:
            logger.error(f"Error starting {mt.name}:{e}")

def stop_monitoring():
    global stop_event, monitoring_threads

    if stop_event is not None:
        stop_event.set()
    for mt in monitoring_threads:
        if mt.is_alive():
            mt.join()
    stop_event = None
    monitoring_threads = []

def get_metrics(metrics_logs="./logs"):
    # Nothing new can appear between samples, so collapse polls that arrive
    # faster than the collectors write (multiple clients, or a poll interval
    # shorter than the sampling interval).
    now = time.monotonic()
    with _metrics_cache_lock:
        cached = _metrics_cache.get(metrics_logs)
        if cached is not None and now - cached[0] < INTERVAL_SECONDS:
            return cached[1]

    latest_utilization = monitor_logs(metrics_logs)

    with _metrics_cache_lock:
        _metrics_cache[metrics_logs] = (now, latest_utilization)
    logger.debug("Returning latest utilization metrics")
    return latest_utilization