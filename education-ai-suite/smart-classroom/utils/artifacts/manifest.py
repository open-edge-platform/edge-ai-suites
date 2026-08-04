import os
from datetime import datetime

from utils.storage_manager import StorageManager
from utils.artifacts.path import get_session_dir

MANIFEST_NAME = "_manifest.json"


def _list_session_files(session_dir: str) -> list:
    result = []
    for root, _dirs, files in os.walk(session_dir):
        for name in files:
            if name.endswith(".tmp") or name == MANIFEST_NAME:
                continue
            abs_path = os.path.join(root, name)
            result.append(os.path.relpath(abs_path, session_dir).replace(os.sep, "/"))
    return sorted(result)


def write_manifest(session_id: str) -> str:
    session_dir = get_session_dir(session_id)
    manifest_path = os.path.join(session_dir, MANIFEST_NAME)
    data = {
        "session_id": session_id,
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "files": _list_session_files(session_dir),
    }
    StorageManager.save(manifest_path, data)
    return manifest_path


def manifest_path(session_id: str) -> str:
    return os.path.join(get_session_dir(session_id), MANIFEST_NAME)


def is_complete(session_id: str) -> bool:
    return os.path.exists(manifest_path(session_id))
