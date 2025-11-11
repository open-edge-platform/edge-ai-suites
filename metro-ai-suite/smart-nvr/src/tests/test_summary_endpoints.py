# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for summary and search embedding endpoints."""
import pytest
from unittest.mock import patch


def test_summary_endpoint(client):
    with patch("api.router.vms_service.summarize", return_value={"status": "ok", "id": "s1"}) as p:
        resp = client.get("/summary/cam1", params={"start_time": 1, "end_time": 2})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        p.assert_called_once()


def test_search_embeddings_endpoint(client):
    with patch("api.router.vms_service.search_embeddings", return_value={"status": "ok", "id": "e1"}) as p:
        resp = client.get("/search-embeddings/cam1", params={"start_time": 1, "end_time": 2})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        p.assert_called_once()


def test_summary_status_endpoint(client):
    with patch("api.router.vms_service.summary", return_value={"status": "completed", "result": "text"}) as p:
        resp = client.get("/summary-status/summary123")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        p.assert_called_once_with("summary123")
