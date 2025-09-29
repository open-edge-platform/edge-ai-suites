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

collector_scripts = {
    "cpu_collector": start_cpu_monitoring,
    "gpu_collector": start_gpu_monitoring if os_name == "Windows" else None,
    "memory_collector": start_memory_monitoring,
    "power_collector":start_power_monitoring if os_name == "Windows" else None,
    "npu_collector": start_npu_monitoring if os_name == "Windows" else None
}

def read_log_file(file_path, indices):
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
            data = []
            for line in lines[1:]:  # Skip header
                values = line.strip().split(",")
                timestamp = values[0]
                data_points = [float(values[i]) for i in indices]
                data.append([timestamp] + data_points)
            return data
    except Exception as e:
        logger.error(f"Error reading log file {file_path}: {e}")
        return []

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
            logger.warning(f"Log file {file_path} does not exist.")
    return latest_utilization

def start_monitoring(metrics_logs="./logs"):
    global stop_event
    stop_event = threading.Event()
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
    stop_event.set()
    for mt in monitoring_threads:
        mt.join()
    logger.info("Stopped monitoring processes")

def get_metrics(metrics_logs="./logs"):
    latest_utilization = monitor_logs(metrics_logs)
    logger.info("Returning latest utilization metrics")
    return latest_utilization