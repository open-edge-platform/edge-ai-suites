#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""log.py — Logging setup. Call setup_logging(config) once at startup."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from config_loader import LogConfig


def setup_logging(config: LogConfig) -> None:
    """Configure the root logger from a LogConfig."""
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    numeric_level = getattr(logging, config.level, logging.INFO)
    root.setLevel(numeric_level)
    formatter = logging.Formatter(config.format)

    console = logging.StreamHandler()
    console.setLevel(numeric_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    if config.file:
        path = Path(config.file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        handler.setLevel(numeric_level)
        handler.setFormatter(formatter)
        root.addHandler(handler)

    logging.getLogger(__name__).debug("Logging configured: level=%s, file=%s", config.level, config.file or "none")
