# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shared setup: the repo on the import path, and one marker for the slow tests."""

import os
import sys

_SC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SC_ROOT not in sys.path:
    sys.path.insert(0, _SC_ROOT)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: needs a real model, the network, or a live service. "
        "Excluded by `-m \"not slow\"`.",
    )
