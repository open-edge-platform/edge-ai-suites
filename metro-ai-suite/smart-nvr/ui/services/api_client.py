# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import time
from ui.config import API_BASE_URL, logger
import uuid
import hashlib
import requests
from typing import List, Dict, Optional, Union


def fetch_cameras() -> Dict[str, List[str]]:
    try:
        response = requests.get(f"{API_BASE_URL}/cameras", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching cameras: {e}")
        return {}


def fetch_cameras_with_labels() -> (List[str], Dict[str, List[str]]):
    """Fetch cameras and preserve label lists if backend provides them.

    Returns:
        (camera_names, camera_labels_map)
        camera_labels_map: mapping camera_name -> list of labels (empty list if unknown)
    """
    try:
        response = requests.get(f"{API_BASE_URL}/cameras", timeout=10)
        response.raise_for_status()
        data = response.json()

        # Case A: {"cameras": {...}} where value is mapping
        if isinstance(data, dict) and "cameras" in data and isinstance(data["cameras"], dict):
            mapping = data["cameras"]
            names = list(mapping.keys())
            normalized = {k: (v if isinstance(v, list) else []) for k, v in mapping.items()}
            return names, normalized
        # Case B: {"cameras": [...]} simple list
        if isinstance(data, dict) and "cameras" in data and isinstance(data["cameras"], list):
            names = data["cameras"]
            return names, {n: [] for n in names}
        # Case C: plain mapping name -> labels list
        if isinstance(data, dict):
            names = list(data.keys())
            normalized = {k: (v if isinstance(v, list) else []) for k, v in data.items()}
            return names, normalized
        # Case D: plain list
        if isinstance(data, list):
            return data, {n: [] for n in data}
        logger.warning(f"Unexpected /cameras payload type for labels: {type(data)} -> {data}")
        return [], {}
    except Exception as e:
        logger.error(f"Error fetching cameras with labels: {e}")
        return [], {}


def fetch_camera_watcher_mapping() -> Dict[str, bool]:
    """Return current enabled/disabled mapping for cameras (empty dict on failure)."""
    try:
        resp = requests.get(f"{API_BASE_URL}/watchers/mapping", timeout=10)
        resp.raise_for_status()
        data = resp.json() or {}
        return data.get("mapping", {}) or {}
    except Exception as e:
        logger.error(f"Error fetching camera watcher mapping: {e}")
        return {}


def submit_camera_watcher_mapping(enabled_list: List[str], all_cameras: List[str]) -> Dict:
    """Submit updated mapping to backend.

    Args:
        enabled_list: list of camera names user selected as enabled.
        all_cameras: full list of cameras (to send disabled ones explicitly).
    Returns: server response dict (or {'error': ...}).
    """
    payload = {"cameras": [{c: (c in enabled_list)} for c in all_cameras]}
    try:
        resp = requests.post(f"{API_BASE_URL}/watchers/enable", json=payload, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"Status {resp.status_code}: {resp.text}"}
    except Exception as e:
        logger.error(f"Error submitting watcher mapping: {e}")
        return {"error": str(e)}


def fetch_events(camera_name):
    try:
        response = requests.get(
            f"{API_BASE_URL}/events", params={"camera": camera_name}, timeout=15
        )
        response.raise_for_status()
        events = response.json()
        events.sort(key=lambda x: x.get("start_time", 0), reverse=True)
        return events
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return []


def add_rule(
    camera: str,
    label: str,
    action: str,
    source: Optional[str] = None,
    count: Optional[int] = None,
) -> Dict:
    # Normalize inputs
    normalized_action = action.lower()
    normalized_source = (source or "frigate").lower()

    # Create a consistent rule ID based on camera, label, source, action, and count
    rule_content = f"{camera}-{label}-{normalized_source}-{normalized_action}"
    if count is not None:
        rule_content += f"-{count}"

    hash = hashlib.md5(rule_content.encode(), usedforsecurity=False).hexdigest()[:8]  # 8-char hash
    rule_id = f"{camera}-{label}-{normalized_source}-{normalized_action}-{hash}"
    # First check if rule already exists
    try:
        check_response = requests.get(f"{API_BASE_URL}/rules/{rule_id}")
        if check_response.status_code == 200:
            return {
                "status": "exists",
                "message": f"Rule already exists with ID: {rule_id}",
                "rule_id": rule_id,
            }
    except Exception as e:
        return {"status": "error", "message": f"Error checking rule: {str(e)}"}

    # If not exists, create new rule
    payload = {
        "id": rule_id,
        "camera": camera,
        "label": label,
        "action": normalized_action,
        "source": normalized_source,
    }

    if count is not None:
        payload["count"] = count

    try:
        response = requests.post(f"{API_BASE_URL}/rules/", json=payload)
        response.raise_for_status()
        return {
            "status": "success",
            "message": f"Rule {rule_id} added successfully.",
            "rule_id": rule_id,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def fetch_rules() -> List[dict]:
    try:
        response = requests.get(f"{API_BASE_URL}/rules/")
        response.raise_for_status()
        return response.json()  # ✅ Return list of rule dicts
    except Exception as e:
        logger.error(f"Error fetching rules: {e}")
        return []


def fetch_rule_responses() -> Dict:
    try:
        response = requests.get(f"{API_BASE_URL}/rules/responses/")
        print(response)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching rule responses: {e}")
        return {"error": str(e)}


def delete_rule_by_id(rule_id: str) -> str:
    try:
        response = requests.delete(f"{API_BASE_URL}/rules/{rule_id}")
        if response.status_code == 200:
            return f"✅ Rule {rule_id} deleted"
        else:
            return f"❌ Failed to delete rule {rule_id}: {response.text}"
    except Exception as e:
        logger.error(f"Error deleting rule {rule_id}: {e}")
        return f"❌ Error: {str(e)}"


def fetch_search_responses() -> Dict:
    """
    Fetch search responses for all rules with action 'search'.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/rules/search-responses/")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching search responses: {e}")
        return {"error": str(e)}


def fetch_summary_status(summary_id: str) -> str:
    """
    Fetch search responses for all rules with action 'search'.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/summary-status/{summary_id}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching search responses: {e}")
        return str(e)

