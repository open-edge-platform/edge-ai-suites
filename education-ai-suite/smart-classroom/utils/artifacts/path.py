import os

from utils.runtime_config_loader import RuntimeConfig
from utils.config_loader import config


DEFAULT_OUTPUT_LAYOUT = {
    "result_dir": "result",
    "raw_dir": "raw",
    "logs_dir": "logs",
}

_LOGS_ROOTS = {
    "utilization_logs",
}

_LOGS_FILES = {
    "performance_metrics.csv",
}

_RESULT_FILES = {
    "summary.md",
    "mindmap.mmd",
    "topics.json",
    "class_report.md",
    "class_report.docx",
    "class_report.pdf",
    "class_report_fields.json",
    "mindmap_report.png",
    "custom_report_template.docx",
}


def _output_layout() -> dict:
    section = getattr(config, "output_layout", None)
    return {
        "result_dir": getattr(section, "result_dir", DEFAULT_OUTPUT_LAYOUT["result_dir"]),
        "raw_dir": getattr(section, "raw_dir", DEFAULT_OUTPUT_LAYOUT["raw_dir"]),
        "logs_dir": getattr(section, "logs_dir", DEFAULT_OUTPUT_LAYOUT["logs_dir"]),
    }


def _tier_root(session_id: str, tier: str) -> str:
    layout = _output_layout()
    dir_name = {
        "result": layout["result_dir"],
        "raw": layout["raw_dir"],
        "logs": layout["logs_dir"],
    }[tier]
    return os.path.join(get_session_dir(session_id), dir_name)


def _classify(normalized_parts: tuple) -> str:
    first = normalized_parts[0]
    name = normalized_parts[-1]

    if first in _LOGS_ROOTS or name in _LOGS_FILES:
        return "logs"

    if first == "va" and "logs" in normalized_parts:
        return "logs"

    if len(normalized_parts) == 1:
        if name in _RESULT_FILES or (
            name.startswith("class_report_") and name.endswith(".pdf")
        ):
            return "result"

    return "raw"


def get_session_dir(session_id: str) -> str:
    proj = RuntimeConfig.get_section("Project")
    return os.path.join(proj.get("location"), proj.get("name"), session_id)


def get_artifact_path(session_id: str, *parts: str) -> str:
    if not parts:
        return get_session_dir(session_id)

    normalized_parts = tuple(str(p).strip("/\\") for p in parts if str(p) != "")
    if not normalized_parts:
        return get_session_dir(session_id)

    tier = _classify(normalized_parts)
    return os.path.join(_tier_root(session_id, tier), *normalized_parts)
