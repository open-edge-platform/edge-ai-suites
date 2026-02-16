# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.pipelines, pipeline listing endpoint."""

from unittest.mock import patch


class TestListPipelines:
    """GET /api/pipelines endpoint."""

    def test_returns_pipelines(self, client):
        """Returns the list of pipelines from the remote server."""
        mock_data = [
            {"pipeline_name": "genai_pipeline", "pipeline_type": "non-detection"},
        ]
        with patch(
            "backend.routes.pipelines.discover_pipelines_remote",
            return_value=mock_data,
        ):
            resp = client.get("/api/pipelines")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["pipelines"]) == 1
        assert body["pipelines"][0]["pipeline_name"] == "genai_pipeline"

    def test_returns_multiple_pipelines(self, client):
        """Multiple pipelines are returned in the response."""
        mock_data = [
            {"pipeline_name": "pipe_a", "pipeline_type": "non-detection"},
            {"pipeline_name": "pipe_b", "pipeline_type": "detection"},
        ]
        with patch(
            "backend.routes.pipelines.discover_pipelines_remote",
            return_value=mock_data,
        ):
            resp = client.get("/api/pipelines")
        assert resp.status_code == 200
        assert len(resp.json()["pipelines"]) == 2

    def test_returns_empty_list_gracefully(self, client):
        """An empty pipeline list is returned without error."""
        with patch(
            "backend.routes.pipelines.discover_pipelines_remote",
            return_value=[],
        ):
            resp = client.get("/api/pipelines")
        assert resp.status_code == 200
        assert resp.json()["pipelines"] == []
