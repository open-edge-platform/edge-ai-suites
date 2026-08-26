import os
import time
import csv
import win32pdh
import logging
from datetime import datetime

from monitoring.scripts.windows.gpu_engines import (
    ENGTYPE_COMPUTE,
    ENGTYPE_NEURAL,
    classify_adapters,
    enumerate_engines,
    sample_utilization,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CSV column -> the "GPU Engine" engine types summed into it. Only render
# adapters (those exposing a 3D engine) contribute; the dedicated NPU adapter is
# owned by collect_npu.py so its Neural engine is never counted here.
#
# Keep Neural at index 9: monitor.py and ResourceUtilizationAccordion consume
# this CSV by index. Compute is separate so Neural matches Task Manager's
# Neural engine rather than combining two physically distinct engines.
ENGINE_BUCKETS = {
    "3D": ("3d",),
    "VideoEncode": ("videoencode",),
    "VideoDecode": ("videodecode",),
    "VideoProcessing": ("videoprocessing",),
    "Copy": ("copy",),
    "Neural": (ENGTYPE_NEURAL,),
    "ComputeEngine": (ENGTYPE_COMPUTE,),
}
CSV_COLUMNS = list(ENGINE_BUCKETS)

def get_gpu_memory_total():
    try:
        query = win32pdh.OpenQuery()
        counters_dedicated = []
        counters_shared = []

        instances = win32pdh.EnumObjectItems(None, None, "GPU Adapter Memory", win32pdh.PERF_DETAIL_WIZARD)[1]
        for inst in instances:
            counters_dedicated.append(
                win32pdh.AddCounter(query, f"\\GPU Adapter Memory({inst})\\Dedicated Usage")
            )
            counters_shared.append(
                win32pdh.AddCounter(query, f"\\GPU Adapter Memory({inst})\\Shared Usage")
            )

        win32pdh.CollectQueryData(query)

        total_dedicated = 0
        total_shared = 0

        for c in counters_dedicated:
            _, val = win32pdh.GetFormattedCounterValue(c, win32pdh.PDH_FMT_LARGE)
            total_dedicated += val

        for c in counters_shared:
            _, val = win32pdh.GetFormattedCounterValue(c, win32pdh.PDH_FMT_LARGE)
            total_shared += val

        win32pdh.CloseQuery(query)

        dedicated_mb = total_dedicated / (1024 * 1024)
        shared_mb = total_shared / (1024 * 1024)
        total_mb = dedicated_mb + shared_mb

        return total_mb, dedicated_mb, shared_mb

    except Exception as e:
        logger.error(f"Error: {e}")
        return None, None, None


def get_gpu_utilization(settle_seconds=0.2):
    """Per-engine GPU utilization, keyed by CSV column name (see ENGINE_BUCKETS)."""
    engines = enumerate_engines()
    render_adapters, _npu_adapters = classify_adapters(engines)

    engtype_to_column = {
        engtype: column
        for column, engtypes in ENGINE_BUCKETS.items()
        for engtype in engtypes
    }

    wanted = [
        (inst, engtype_to_column[engtype])
        for inst, luid, engtype in engines
        if luid in render_adapters and engtype in engtype_to_column
    ]

    totals = sample_utilization(wanted, settle_seconds=settle_seconds)
    return {column: totals.get(column, 0.0) for column in CSV_COLUMNS}


def start_gpu_monitoring(interval_seconds, stop_event, output_dir=None):
    if output_dir is None:
        output_dir = os.getcwd()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    gpu_file = os.path.join(output_dir, "gpu_metrics.csv")
    mode = 'a' if os.path.exists(gpu_file) else 'w'
    try:
        with open(gpu_file, mode, newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if mode == 'w':
                writer.writerow(
                    ["timestamp", "total_memory_mb", "dedicated_memory_mb", "shared_memory_mb"]
                    + [f"{column}_utilization_percent" for column in CSV_COLUMNS]
                )
                file.flush()

            while not stop_event.is_set():
                start_time = time.perf_counter()
                try:
                    total, dedicated, shared = get_gpu_memory_total()
                    # Use the full configured interval as the PDH observation
                    # window. A 0.2s snapshot every 2s aliases bursty inference
                    # into misleading 0/100 spikes unlike Task Manager.
                    engine_totals = get_gpu_utilization(
                        settle_seconds=interval_seconds
                    )
                    timestamp = datetime.now().isoformat(timespec="milliseconds")

                    if total is not None:
                        writer.writerow(
                            [timestamp, total, dedicated, shared]
                            + [engine_totals[column] for column in CSV_COLUMNS]
                        )
                    else:
                        writer.writerow([timestamp, 0.0, 0.0, 0.0] + [0.0] * len(CSV_COLUMNS))
                    file.flush()
                except Exception as e:
                    logger.error(f"Error collecting GPU metrics: {e}")
                    timestamp = datetime.now().isoformat(timespec="milliseconds")
                    writer.writerow([timestamp, 0.0, 0.0, 0.0] + [0.0] * len(CSV_COLUMNS))
                    file.flush()

                elapsed_time = time.perf_counter() - start_time
                stop_event.wait(max(0, interval_seconds - elapsed_time))
    except KeyboardInterrupt:
        logger.info("\nGPU monitoring stopped by user.")