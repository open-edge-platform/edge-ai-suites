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


def assert_condition(condition, message=""):
    """Fail a test when condition is false."""
    assert condition, message  # nosec B101


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
    assert_condition(r.status_code == 200)
    assert_condition("Agentic Weld Quality Analysis" in r.text)


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
    assert_condition(r.status_code == 200)
    assert_condition("Rupture" in r.text)


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
    assert_condition(r.status_code == 200)
    assert_condition("r1"[:8] in r.text or "r1" in r.text)


@respx.mock
def test_detections_page(client):
    detections = [
        {"frame_id": 1, "label": "Rupture", "confidence": 0.9, "x": 10, "y": 10, "width": 50, "height": 40, "timestamp": "2026-01-01T00:00:00"}
    ]
    respx.get("http://mock-storage/detections").mock(return_value=httpx.Response(200, json=detections))
    r = client.get("/detections")
    assert_condition(r.status_code == 200)
    assert_condition("Rupture" in r.text)


@respx.mock
def test_detections_page_forwards_valid_label(client):
    detections_route = respx.get("http://mock-storage/detections").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://mock-storage/detections/summary").mock(return_value=httpx.Response(200, json={}))

    r = client.get("/detections", params={"label": "Rupture-1"})

    assert_condition(r.status_code == 200)
    assert_condition(detections_route.calls.last.request.url.params["label"] == "Rupture-1")


@respx.mock
def test_detections_page_rejects_overlong_label(client, caplog):
    detections_route = respx.get("http://mock-storage/detections").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://mock-storage/detections/summary").mock(return_value=httpx.Response(200, json={}))
    label = "A" * 129

    with caplog.at_level("WARNING"):
        r = client.get("/detections", params={"label": label})

    assert_condition(r.status_code == 200)
    assert_condition("label" not in detections_route.calls.last.request.url.params)
    assert_condition("Ignoring detections label filter longer than 128 characters" in caplog.text)


@respx.mock
def test_detections_page_rejects_label_with_disallowed_characters(client, caplog):
    detections_route = respx.get("http://mock-storage/detections").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://mock-storage/detections/summary").mock(return_value=httpx.Response(200, json={}))

    with caplog.at_level("WARNING"):
        r = client.get("/detections", params={"label": "Rupture<script>"})

    assert_condition(r.status_code == 200)
    assert_condition("label" not in detections_route.calls.last.request.url.params)
    assert_condition("Ignoring detections label filter with unsupported characters" in caplog.text)


def test_health(client):
    r = client.get("/health")
    assert_condition(r.status_code == 200)
    assert_condition(r.json()["service"] == "ui-service")
    assert_condition(r.json()["use_case_id"] == "test-case")
