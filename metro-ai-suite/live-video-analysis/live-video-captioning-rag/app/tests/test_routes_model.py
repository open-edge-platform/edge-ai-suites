# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.model."""

from unittest.mock import patch


class TestModelEndpoint:
    """GET /api/model endpoint."""

    def test_returns_success_and_model_name(self, client):
        # LLM_MODEL_ID is imported in route module; patch there for deterministic output.
        with patch("backend.routes.model.LLM_MODEL_ID", "unit-test-llm"):
            resp = client.get("/api/model")

        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "llm_model": "unit-test-llm"}
