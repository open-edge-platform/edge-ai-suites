import subprocess
import pandas as pd
import os
import csv
from datetime import datetime, timezone
import logging
import ctypes
import shutil
import atexit
import stat
from utils.config_loader import config 
logger = logging.getLogger(__name__)

SOCWATCH_PATH = config.monitoring.socwatch_path
OUTPUT_PREFIX = "SoCWatchOutput"
OUTPUT_DIR = config.monitoring.execution_logs   
AUTOMATIC_SUMMARY_CSV = os.path.join(OUTPUT_DIR, "Automation_Summary.csv")

@atexit.register
def cleanup_socwatch_outputs():
    try:
        if os.path.exists(OUTPUT_DIR):
            for file in os.listdir(OUTPUT_DIR):
                if file.startswith(OUTPUT_PREFIX) or file == "Automation_Summary.csv":
                    file_path = os.path.join(OUTPUT_DIR, file)
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.error(f"Failed to remove {file_path}: {e}")
                        return
            logger.info("Removed SoCwatch output files")
    except Exception as e:
        logger.error(f"Error cleaning up SoCWatch output files: {e}")

def check_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_socwatch_quick(collection_duration, interval_ms):
    os.makedirs(OUTPUT_DIR, exist_ok=True)  

    cmd = [
        SOCWATCH_PATH,
        "-f", "power",
        "-r", "auto",
        "-m",
        "-n", str(interval_ms),
        "-t", str(collection_duration),
        "-o", os.path.join(OUTPUT_DIR, OUTPUT_PREFIX)  
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logging.debug(result.stdout.strip())
        if result.stderr.strip():
            logging.warning(result.stderr.strip())
            return False
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ SoCWatch execution error: {e.stderr or e}")
        return False

def gmt_to_local_timestamp(gmt_string):
    try:
        gmt_time = datetime.strptime(gmt_string.replace(" GMT", ""), "%Y-%m-%d %H:%M:%S")
        gmt_time = gmt_time.replace(tzinfo=timezone.utc)
        local_time = gmt_time.astimezone()
        return local_time.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception as e:
        logger.error(f"Error converting GMT timestamp: {e}")
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

def extract_average_power_from_automatic_summary(csv_file):
    try:
        with open(csv_file, 'rb') as f:
            f.seek(0, 2)
            pos = f.tell() -2
            if pos< 0:
                return None, None
            while pos >= 0:
                f.seek(pos)
                if f.read(1)  == b'\n':  
                    break
                pos -= 1
            f.seek(pos + 1)
            last_line = f.readline().decode('utf-8', errors='ignore').strip()

        if not last_line:
            return None, None
        row = list(csv.reader([last_line]))[0]

        if len(row) >= 4:
            try:
                gmt_timestamp = row[1]
                avg_power_mw = float(row[3])
                local_timestamp = gmt_to_local_timestamp(gmt_timestamp)
                return local_timestamp, avg_power_mw
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing values from last row: {e}")
                return None, None
        else:
            logger.error(f"Insufficient columns in last row: {len(row)} columns found")
            return None, None

    except Exception as e:
        logger.error(f"Error reading automatic summary CSV: {e}")
        return None, None


def start_power_monitoring(interval_seconds, stop_event, output_dir=None):
    if not check_admin():
        logger.error("Administrator privileges required for power monitoring")
        return

    output_dir = output_dir or os.getcwd()
    os.makedirs(output_dir, exist_ok=True)

    power_file = os.path.join(output_dir, "power_metrics.csv")
    mode = 'a' if os.path.exists(power_file) else 'w'

    def write_power(ts, power_w):
        writer.writerow([ts, power_w])
        f.flush()

    try:
        with open(power_file, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if mode == 'w':
                writer.writerow(['timestamp', 'power_usage(w)'])
                f.flush()

            while not stop_event.is_set():
                try:
                    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    power_w = 0.0  
                    if run_socwatch_quick(collection_duration=interval_seconds, interval_ms=500) and os.path.exists(AUTOMATIC_SUMMARY_CSV):
                        local_timestamp, avg_power_mw = extract_average_power_from_automatic_summary(AUTOMATIC_SUMMARY_CSV)
                        if local_timestamp and avg_power_mw:
                            timestamp = local_timestamp
                            power_w = round(avg_power_mw / 1000.0, 3)
                        else:
                            logger.error("Could not extract power data from automatic summary")
                    else:
                        logger.error("SoCWatch failed or automatic summary CSV not found")

                    if(power_w!=0):
                        write_power(timestamp, power_w)

                except Exception as e:
                    logger.error(f"Power monitoring error: {e}")

    except KeyboardInterrupt:
        logger.info("Power monitoring stopped by user.")
    except Exception as e:
        logger.error(f"Power monitoring error: {e}")