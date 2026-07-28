# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""UI service tests — uses HTTPX respx to mock backend services."""

import os
import pytest

os.environ["MQTT_DISABLED"] = "true"
os.environ["AGENT_SERVICE_URL"]     = "http://mock-agent"
os.environ["DETECTION_SERVICE_URL"] = "http://mock-detection"
os.environ["STORAGE_SERVICE_URL"]   = "http://mock-storage"
os.environ["USE_CASE_ID"]           = "test-case"

import respx
import httpx
from fastapi.testclient import TestClient
from src.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@respx.mock
def test_index_no_data(client):
    respx.get("http://mock-storage/detections/summary").mock(return_value=httpx.Response(200, json={}))
    respx.get("http://mock-detection/detection/runs").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://mock-detection/detection/videos").mock(return_value=httpx.Response(200, json={"videos": []}))
    r = client.get("/")
    assert r.status_code == 200
    assert "Agentic Predictive Maintenance" in r.text


@respx.mock
def test_index_with_summary(client):
    summary = {
        "by_class": [
            {"label": "Rupture", "count": 5, "avg_confidence": 0.88, "max_confidence": 0.95}
        ]
    }
    respx.get("http://mock-storage/detections/summary").mock(return_value=httpx.Response(200, json=summary))
    respx.get("http://mock-detection/detection/runs").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://mock-detection/detection/videos").mock(return_value=httpx.Response(200, json={"videos": []}))
    r = client.get("/")
    assert r.status_code == 200
    assert "Rupture" in r.text


@respx.mock
def test_index_merges_detection_and_agent_runs(client):
    respx.get("http://mock-storage/detections/summary").mock(return_value=httpx.Response(200, json={}))
    respx.get("http://mock-detection/detection/videos").mock(return_value=httpx.Response(200, json={"videos": []}))
    respx.get("http://mock-detection/detection/runs").mock(return_value=httpx.Response(200, json=[
        {"run_id": "r1", "status": "completed", "phase": "completed", "result": {}},
        {"run_id": "r2", "status": "running", "phase": "detecting", "result": None},
    ]))
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[
        {"run_id": "r1", "status": "completed", "phase": "completed"},
    ]))
    r = client.get("/")
    assert r.status_code == 200
    assert "r1"[:8] in r.text or "r1" in r.text


@respx.mock
def test_detections_page(client):
    detections = [
        {"frame_id": 1, "label": "Rupture", "confidence": 0.9, "x": 10, "y": 10, "width": 50, "height": 40, "timestamp": "2026-01-01T00:00:00"}
    ]
    respx.get("http://mock-storage/detections").mock(return_value=httpx.Response(200, json=detections))
    r = client.get("/detections")
    assert r.status_code == 200
    assert "Rupture" in r.text


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "ui-service"
    assert r.json()["use_case_id"] == "test-case"
