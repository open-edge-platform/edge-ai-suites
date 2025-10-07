import time
import os
import csv
from datetime import datetime
import logging
import psutil # type: ignore
import threading

logger = logging.getLogger(__name__)

def start_cpu_monitoring(interval_seconds, stop_event, output_dir=None):
    if output_dir is None:
        output_dir = os.getcwd()
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    cpu_file = os.path.join(output_dir, "cpu_utilization.csv")
    mode = 'a' if os.path.exists(cpu_file) else 'w'
    try:
        with open(cpu_file, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if mode=='w':
                writer.writerow(['timestamp', 'total_cpu_utilization'])
                f.flush()
            while not stop_event.is_set():
                timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                try:
                    cpu_times_percent = psutil.cpu_times_percent(interval=0)
                    total_cpu_utilization = 100.0 - cpu_times_percent.idle                
                    writer.writerow([
                        timestamp,
                        total_cpu_utilization,
                    ])
                    f.flush()
                except Exception as e:
                    logger.error(f"Error: CPU monitoring error: {e}")
                    writer.writerow([timestamp, 0.0])
                stop_event.wait(interval_seconds)
    except KeyboardInterrupt:
        logger.info("CPU monitoring stopped by user.")
    except Exception as e:
        logger.error(f"Error: CPU monitoring error: {e}")