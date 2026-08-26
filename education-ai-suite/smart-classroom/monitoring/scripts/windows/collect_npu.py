import os
import time
import csv
import subprocess
import queue
import threading
from datetime import datetime
import logging
from utils.config_loader import config

from monitoring.scripts.windows.gpu_engines import (
    ENGINE_OBJECT,
    ENGTYPE_NEURAL,
    classify_adapters,
    enumerate_engines,
    sample_utilization,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_NPU_BUCKET = "npu"


def get_npu_instances():
    """Return the "GPU Engine" instances that belong to a dedicated NPU adapter.

    Instances are per-process and come and go with the workload, so this is
    re-enumerated on every sample. An integrated GPU also exposes a Neural
    engine; adapters that additionally expose a 3D engine are therefore skipped
    so their AI work is not double counted as NPU (collect_gpu.py owns the
    render GPU's Neural engine).
    """
    engines = enumerate_engines()
    _render_adapters, npu_adapters = classify_adapters(engines)
    return [
        inst
        for inst, luid, engtype in engines
        if luid in npu_adapters and engtype == ENGTYPE_NEURAL
    ]


def get_npu_utilization():
    """Total NPU utilization percentage summed over every process using it."""
    instances = get_npu_instances()
    if not instances:
        return 0.0
    totals = sample_utilization((inst, _NPU_BUCKET) for inst in instances)
    return totals.get(_NPU_BUCKET, 0.0)


def start_npu_monitoring(interval_seconds, stop_event, output_dir=None):
    if output_dir is None:
        output_dir = os.getcwd()
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if get_npu_instances():
        _monitor_via_pdh(interval_seconds, stop_event, output_dir)
    else:
        logger.warning(
            f"No dedicated NPU adapter found in the '{ENGINE_OBJECT}' counters; "
            "falling back to the level-zero utilization tool."
        )
        _monitor_via_level_zero(interval_seconds, stop_event, output_dir)


def _open_npu_csv(output_dir):
    """Open npu_metrics.csv for append, writing the header on first creation."""
    npu_file = os.path.join(output_dir, "npu_metrics.csv")
    mode = 'a' if os.path.exists(npu_file) else 'w'
    file = open(npu_file, mode, newline='', encoding='utf-8')
    writer = csv.writer(file)
    if mode == 'w':
        writer.writerow(["timestamp", "total_npu_utilization"])
        file.flush()
    return file, writer


def _monitor_via_pdh(interval_seconds, stop_event, output_dir):
    """Sample the NPU adapter's Neural engine counters once per interval."""
    logger.info("Started NPU monitoring (performance counters)")
    try:
        file, writer = _open_npu_csv(output_dir)
        with file:
            while not stop_event.is_set():
                start_time = time.perf_counter()
                timestamp = datetime.now().isoformat(timespec="milliseconds")
                try:
                    utilization = get_npu_utilization()
                except Exception as e:
                    logger.error(f"Error reading NPU utilization: {e}")
                    utilization = 0.0
                writer.writerow([timestamp, utilization])
                file.flush()

                elapsed_time = time.perf_counter() - start_time
                stop_event.wait(max(0, interval_seconds - elapsed_time))
    except Exception as e:
        logger.error(f"Error in NPU monitoring: {e}")
    finally:
        logger.info("NPU monitoring terminated.")


def _monitor_via_level_zero(interval_seconds, stop_event, output_dir):
    """Fallback: stream utilization from the bundled level-zero sample tool."""
    npu_relative_path = config.monitoring.npu_exe_path
    app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    exe_path = os.path.join(app_root, npu_relative_path)

    if not os.path.exists(exe_path):
        logger.error(f"NPU exe not found at {exe_path}")
        return

    process = subprocess.Popen(
        [exe_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    logger.info("Started NPU monitoring (real-time streaming)")

    try:
        file, writer = _open_npu_csv(output_dir)
        with file:
            last_write_time = time.time()
            latest_util = None
            lines = queue.Queue()

            def read_output():
                for output_line in process.stdout:
                    lines.put(output_line)

            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()

            while not stop_event.is_set():
                try:
                    line = lines.get(timeout=min(interval_seconds, 0.5))
                except queue.Empty:
                    if process.poll() is not None:
                        logger.error(
                            f"{os.path.basename(exe_path)} exited with code "
                            f"{process.returncode}; no NPU samples collected."
                        )
                        break
                    continue

                if "Utilization" in line:
                    try:
                        latest_util = float(line.split(":")[1].replace("%", "").strip())
                    except Exception:
                        latest_util = 0.0

                # Only emit once the tool has actually reported a value, so a
                # startup banner cannot be logged as 0% utilization.
                now = time.time()
                if latest_util is not None and now - last_write_time >= interval_seconds:
                    timestamp = datetime.now().isoformat(timespec="milliseconds")
                    writer.writerow([timestamp, latest_util])
                    file.flush()
                    last_write_time = now

            logger.info("Stopping NPU monitoring...")

    except Exception as e:
        logger.error(f"Error in NPU monitoring: {e}")

    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except Exception:
                process.kill()

        logger.info("NPU monitoring terminated.")
