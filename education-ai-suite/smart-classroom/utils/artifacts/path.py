import os

from utils.runtime_config_loader import RuntimeConfig


def get_session_dir(session_id: str) -> str:
    proj = RuntimeConfig.get_section("Project")
    return os.path.join(proj.get("location"), proj.get("name"), session_id)


def get_artifact_path(session_id: str, *parts: str) -> str:
    return os.path.join(get_session_dir(session_id), *parts)
