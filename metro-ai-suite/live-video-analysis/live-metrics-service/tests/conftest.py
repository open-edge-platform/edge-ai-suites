# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures for the live-metrics-service test suite."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    """Create a FastAPI TestClient for making HTTP and WebSocket requests."""
    return TestClient(app)
