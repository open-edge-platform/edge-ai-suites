# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import sys
import pathlib
import pytest
from fastapi.testclient import TestClient

# Ensure the src directory (parent of this tests folder) is on sys.path so 'api', 'service', etc. resolve
_SRC_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from fastapi import FastAPI
from api.router import router  # api package lives under src/api

# Single FastAPI app instance for all tests
app = FastAPI()
app.include_router(router)

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
def client():
    return TestClient(app)
