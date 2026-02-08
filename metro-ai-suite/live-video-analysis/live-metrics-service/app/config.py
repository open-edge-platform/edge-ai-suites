# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Configuration module for the Metrics Service.

Environment variables:
    METRICS_PORT: Port to run the metrics service on (default: 9090)
    LOG_LEVEL: Logging level (default: INFO)
"""

import os
import sys

def _get_int_env(env_var: str, default: int) -> int:
    """Safely parse an integer environment variable with error handling."""
    try:
        value = os.environ.get(env_var, str(default))
        return int(value)
    except ValueError:
        print(f"Error: Invalid value '{value}' for {env_var}. Expected an integer. Using default: {default}", file=sys.stderr)
        return default

# Service configuration
METRICS_PORT = _get_int_env("METRICS_PORT", 9090)
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# CORS configuration
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
