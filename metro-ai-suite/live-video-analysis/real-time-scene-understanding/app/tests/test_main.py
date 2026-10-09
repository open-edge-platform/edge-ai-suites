# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for app entrypoint module main.py."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestMainEntrypoint:
    def test_main_module_exposes_fastapi_app(self):
        import main as main_module

        assert main_module.app.title == "Real Time Scene Understanding"

    def test_health_endpoint_works_via_main_app(self):
        import main as main_module

        client = TestClient(main_module.app)
        response = client.get("/api/health")

        assert response.status_code == 200
        payload = response.json()
        assert "status" in payload
