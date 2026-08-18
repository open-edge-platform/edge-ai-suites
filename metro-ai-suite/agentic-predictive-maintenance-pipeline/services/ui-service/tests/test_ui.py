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
os.environ["APM_API_KEY"]           = "test-key"

import respx
import httpx
from fastapi.testclient import TestClient
import src.app as app_module
from src.app import app

app_module._AGENT_URL = "http://mock-agent"
app_module._DETECTION_URL = "http://mock-detection"
app_module._STORAGE_URL = "http://mock-storage"
app_module._USE_CASE_ID = "test-case"


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
    completed_run_id = "11111111-2222-3333-4444-555555555555"
    respx.get("http://mock-storage/detections/summary").mock(return_value=httpx.Response(200, json={}))
    respx.get("http://mock-detection/detection/videos").mock(return_value=httpx.Response(200, json={"videos": []}))
    respx.get("http://mock-detection/detection/runs").mock(return_value=httpx.Response(200, json=[
        {"run_id": completed_run_id, "status": "completed", "phase": "completed", "result": {}},
        {"run_id": "r2", "status": "running", "phase": "detecting", "result": None},
    ]))
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[
        {"run_id": completed_run_id, "status": "completed", "phase": "completed"},
    ]))
    r = client.get("/")
    assert r.status_code == 200
    assert completed_run_id in r.text
    assert f"/chat?run_id={completed_run_id}" in r.text


@respx.mock
def test_index_running_without_phase_does_not_render_null(client):
    respx.get("http://mock-storage/detections/summary").mock(return_value=httpx.Response(200, json={}))
    respx.get("http://mock-detection/detection/videos").mock(return_value=httpx.Response(200, json={"videos": []}))
    respx.get("http://mock-detection/detection/runs").mock(return_value=httpx.Response(200, json=[
        {"run_id": "r1", "status": "running", "phase": None, "result": None},
    ]))
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[]))

    r = client.get("/")

    assert r.status_code == 200
    assert "Inspection: RUNNING" in r.text
    assert "RUNNING (None)" not in r.text
    assert "RUNNING (null)" not in r.text


@respx.mock
def test_detections_page(client):
    detections = [
        {"frame_id": 1, "label": "Rupture", "confidence": 0.9, "x": 10, "y": 10, "width": 50, "height": 40, "timestamp": "2026-01-01T00:00:00"}
    ]
    respx.get("http://mock-storage/detections").mock(return_value=httpx.Response(200, json=detections))
    r = client.get("/detections")
    assert r.status_code == 200
    assert "Rupture" in r.text


@respx.mock
def test_index_run_form_posts_to_video_run_when_disabled(client):
    app_module._MULTIMODAL_CONFIG_PATH = ""
    respx.get("http://mock-storage/detections/summary").mock(return_value=httpx.Response(200, json={}))
    respx.get("http://mock-detection/detection/runs").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://mock-detection/detection/videos").mock(return_value=httpx.Response(200, json={"videos": []}))
    r = client.get("/")
    assert r.status_code == 200
    assert 'action="/run"' in r.text
    assert "run-multimodal" not in r.text
    assert 'name="video_filename"' in r.text


@respx.mock
def test_index_run_form_posts_to_multimodal_run_when_enabled(client):
    app_module._MULTIMODAL_CONFIG_PATH = "/app/configs/gas_detection.docker.json"
    respx.get("http://mock-storage/detections/summary").mock(return_value=httpx.Response(200, json={}))
    respx.get("http://mock-detection/detection/runs").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[]))
    respx.get("http://mock-detection/detection/videos").mock(return_value=httpx.Response(200, json={"videos": []}))
    r = client.get("/")
    assert r.status_code == 200
    assert 'action="/run-multimodal"' in r.text
    assert 'name="video_filename"' not in r.text
    app_module._MULTIMODAL_CONFIG_PATH = ""


@respx.mock
def test_detections_page_shows_modality_columns_when_enabled(client):
    app_module._MULTIMODAL_CONFIG_PATH = "/app/configs/gas_detection.docker.json"
    detections = [
        {
            "frame_id": 1, "label": "Smoke", "confidence": 0.95, "x": 0, "y": 0, "width": 0, "height": 0,
            "timestamp": "2026-01-01T00:00:00", "source": "gas_detection_multimodal",
            "image_confidence": 0.9, "sensor_confidence": 0.97, "sensor_raw_json": "{}",
        }
    ]
    respx.get("http://mock-storage/detections").mock(return_value=httpx.Response(200, json=detections))
    r = client.get("/detections")
    assert r.status_code == 200
    assert "gas_detection_multimodal" in r.text
    assert "0.900" in r.text
    assert "0.970" in r.text
    app_module._MULTIMODAL_CONFIG_PATH = ""


@respx.mock
def test_trigger_multimodal_run_disabled_returns_404(client):
    app_module._MULTIMODAL_CONFIG_PATH = ""
    r = client.post("/run-multimodal", data={"device": "CPU"}, follow_redirects=False)
    assert r.status_code == 404


@respx.mock
def test_trigger_multimodal_run_posts_config_path(client):
    app_module._MULTIMODAL_CONFIG_PATH = "/app/configs/gas_detection.docker.json"
    route = respx.post("http://mock-detection/detection/run-multimodal").mock(
        return_value=httpx.Response(202, json={"run_id": "abc123"})
    )

    r = client.post("/run-multimodal", data={"device": "CPU"}, follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == "/results/abc123"
    assert route.called
    sent = respx.calls.last.request
    import json as _json
    body = _json.loads(sent.content)
    assert body == {"device": "CPU", "config_path": "/app/configs/gas_detection.docker.json"}
    app_module._MULTIMODAL_CONFIG_PATH = ""


@respx.mock
def test_clear_detections_sends_api_key(client):
    route = respx.delete("http://mock-storage/detections").mock(return_value=httpx.Response(204))

    r = client.post("/clear-detections", follow_redirects=False)

    assert r.status_code == 303
    assert route.called
    assert route.calls.last.request.headers["X-API-Key"] == "test-key"


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "ui-service"
    assert r.json()["use_case_id"] == "test-case"
