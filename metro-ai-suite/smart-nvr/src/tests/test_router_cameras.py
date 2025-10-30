# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for camera router endpoints."""
import pytest
from unittest.mock import patch


def test_get_cameras_empty(client):
    with patch("api.router.frigate_service.get_camera_names", return_value={}) as mock_fn:
        resp = client.get("/cameras")
        assert resp.status_code == 200
        assert resp.json() == {}
        mock_fn.assert_called_once()


def test_get_cameras_non_empty(client):
    cams = {"garage": [], "livingroom": []}
    with patch("api.router.frigate_service.get_camera_names", return_value=cams):
        resp = client.get("/cameras")
        assert resp.status_code == 200
        assert resp.json() == cams


def test_get_events_calls_service(client):
    with patch("api.router.frigate_service.get_camera_events") as mock_events:
        mock_events.return_value = [{"id": 1}]
        resp = client.get("/events", params={"camera": "garage"})
        assert resp.status_code == 200
        assert resp.json() == [{"id": 1}]
        mock_events.assert_awaited()
