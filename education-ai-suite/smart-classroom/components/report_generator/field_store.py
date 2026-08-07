"""
Session-level report field cache.

A generation resolves the ENTIRE field catalog once (raw values from data +
generated prose from a single LLM call) and persists it here as
``class_report_fields.json``. This makes re-selecting fields cheap: toggling
checkboxes after a report exists is a pure re-projection of this cache onto the
template (drop the deselected fields, re-fill) — no data re-read, no LLM re-run,
and the AI text stays stable. See ``ReportGenerator.reapply_selection``.

Only "Regenerate" recomputes the cache (fresh LLM prose).
"""

import os
import json
import logging

from utils.storage_manager import StorageManager
from utils.artifacts.path import get_artifact_path

logger = logging.getLogger(__name__)

FIELDS_FILENAME = "class_report_fields.json"


def store_path(session_dir: str) -> str:
    return os.path.join(session_dir, FIELDS_FILENAME)


def load_store(session_id: str) -> dict:
    """Load the session field cache as ``{"fields": {code: value}}``.

    Returns an empty cache (never raises) when the file is absent or corrupt.
    """
    path = get_artifact_path(session_id, FIELDS_FILENAME)
    if not os.path.exists(path):
        return {"fields": {}}
    try:
        data = json.loads(StorageManager.read_text_file(path) or "{}")
    except (ValueError, TypeError):
        logger.warning("[field_store] Corrupt %s; starting from an empty cache.", FIELDS_FILENAME)
        return {"fields": {}}
    if not isinstance(data, dict) or not isinstance(data.get("fields"), dict):
        return {"fields": {}}
    return data


def save_store(session_id: str, fields: dict) -> None:
    """Persist the full-catalog ``fields`` cache for the session."""
    StorageManager.save(
        get_artifact_path(session_id, FIELDS_FILENAME),
        json.dumps({"fields": fields}, ensure_ascii=False, indent=2),
        append=False,
    )
