import json
import logging
import os
from types import SimpleNamespace

import yaml


logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PREFIX = "SMART_KIOSK_RAG__"
CONFIG_PATH_ENV = "SMART_KIOSK_RAG_CONFIG_PATH"
CONFIG_OVERRIDE_PATHS_ENV = "SMART_KIOSK_RAG_CONFIG_OVERRIDE_PATHS"


def _resolve_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)


def _load_yaml_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _deep_merge(base: dict, override: dict) -> dict:
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override

    merged = dict(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _parse_env_value(raw_value: str, existing_value):
    if isinstance(existing_value, bool):
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(existing_value, int) and not isinstance(existing_value, bool):
        return int(raw_value)
    if isinstance(existing_value, float):
        return float(raw_value)
    if isinstance(existing_value, list):
        stripped = raw_value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            parsed = json.loads(stripped)
            if not isinstance(parsed, list):
                raise ValueError("Expected a JSON array for list-valued config override")
            return parsed
        return [item.strip() for item in raw_value.split(",") if item.strip()]
    if existing_value is None:
        stripped = raw_value.strip()
        if stripped.lower() in {"none", "null"}:
            return None
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return raw_value
    return raw_value


def _set_nested_value(data: dict, path: list[str], value) -> None:
    cursor = data
    for segment in path[:-1]:
        child = cursor.get(segment)
        if not isinstance(child, dict):
            child = {}
            cursor[segment] = child
        cursor = child
    cursor[path[-1]] = value


def _apply_env_overrides(data: dict) -> dict:
    for env_key, raw_value in os.environ.items():
        if not env_key.startswith(ENV_PREFIX):
            continue

        path = [segment.lower() for segment in env_key[len(ENV_PREFIX):].split("__") if segment]
        if not path:
            continue

        existing_value = data
        for segment in path:
            if isinstance(existing_value, dict) and segment in existing_value:
                existing_value = existing_value[segment]
            else:
                existing_value = None
                break

        _set_nested_value(data, path, _parse_env_value(raw_value, existing_value))

    return data


def _apply_yaml_overrides(data: dict) -> dict:
    raw_paths = os.environ.get(CONFIG_OVERRIDE_PATHS_ENV, "").strip()
    if not raw_paths:
        return data

    for override_path in [entry.strip() for entry in raw_paths.split(",") if entry.strip()]:
        resolved = _resolve_path(override_path)
        if not os.path.isfile(resolved):
            logger.warning("Config override file not found: %s", resolved)
            continue
        data = _deep_merge(data, _load_yaml_file(resolved))
    return data


def _dict_to_namespace(data):
    if isinstance(data, dict):
        return SimpleNamespace(**{key: _dict_to_namespace(value) for key, value in data.items()})
    return data


def load_config(path: str = "config.yaml"):
    config_path = _resolve_path(os.environ.get(CONFIG_PATH_ENV, path))
    data = _load_yaml_file(config_path)
    data = _apply_yaml_overrides(data)
    data = _apply_env_overrides(data)
    return _dict_to_namespace(data)


config = load_config()
