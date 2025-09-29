import os
import time
import csv
import win32pdh
import re
from collections import defaultdict
import threading
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def get_gpu_utilization():
    query = win32pdh.OpenQuery()
    counters = []

    _, instances = win32pdh.EnumObjectItems(None, None, "GPU Engine", win32pdh.PERF_DETAIL_WIZARD)
    engine_types = ["engtype_3D", "engtype_VideoEncode", "engtype_VideoDecode",
                    "engtype_VideoProcessing", "engtype_Copy", "engtype_Compute"]

    for inst in instances:
        for engine_type in engine_types:
            if re.search(engine_type, inst, re.IGNORECASE):
                try:
                    c = win32pdh.AddCounter(query, f"\\GPU Engine({inst})\\Utilization Percentage")
                    counters.append((c, engine_type))
                except Exception as e:
                    logger.info(f"Skipping {inst}: {e}")
    win32pdh.CollectQueryData(query)
    time.sleep(0.2)
    win32pdh.CollectQueryData(query)

    engine_totals = defaultdict(float)
    for c, engine_type in counters:
        try:
            _, val = win32pdh.GetFormattedCounterValue(c, win32pdh.PDH_FMT_DOUBLE)
            engine_totals[engine_type] += val
        except Exception:
            pass

    win32pdh.CloseQuery(query)
    return engine_totals


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
                writer.writerow([
                    "timestamp", "total_memory_mb", "dedicated_memory_mb", "shared_memory_mb",
                    "3D_utilization_percent", "VideoEncode_utilization_percent",
                    "VideoDecode_utilization_percent", "VideoProcessing_utilization_percent",
                    "Copy_utilization_percent", "Compute_utilization_percent"
                ])
                file.flush()

            while not stop_event.is_set():
                start_time = time.perf_counter()
                timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                try:
                    total, dedicated, shared = get_gpu_memory_total()
                    engine_totals = get_gpu_utilization()

                    if total is not None:
                        writer.writerow([
                            timestamp, total, dedicated, shared,
                            engine_totals.get("engtype_3D", 0.0),
                            engine_totals.get("engtype_VideoEncode", 0.0),
                            engine_totals.get("engtype_VideoDecode", 0.0),
                            engine_totals.get("engtype_VideoProcessing", 0.0),
                            engine_totals.get("engtype_Copy", 0.0),
                            engine_totals.get("engtype_Compute", 0.0)
                        ])
                    else:
                        writer.writerow([timestamp, 0.0, 0.0, 0.0] + [0.0]*6)
                    file.flush()
                except Exception as e:
                    print(f"Error: {e}")
                    writer.writerow([timestamp, 0.0, 0.0, 0.0] + [0.0]*6)
                    file.flush()

                elapsed_time = time.perf_counter() - start_time
                stop_event.wait(max(0, interval_seconds - elapsed_time))
    except KeyboardInterrupt:
        logger.info("\nGPU monitoring stopped by user.")