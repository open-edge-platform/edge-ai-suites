from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_COMPONENT_ROOT = Path(__file__).resolve().parents[1]
_PARENT_ROOT = _COMPONENT_ROOT.parents[1]

SELF_ONLY = "self-only"
PARENT_OVERRIDE = "parent-override"

_PARENT_OVERRIDE_KEYS = ("app", "models", "grading")


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict[str, Any]:
    cfg = _read_yaml(_COMPONENT_ROOT / "config.yaml")
    source = str(cfg.get("config_source", PARENT_OVERRIDE)).strip().lower()

    if source == SELF_ONLY:
        return cfg

    parent = _read_yaml(_PARENT_ROOT / "config.yaml")
    if not parent:
        return cfg

    override = {k: parent[k] for k in _PARENT_OVERRIDE_KEYS if isinstance(parent.get(k), dict)}
    return _deep_merge(cfg, override)


def get_language() -> str:
    cfg = load_config()
    return str((cfg.get("app") or {}).get("language", "en"))


def get_ocr_config() -> dict[str, Any]:
    return _read_yaml(_COMPONENT_ROOT / "providers" / "ocr_service" / "config.yaml")


def get_provider_url(key: str, default: str) -> str:
    cfg = load_config()
    provider = ((cfg.get("grading") or {}).get("provider") or {})
    url = provider.get(key)
    return str(url) if url else default


def resolve_model_dir(model_dir: str, default: str = "../../models/ocr") -> Path:
    p = Path(model_dir or default)
    if p.is_absolute():
        return p.resolve()
    component_rel = (_COMPONENT_ROOT / p).resolve()
    if component_rel.exists():
        return component_rel
    parent_rel = (_PARENT_ROOT / p).resolve()
    if parent_rel.exists():
        return parent_rel
    return component_rel
