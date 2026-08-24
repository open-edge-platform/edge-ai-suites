import os
import csv
from datetime import datetime
import logging
import psutil # type: ignore

logger = logging.getLogger(__name__)

def start_cpu_monitoring(interval_seconds, stop_event, output_dir=None):
    if output_dir is None:
        output_dir = os.getcwd()
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    cpu_file = os.path.join(output_dir, "cpu_utilization.csv")
    mode = 'a' if os.path.exists(cpu_file) else 'w'

    # cpu_times_percent(interval=0) reports the delta since the previous call,
    # so it needs a reference point plus a real gap before the first sample.
    # Without both, the first row came back idle=0.0 — a fake 100% CPU spike
    # landing inside the first stage's window, which inflated the ASR row's
    # peak (and average) in every recorded session.
    psutil.cpu_times_percent(interval=0)

    try:
        with open(cpu_file, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if mode=='w':
                writer.writerow(['timestamp', 'total_cpu_utilization'])
                f.flush()
            while not stop_event.wait(interval_seconds):
                timestamp = datetime.now().isoformat(timespec="milliseconds")
                try:
                    cpu_times_percent = psutil.cpu_times_percent(interval=0)
                    total_cpu_utilization = 100.0 - cpu_times_percent.idle
                    writer.writerow([
                        timestamp,
                        total_cpu_utilization,
                    ])
                except Exception as e:
                    logger.error(f"Error: CPU monitoring error: {e}")
                    writer.writerow([timestamp, 0.0])
                f.flush()
    except KeyboardInterrupt:
        logger.info("CPU monitoring stopped by user.")
    except Exception as e:
        logger.error(f"Error: CPU monitoring error: {e}")