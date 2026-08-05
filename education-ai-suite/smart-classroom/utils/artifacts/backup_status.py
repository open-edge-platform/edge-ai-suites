import os
from datetime import datetime

from utils.runtime_config_loader import RuntimeConfig
from utils.config_loader import config
from utils.artifacts.path import get_session_dir, _output_layout

DEFAULT_QUIET_SECONDS = 60
_TMP_SUFFIX = ".tmp"


def _quiet_seconds() -> float:
    section = getattr(config, "backup", None)
    return float(getattr(section, "quiet_seconds", DEFAULT_QUIET_SECONDS))


def _storage_root() -> str:
    proj = RuntimeConfig.get_section("Project")
    return os.path.join(proj.get("location"), proj.get("name"))


def _scanned_tiers() -> tuple:
    layout = _output_layout()
    return (layout["result_dir"], layout["raw_dir"])


def _scan(session_dir: str):
    latest_mtime = None
    has_file = False
    has_tmp = False
    for tier in _scanned_tiers():
        tier_root = os.path.join(session_dir, tier)
        if not os.path.isdir(tier_root):
            continue
        for root, _dirs, files in os.walk(tier_root):
            for name in files:
                if name.endswith(_TMP_SUFFIX):
                    has_tmp = True
                    continue
                has_file = True
                try:
                    mtime = os.path.getmtime(os.path.join(root, name))
                except OSError:
                    continue
                if latest_mtime is None or mtime > latest_mtime:
                    latest_mtime = mtime
    return has_file, has_tmp, latest_mtime


def evaluate_session(session_id: str, now: float = None) -> dict:
    if now is None:
        now = _now_epoch()

    result = {"session_id": session_id, "ready": False, "reason": "not_found"}
    session_dir = get_session_dir(session_id)
    if not os.path.isdir(session_dir):
        return result

    has_file, has_tmp, latest_mtime = _scan(session_dir)

    if has_tmp:
        result["reason"] = "writing"
    elif not has_file:
        result["reason"] = "empty"
    elif (now - latest_mtime) >= _quiet_seconds():
        result["ready"] = True
        result["reason"] = "stable"
    else:
        result["reason"] = "processing"
    return result


def list_sessions(ready_only: bool = False) -> list:
    root = _storage_root()
    out = []
    if not os.path.isdir(root):
        return out
    now = _now_epoch()
    for name in sorted(os.listdir(root)):
        if not os.path.isdir(os.path.join(root, name)):
            continue
        status = evaluate_session(name, now=now)
        if ready_only and not status["ready"]:
            continue
        out.append(status)
    return out


def _now_epoch() -> float:
    return datetime.now().timestamp()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
