# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime, timedelta
import os
import pytz
import requests
from ui.config import API_BASE_URL, logger

# ---------------------------------------------------------------------------
# Dynamic timezone detection
# ---------------------------------------------------------------------------
# We mount /etc/localtime and /etc/timezone inside the container. Prefer:
# 1. Explicit override via APP_TIMEZONE or TZ env vars.
# 2. /etc/timezone file content (common on Debian/Ubuntu).
# 3. Symlink target of /etc/localtime (contains region/city in path).
# 4. Fallback to UTC if detection fails.

def _detect_system_timezone():
    candidates = []
    # Explicit env overrides first
    for env_var in ["APP_TIMEZONE", "TZ"]:
        val = os.getenv(env_var)
        if val:
            candidates.append(val.strip())
    # /etc/timezone file
    tz_file = "/etc/timezone"
    if os.path.exists(tz_file):
        try:
            with open(tz_file, "r", encoding="utf-8") as f:
                line = f.readline().strip()
                if line:
                    candidates.append(line)
        except Exception as e:
            logger.debug(f"Failed reading /etc/timezone: {e}")
    # /etc/localtime symlink path parsing
    localtime_path = "/etc/localtime"
    if os.path.islink(localtime_path):
        try:
            target = os.readlink(localtime_path)
            # Extract part after 'zoneinfo/' if present
            if "zoneinfo" in target:
                zone_part = target.split("zoneinfo/")[-1]
                if zone_part:
                    candidates.append(zone_part)
        except Exception as e:
            logger.debug(f"Failed resolving /etc/localtime: {e}")
    # De-dupe preserving order
    seen = set()
    ordered = []
    for c in candidates:
        if c not in seen:
            ordered.append(c)
            seen.add(c)
    for name in ordered:
        try:
            tz = pytz.timezone(name)
            logger.info(f"Using detected system timezone: {name}")
            return tz
        except Exception:
            logger.debug(f"Candidate timezone '{name}' invalid")
    logger.warning("Could not detect system timezone; falling back to UTC")
    return pytz.utc

LOCAL_TZ = _detect_system_timezone()


def parse_input_to_timestamp(input_val, label):
    try:
        dt = None
        if isinstance(input_val, datetime):
            dt = (
                LOCAL_TZ.localize(input_val)
                if input_val.tzinfo is None
                else input_val.astimezone(LOCAL_TZ)
            )
        elif isinstance(input_val, str):
            dt = datetime.fromisoformat(input_val)
            dt = LOCAL_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(LOCAL_TZ)
        elif isinstance(input_val, (float, int)):
            dt = datetime.fromtimestamp(input_val, tz=pytz.utc).astimezone(LOCAL_TZ)
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
            start_dt = datetime.fromtimestamp(start_dt, tz=pytz.utc).astimezone(LOCAL_TZ)
        elif isinstance(start_dt, datetime):
            if start_dt.tzinfo is None:
                logger.warning("start_dt has no timezone info; assuming system timezone.")
                start_dt = LOCAL_TZ.localize(start_dt)
            else:
                start_dt = start_dt.astimezone(LOCAL_TZ)
        else:
            return {"status": "error", "message": "Invalid start time type"}

        logger.info(f"Normalized start_dt: {start_dt} tz={start_dt.tzinfo} (system tz={LOCAL_TZ.zone})")

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
