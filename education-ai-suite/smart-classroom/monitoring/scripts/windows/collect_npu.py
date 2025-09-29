import os
import time
import csv
import threading
import subprocess
from datetime import datetime
import logging
from utils.config_loader import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_npu_monitoring(interval_seconds, stop_event, output_dir=None):
    if output_dir is None:
        output_dir = os.getcwd()
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    npu_file = os.path.join(output_dir, "npu_metrics.csv")
    mode = 'a' if os.path.exists(npu_file) else 'w'

    # Updated exe path relative to your project structure
    npu_relative_path = config.monitoring.npu_exe_path
    exe_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", npu_relative_path))
    exe_path = os.path.abspath(exe_path)

    if not os.path.exists(exe_path):
        logger.error(f"NPU exe not found at {exe_path}")
        return

    try:
        with open(npu_file, mode, newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if mode == 'w':
                writer.writerow(["timestamp", "total_npu_utilization"])
                file.flush()

            while not stop_event.is_set():
                start_time = time.perf_counter()
                timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

                try:
                    # Run the exe and capture its stdout
                    result = subprocess.run(
                        [exe_path],
                        capture_output=True,
                        text=True,
                        timeout=interval_seconds
                    )
                    output = result.stdout.splitlines()
                    utilization = None
                    # Parse the last line that contains "Utilization : X %"
                    for line in reversed(output):
                        if "Utilization" in line:
                            try:
                                utilization = float(line.split(":")[1].replace("%", "").strip())
                                break
                            except Exception:
                                utilization = 0.0

                    if utilization is None:
                        utilization = 0.0

                    writer.writerow([timestamp, utilization])
                    file.flush()
                except subprocess.TimeoutExpired:
                    writer.writerow([timestamp, 0.0])
                    file.flush()
                except Exception as e:
                    logger.error(f"Error in NPU monitoring: {e}")
                    writer.writerow([timestamp, 0.0])
                    file.flush()

                elapsed_time = time.perf_counter() - start_time
                stop_event.wait(max(0, interval_seconds - elapsed_time))

    except KeyboardInterrupt:
        logger.info("NPU monitoring stopped by user")
