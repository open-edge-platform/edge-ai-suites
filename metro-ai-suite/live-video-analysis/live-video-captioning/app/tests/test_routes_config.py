# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.routes.config, runtime configuration endpoint."""

import json


class TestRuntimeConfig:
    """GET /runtime-config.js endpoint."""

    def test_returns_javascript_content_type(self, client):
        """Response content-type is application/javascript."""
        resp = client.get("/runtime-config.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]

    def test_body_sets_window_runtime_config(self, client):
        """Response body assigns window.RUNTIME_CONFIG."""
        resp = client.get("/runtime-config.js")
        body = resp.text
        assert body.startswith("window.RUNTIME_CONFIG = ")
        assert body.endswith(";")

    def test_payload_contains_expected_keys(self, client):
        """window.RUNTIME_CONFIG includes all required configuration keys."""
        resp = client.get("/runtime-config.js")
        # Extract JSON from "window.RUNTIME_CONFIG = {...};"
        json_str = resp.text.removeprefix("window.RUNTIME_CONFIG = ").removesuffix(";")
        payload = json.loads(json_str)

        expected_keys = {
            "signalingUrl",
            "defaultPeerId",
            "mqttTopicPrefix",
            "alertMode",
            "defaultPrompt",
            "defaultRtspUrl",
            "enableDetectionPipeline",
            "metricsServicePort",
        }
        assert expected_keys.issubset(payload.keys())

    def test_alert_mode_is_boolean(self, client):
        """alertMode value is a boolean."""
        resp = client.get("/runtime-config.js")
        json_str = resp.text.removeprefix("window.RUNTIME_CONFIG = ").removesuffix(";")
        payload = json.loads(json_str)
        assert isinstance(payload["alertMode"], bool)
