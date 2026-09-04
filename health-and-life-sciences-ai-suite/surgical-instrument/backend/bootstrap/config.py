"""YAML config loader with ${VAR:-default} env-var expansion."""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _expand(value):
    if isinstance(value, str):
        def repl(m):
            var, default = m.group(1), m.group(2) or ""
            return os.environ.get(var, default)
        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def load_config(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    return _expand(data)
