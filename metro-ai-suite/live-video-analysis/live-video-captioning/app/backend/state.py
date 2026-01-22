# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from .models import RunInfo

# In-memory storage for active runs
RUNS: dict[str, RunInfo] = {}
