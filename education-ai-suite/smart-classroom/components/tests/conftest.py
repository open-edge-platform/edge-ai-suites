# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shared setup: the repo on the import path, and one marker for the slow tests."""

import os
import sys

import pytest

_SC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SC_ROOT not in sys.path:
    sys.path.insert(0, _SC_ROOT)


@pytest.fixture(autouse=True)
def _warnings_to_tmp(tmp_path, monkeypatch):
    """Keep recorded overload warnings out of the real ``storage/`` tree.
    """
    from utils import overload_warnings

    monkeypatch.setattr(overload_warnings, "warnings_path",
                        lambda session_id: tmp_path / f"{session_id}.warnings.jsonl")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: needs a real model, the network, or a live service. "
        "Excluded by `-m \"not slow\"`.",
    )
