# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime, timedelta
import pytz
import requests
from ui.config import API_BASE_URL, logger

IST = pytz.timezone("Asia/Kolkata")


def parse_input_to_timestamp(input_val, label):
    try:
        dt = None
        if isinstance(input_val, datetime):
            dt = (
                IST.localize(input_val)
                if input_val.tzinfo is None
                else input_val.astimezone(IST)
            )
        elif isinstance(input_val, str):
            dt = datetime.fromisoformat(input_val)
            dt = IST.localize(dt) if dt.tzinfo is None else dt.astimezone(IST)
        elif isinstance(input_val, (float, int)):
            dt = datetime.fromtimestamp(input_val, tz=pytz.utc).astimezone(IST)
        else:
            return None, None
        return dt.timestamp(), dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception as e:
        logger.error(f"Error parsing {label}: {e}")
        return None, None


def process_video(camera_name, start_dt, duration_seconds, action, label=None):
    """Process a video summarization or search request.

    start_dt may be:
      - datetime (naive or tz-aware)
      - int/float epoch seconds
    """
    try:
        # Normalize start_dt
        if isinstance(start_dt, (int, float)):
            start_dt = datetime.fromtimestamp(start_dt, tz=pytz.utc).astimezone(IST)
        elif isinstance(start_dt, datetime):
            if start_dt.tzinfo is None:
                logger.warning("start_dt has no timezone info; assuming IST.")
                start_dt = IST.localize(start_dt)
            else:
                start_dt = start_dt.astimezone(IST)
        else:
            return {"status": "error", "message": "Invalid start time type"}

        logger.info(f"Normalized start_dt: {start_dt} tz={start_dt.tzinfo}")

        if duration_seconds <= 0:
            return {"status": "error", "message": "End time must be after start time"}

        end_dt = start_dt + timedelta(seconds=duration_seconds)
        start_time = int(start_dt.timestamp())
        end_time = int(end_dt.timestamp())

        if start_time >= end_time:
            return {"status": "error", "message": "End time must be after start time"}

        if action == "Summarize":
            response = requests.get(
                f"{API_BASE_URL}/summary/{camera_name}",
                params={"start_time": start_time, "end_time": end_time},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("status") != 200:
                return {"status": "Failed", "message": result.get("message")}
            return {"status": "success", "summary_id": result.get("message")}
        elif action == "Add to Search":
            response = requests.get(
                f"{API_BASE_URL}/search-embeddings/{camera_name}",
                params={"start_time": start_time, "end_time": end_time},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("status") != 200:
                return {"status": "Failed", "message": result.get("message")}
            return {"status": "success", "response": result.get("message")}
        else:
            return {"status": "error", "message": "Unknown action"}
    except Exception as e:
        logger.error(f"Video processing failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
