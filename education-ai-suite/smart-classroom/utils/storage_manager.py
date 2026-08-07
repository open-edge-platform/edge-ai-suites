import os
import io
import json, csv
from threading import Thread
from typing import Union, List, Dict, Tuple
from pathlib import Path
import logging

from utils.artifacts.pending_writes import PendingWrites

logger = logging.getLogger(__name__)

class StorageManager:
    @staticmethod
    def _ensure_dir(path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)

    @staticmethod
    def _prepare_json_data(path: str, data: dict, append: bool) -> list:
        if append and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    if isinstance(existing, list):
                        existing.append(data)
                        return existing
                    return [existing, data]
            except json.JSONDecodeError:
                return [data]
        return [data]  # Always return list

    @staticmethod
    def _render_payload(path: str, data: Union[str, dict], append: bool) -> str:
        if isinstance(data, dict):
            merged = StorageManager._prepare_json_data(path, data, append)
            return json.dumps(merged, indent=2, ensure_ascii=False)

        if append and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read() + data
        return data

    @staticmethod
    def _atomic_write_text(path: str, payload: str, newline: str = ""):
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", newline=newline, encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    @staticmethod
    def _write(path: str, data: Union[str, dict], append: bool):
        StorageManager._ensure_dir(path)
        payload = StorageManager._render_payload(path, data, append)
        StorageManager._atomic_write_text(path, payload)

    @staticmethod
    def save(path: str, data: Union[str, dict], append: bool = False):
        StorageManager._write(path, data, append)

    @staticmethod
    def save_async(path: str, data: Union[str, dict], append: bool = False):
        PendingWrites.inc()

        def _run():
            try:
                StorageManager._write(path, data, append)
            finally:
                PendingWrites.dec()

        Thread(target=_run).start()
        
    @staticmethod
    def save_csv(path: str, data: dict, headers: List[str], append: bool = True):
        StorageManager._ensure_dir(path)

        existing_rows = []
        if append and os.path.exists(path):
            with open(path, "r", newline="", encoding="utf-8") as f:
                existing_rows = list(csv.DictReader(f))

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=headers)
        writer.writeheader()
        writer.writerows(existing_rows)
        writer.writerow(data)
        StorageManager._atomic_write_text(path, buffer.getvalue())

    @staticmethod
    def update_csv(path: str, new_data: Dict[str, Union[str, int, float]]):
        StorageManager._ensure_dir(path)

        rows = []
        headers = list(new_data.keys())

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                for row in rows:
                    for key in row.keys():
                        if key not in headers:
                            headers.append(key)

        if rows:
            rows[0].update(new_data)
        else:
            rows = [new_data]

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        StorageManager._atomic_write_text(path, buffer.getvalue())
            
    @staticmethod
    def read_performance_metrics(project_location: str, project_name: str, session_id: str) -> dict:
        metrics_csv = os.path.join(project_location, project_name, session_id, "performance_metrics.csv")

        if not os.path.exists(metrics_csv):
            return {}

        def convert_value(val):
            try:
                f = float(val)
                return int(f) if f.is_integer() else f
            except Exception:
                return val

        with open(metrics_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if not rows:
                return {}

            latest = rows[-1]
            nested_data = {}

            for key, value in latest.items():
                val = convert_value(value)
                if "." in key:
                    group, subkey = key.split(".", 1)
                    if group not in nested_data:
                        nested_data[group] = {}
                    nested_data[group][subkey] = val
                else:
                    nested_data[key] = val

            return nested_data

    @staticmethod
    def read_text_file(path: str | Path) -> str | None:
        """
        Reads a text file and returns its content as a string.
        Returns None if the file is empty or contains only whitespace.
        """
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            raise
        except Exception as e:
            raise RuntimeError(f"Error reading file {path}: {e}")
