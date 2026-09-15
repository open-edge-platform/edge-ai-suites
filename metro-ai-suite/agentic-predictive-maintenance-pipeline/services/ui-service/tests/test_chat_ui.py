# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Focused tests for the Ask & Analyze page."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["MQTT_DISABLED"] = "true"
os.environ["AGENT_SERVICE_URL"] = "http://mock-agent"
os.environ["DETECTION_SERVICE_URL"] = "http://mock-detection"
os.environ["STORAGE_SERVICE_URL"] = "http://mock-storage"
os.environ["USE_CASE_ID"] = "test-case"

import src.app as app_module
from src.app import app

app_module._AGENT_URL = "http://mock-agent"
app_module._DETECTION_URL = "http://mock-detection"
app_module._STORAGE_URL = "http://mock-storage"
app_module._USE_CASE_ID = "test-case"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_chat_page_has_accessible_controls(client, respx_mock):
    respx_mock.get("http://mock-storage/detections/summary").respond(200, json={})
    respx_mock.get("http://mock-detection/detection/runs").respond(200, json=[
        {"run_id": "completed-run-id", "status": "completed", "phase": "completed"},
        {"run_id": "active-run-id", "status": "running", "phase": "detecting"},
    ])
    respx_mock.get("http://mock-agent/agents/runs").respond(200, json=[
        {"run_id": "completed-run-id", "status": "completed", "phase": "completed"},
    ])
    response = client.get("/chat")

    assert response.status_code == 200
    assert "Ask &amp; Analyze" in response.text
    assert 'aria-current="page"' in response.text
    assert 'name="chat-mode"' in response.text
    assert 'value="analysis"' in response.text
    assert 'value="detections"' in response.text
    assert 'value="combined"' in response.text
    assert 'id="chat-transcript"' in response.text
    assert 'role="log"' in response.text
    assert 'id="chat-thinking"' in response.text
    assert 'aria-label="Generating response"' in response.text
    assert 'id="chat-error"' in response.text
    assert 'id="chat-message"' in response.text
    assert 'id="chat-clear"' in response.text
    assert '<option value="completed-run-id"' in response.text
    assert "active-run-id" not in response.text
    assert 'src="/static/js/chat.js"' in response.text


def test_chat_page_preselects_requested_completed_run(client, respx_mock):
    respx_mock.get("http://mock-storage/detections/summary").respond(200, json={})
    respx_mock.get("http://mock-detection/detection/runs").respond(200, json=[
        {"run_id": "older-run", "status": "completed", "phase": "completed"},
        {"run_id": "newer-run", "status": "completed", "phase": "completed"},
    ])
    respx_mock.get("http://mock-agent/agents/runs").respond(200, json=[
        {"run_id": "newer-run", "status": "completed", "phase": "completed"},
        {"run_id": "older-run", "status": "completed", "phase": "completed"},
    ])

    response = client.get("/chat?run_id=older-run")

    assert response.status_code == 200
    assert '<option value="older-run" selected>older-run</option>' in response.text


@pytest.mark.parametrize("path", ["/", "/detections", "/results/example-run"])
def test_existing_pages_link_to_chat(client, path, respx_mock):
    if path == "/":
        respx_mock.get("http://mock-storage/detections/summary").respond(200, json={})
        respx_mock.get("http://mock-detection/detection/runs").respond(200, json=[])
        respx_mock.get("http://mock-agent/agents/runs").respond(200, json=[])
        respx_mock.get("http://mock-detection/detection/videos").respond(200, json={"videos": []})
    elif path == "/detections":
        respx_mock.get("http://mock-storage/detections").respond(200, json=[])
        respx_mock.get("http://mock-storage/detections/summary").respond(200, json={})
    else:
        respx_mock.get("http://mock-detection/detection/status/example-run").respond(
            200, json={"phase": "detecting"}
        )

    response = client.get(path)
    assert response.status_code == 200
    assert 'href="/chat"' in response.text


def test_chat_script_uses_safe_dom_rendering():
    script_path = Path(__file__).parents[1] / "src" / "static" / "js" / "chat.js"
    script = script_path.read_text(encoding="utf-8")

    assert 'fetch("/api/chat"' in script
    assert "textContent" in script
    assert "innerHTML" not in script
    assert "JSON.stringify(request)" in script
    assert "JSON.stringify(options.query)" in script
    assert "query: result.query" in script
    assert "thinkingIndicator.hidden = !value" in script
    assert "transcript.appendChild(thinkingIndicator)" in script
    assert "sendRequest(lastRequest, false)" in script
    assert 'sessionStorage.setItem(historyStorageKey(), JSON.stringify(chatHistory))' in script
    assert 'runIdInput.addEventListener("change", showSelectedRunHistory)' in script
    assert 'encodeURIComponent(runId || "default")' in script
    assert "restoreHistory();" in script
    assert 'sessionStorage.removeItem(historyStorageKey())' in script
    assert "innerHTML" not in script

    live_script = (
        Path(__file__).parents[1] / "src" / "static" / "js" / "live-status.js"
    ).read_text(encoding="utf-8")
    assert "run.run_id.slice" not in live_script
    assert "encodeURIComponent(run.run_id)" in live_script


def test_chat_page_shows_fallback_banner_when_llm_unavailable(client, respx_mock):
    """When LLM is not configured the chat page renders a visible warning banner."""
    original_available = app_module._chat_available
    try:
        app_module._chat_available = False
        respx_mock.get("http://mock-storage/detections/summary").respond(200, json={})
        respx_mock.get("http://mock-detection/detection/runs").respond(200, json=[])
        respx_mock.get("http://mock-agent/agents/runs").respond(200, json=[])

        response = client.get("/chat")

        assert response.status_code == 200
        assert "chat-unavailable-banner" in response.text
        assert "Ask &amp; Analyze is unavailable in fallback mode" in response.text
        assert "LLM_MODE=llm" in response.text
    finally:
        app_module._chat_available = original_available


def test_chat_page_hides_fallback_banner_when_llm_available(client, respx_mock):
    """When LLM is configured the banner must not appear."""
    original_available = app_module._chat_available
    try:
        app_module._chat_available = True
        respx_mock.get("http://mock-storage/detections/summary").respond(200, json={})
        respx_mock.get("http://mock-detection/detection/runs").respond(200, json=[])
        respx_mock.get("http://mock-agent/agents/runs").respond(200, json=[])

        response = client.get("/chat")

        assert response.status_code == 200
        assert "chat-unavailable-banner" not in response.text
    finally:
        app_module._chat_available = original_available


def test_chat_available_endpoint(client):
    """The /api/chat/available endpoint reflects LLM configuration state."""
    response = client.get("/api/chat/available")
    assert response.status_code == 200
    body = response.json()
    assert "available" in body
    assert isinstance(body["available"], bool)
