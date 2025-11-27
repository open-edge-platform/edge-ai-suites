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

    # Path to your NPU exe
    npu_relative_path = config.monitoring.npu_exe_path
    exe_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", npu_relative_path)
    )

    if not os.path.exists(exe_path):
        logger.error(f"NPU exe not found at {exe_path}")
        return

    process = subprocess.Popen(
        [exe_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    logger.info("Started NPU monitoring (real-time streaming)")

    try:
        with open(npu_file, mode, newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if mode == 'w':
                writer.writerow(["timestamp", "total_npu_utilization"])
                file.flush()

            last_write_time = 0
            latest_util = 0.0

            while not stop_event.is_set():
                line = process.stdout.readline()

                if not line:
                    if process.poll() is not None: 
                        break
                    continue

                if "Utilization" in line:
                    try:
                        latest_util = float(line.split(":")[1].replace("%", "").strip())
                    except:
                        latest_util = 0.0

                now = time.time()
                if now - last_write_time >= interval_seconds:
                    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
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
            except:
                process.kill()

        logger.info("NPU monitoring terminated.")

