#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""
exceptions.py — Custom exception hierarchy for win_vision_ai.

All application-specific exceptions derive from :class:`WinVisionAIError` so
callers can catch the entire family with a single ``except WinVisionAIError``.

Hierarchy
---------
::

    Exception
    └── WinVisionAIError
        ├── ConfigError        (also a ValueError — backward-compatible)
        └── PipelineError
"""

from __future__ import annotations


class WinVisionAIError(Exception):
    """Base class for all win_vision_ai exceptions."""


class ConfigError(WinVisionAIError, ValueError):
    """
    Raised when configuration validation fails.

    Subclasses :class:`ValueError` so existing code that catches
    ``ValueError`` from :func:`~win_vision_ai.config.load_config` continues to work.
    """


class PipelineError(WinVisionAIError):
    """Raised for pipeline startup or unrecoverable state errors."""
