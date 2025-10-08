# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import time
from ui.config import API_BASE_URL, logger
import uuid
import hashlib
import requests
from typing import List, Dict, Optional


def fetch_cameras() -> Dict[str, List[str]]:
    try:
        response = requests.get(f"{API_BASE_URL}/cameras", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching cameras: {e}")
        return {}


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
    vehicle_count: Optional[int] = None,
) -> Dict:
    # Normalize inputs
    normalized_action = action.lower()
    normalized_source = (source or "frigate").lower()

    # Create a consistent rule ID based on camera, label, source, action, and vehicle count
    rule_content = f"{camera}-{label}-{normalized_source}-{normalized_action}"
    if vehicle_count is not None:
        rule_content += f"-{vehicle_count}"

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

    if vehicle_count is not None:
        payload["vehicle_count"] = vehicle_count

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

