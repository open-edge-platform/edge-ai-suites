#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
log_config.py — Shared logging setup for benchmark scripts.

Log level is configurable via the LOG_LEVEL environment variable (DEBUG, INFO,
WARNING, ERROR, CRITICAL). A `.env` file at the repo root is loaded
automatically (without requiring the python-dotenv dependency) so CI/local
runs can pin a level without exporting shell variables every time.

Usage
-----
    from log_config import get_logger

    logger = get_logger(__name__)
    logger.info("normal progress output")
    logger.warning("non-fatal issue")
    logger.error("fatal problem")

Override precedence (highest wins):
    1. Explicit `level` argument passed to get_logger()/configure_logging()
    2. LOG_LEVEL environment variable (may come from a real env var or .env)
    3. Default: INFO
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Union

_REPO_ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path: Optional[Union[str, Path]] = None) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ.

    Existing environment variables always take precedence and are never
    overridden. Safe to call multiple times; does nothing if the file is
    missing. The file location defaults to `<repo_root>/.env`, or the path
    given by the BENCHMARK_ENV_FILE environment variable.
    """
    if load_env_file.loaded and path is None:
        return

    if path is None:
        path = os.environ.get("BENCHMARK_ENV_FILE", str(_REPO_ROOT / ".env"))
    env_path = Path(path)
    if not env_path.is_file():
        load_env_file.loaded = True
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)

    load_env_file.loaded = True


load_env_file.loaded = False


def configure_logging(level: Optional[str] = None) -> None:
    """Configure the root logger once, honouring LOG_LEVEL / .env / default.

    Logs to stdout (not the logging module's stderr default) so behaviour
    matches the print() calls this module replaced — shell wrappers that do
    `2>/dev/null` to silence third-party stderr noise (e.g. rosbag2 [WARN]
    lines) don't end up silencing our own script output too.

    Safe to call multiple times: subsequent calls only adjust the level.
    """
    load_env_file()
    level_name = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    resolved = getattr(logging, level_name, None)
    if not isinstance(resolved, int):
        resolved = logging.INFO

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(handler)
        root.setLevel(resolved)
    else:
        root.setLevel(resolved)


def get_logger(name: Optional[str] = None, level: Optional[str] = None) -> logging.Logger:
    """Configure logging (if needed) and return a logger for `name`."""
    configure_logging(level)
    return logging.getLogger(name)
