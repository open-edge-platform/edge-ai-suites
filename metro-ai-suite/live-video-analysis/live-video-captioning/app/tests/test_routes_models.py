# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.models, VLM and detection model listing endpoints."""

from unittest.mock import patch


class TestListVlmModels:
    """GET /api/vlm-models endpoint."""

    def test_returns_empty_list_when_no_models(self, client):
        """Returns an empty model list when the models directory is empty."""
        with patch("backend.routes.models.discover_models", return_value=[]):
            resp = client.get("/api/vlm-models")
        assert resp.status_code == 200
        assert resp.json() == {"models": []}

    def test_returns_discovered_models(self, client):
        """Returns model names discovered from the directory."""
        models = ["InternVL2-1B", "InternVL2-2B"]
        with patch("backend.routes.models.discover_models", return_value=models):
            resp = client.get("/api/vlm-models")
        assert resp.status_code == 200
        assert resp.json()["models"] == models


class TestListDetectionModels:
    """GET /api/detection-models endpoint."""

    def test_returns_empty_list_when_no_models(self, client):
        """Returns an empty list when no detection models exist."""
        with patch("backend.routes.models.discover_detection_models", return_value=[]):
            resp = client.get("/api/detection-models")
        assert resp.status_code == 200
        assert resp.json() == {"models": []}

    def test_returns_discovered_detection_models(self, client):
        """Returns detection model names from the directory."""
        models = ["yolov8s"]
        with patch(
            "backend.routes.models.discover_detection_models", return_value=models
        ):
            resp = client.get("/api/detection-models")
        assert resp.status_code == 200
        assert resp.json()["models"] == models
