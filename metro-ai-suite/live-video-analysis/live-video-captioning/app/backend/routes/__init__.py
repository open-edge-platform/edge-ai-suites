# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# API route handlers
from .config import router as config_router
from .metrics import router as metrics_router
from .models import router as models_router
from .pipelines import router as pipelines_router
from .runs import router as runs_router
from .health import router as health_router

__all__ = [
    "config_router",
    "metrics_router",
    "models_router",
    "pipelines_router",
    "runs_router",
    "health_router",
]
