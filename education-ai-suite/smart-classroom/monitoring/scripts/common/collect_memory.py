import os
import time
import csv
from datetime import datetime
import psutil # type: ignore
import logging
import threading

logger = logging.getLogger(__name__)

def start_memory_monitoring(interval_seconds, stop_event, output_dir=None):
    if output_dir is None:
        output_dir = os.getcwd()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    memory_file = os.path.join(output_dir, "memory_metrics.csv")
    mode = 'a' if os.path.exists(memory_file) else 'w'
    try:
        with open(memory_file, mode, newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if mode=='w':
                writer.writerow(["timestamp", "total_gb", "available_gb", "used_gb", "usage_percent"])
                file.flush()  
            while not stop_event.is_set():
                timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                try:
                    vm = psutil.virtual_memory()
                    total_gb = vm.total / (1024**3)
                    available_gb = vm.available / (1024**3)
                    used_gb = vm.used / (1024**3)
                    usage_percent = vm.percent

                    writer.writerow([timestamp, total_gb, available_gb, used_gb, usage_percent])
                    file.flush()  
                except Exception as e:
                    logger.error(f"Memory monitoring error: {e}")
                    writer.writerow([timestamp, 0.0, 0.0, 0.0, 0.0])
                    file.flush()
                stop_event.wait(interval_seconds)
    except KeyboardInterrupt:
        logger.info("\nMemory monitoring stopped by user.")