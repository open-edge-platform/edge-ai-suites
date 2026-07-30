# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for api-reference-videostream-analytics.md."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


SOURCE_STATUS = {
    "source_id": "cam_child",
    "source_url": "rtsp://localhost:8554/live/child",
    "data_dir": "/data/cam_child",
    "status": "online",
    "running": True,
    "recording_enabled": True,
    "health": {},
    "keepalive_enabled": True,
    "last_keepalive_at": None,
}


@pytest.fixture
def client_and_manager(vsa_api: tuple[TestClient, MagicMock]):
    client, manager = vsa_api
    manager.get_sources.return_value = [SOURCE_STATUS]
    manager.get_source_status.return_value = SOURCE_STATUS
    manager.register_source.return_value = {
        "status": "started",
        "source_id": "cam_child",
        "source_url": SOURCE_STATUS["source_url"],
        "data_dir": SOURCE_STATUS["data_dir"],
    }
    manager.unregister_source.return_value = {"status": "stopped", "source_id": "cam_child"}
    manager.pause_source.return_value = {"status": "paused", "source_id": "cam_child"}
    manager.resume_source.return_value = {"status": "online", "source_id": "cam_child"}
    manager.keepalive_source.return_value = {
        "status": "ok",
        "source_id": "cam_child",
        "last_keepalive_at": "2026-06-30T12:34:56Z",
    }
    manager.update_pipeline_config.return_value = {"status": "updated", "source_id": "cam_child"}
    bundle = MagicMock()
    manager._bundles = {"cam_child": bundle}
    return client, manager, bundle


def test_health_and_source_queries(client_and_manager):
    client, _, _ = client_and_manager

    health = client.get("/health")
    sources = client.get("/sources")
    source = client.get("/sources/cam_child")
    status = client.get("/sources/cam_child/status")

    assert health.json() == {"status": "ok", "service": "videostream-analytics"}
    assert sources.json() == [SOURCE_STATUS]
    assert source.json() == SOURCE_STATUS
    assert status.json() == SOURCE_STATUS


def test_register_source_uses_nested_pipeline_schema(client_and_manager):
    client, manager, _ = client_and_manager

    response = client.post(
        "/register_source",
        json={
            "source_id": "cam_child",
            "source_url": "rtsp://localhost:8554/live/child",
            "webhook_url": "http://localhost:3101/events",
            "data_dir": "/data/cam_child",
            "pipeline": {
                "motion": {"diff_threshold": 15, "area_ratio": 0.005, "stable_frames": 45},
                "keepalive": {"enabled": True, "timeout_seconds": 90, "check_interval_seconds": 10},
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    source = manager.register_source.call_args.args[0]
    assert source.source_id == "cam_child"
    assert source.motion.diff_threshold == 15
    assert source.keepalive.enabled is True


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("delete", "/sources/cam_child"),
        ("post", "/sources/cam_child/stop"),
    ],
)
def test_path_unregister_variants(client_and_manager, method: str, path: str):
    client, manager, _ = client_and_manager

    response = getattr(client, method)(path)

    assert response.status_code == 200
    assert response.json() == {"status": "stopped", "source_id": "cam_child"}
    manager.unregister_source.assert_called_with("cam_child")


def test_body_unregister_variant(client_and_manager):
    client, manager, _ = client_and_manager

    response = client.request("DELETE", "/unregister_source", json={"source_id": "cam_child"})

    assert response.status_code == 200
    manager.unregister_source.assert_called_with("cam_child")


def test_restart_controls_pipeline_and_recorder(client_and_manager):
    client, _, bundle = client_and_manager

    response = client.post("/sources/cam_child/restart")

    assert response.json() == {"status": "restarted", "source_id": "cam_child"}
    bundle.pipeline.stop.assert_called_once_with()
    bundle.pipeline.start.assert_called_once_with()
    bundle.recorder.stop.assert_called_once_with()
    bundle.recorder.start.assert_called_once_with()


@pytest.mark.parametrize(
    ("path", "method_name", "expected_status"),
    [
        ("pause", "pause_source", "paused"),
        ("resume", "resume_source", "online"),
        ("keepalive", "keepalive_source", "ok"),
    ],
)
def test_runtime_controls(client_and_manager, path: str, method_name: str, expected_status: str):
    client, manager, _ = client_and_manager

    response = client.post(f"/sources/cam_child/{path}")

    assert response.status_code == 200
    assert response.json()["status"] == expected_status
    getattr(manager, method_name).assert_called_with("cam_child")


def test_hot_update_pipeline(client_and_manager):
    client, manager, _ = client_and_manager

    response = client.put(
        "/sources/cam_child/pipeline",
        json={
            "pipeline": {
                "health": {
                    "max_failures": 3,
                    "recovery_strategy": "pause",
                    "backoff_base": 1.0,
                    "backoff_max": 5.0,
                }
            }
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "updated", "source_id": "cam_child"}
    assert manager.update_pipeline_config.call_args.kwargs["health"].max_failures == 3


def test_unknown_source_returns_404(client_and_manager):
    client, manager, _ = client_and_manager
    manager.get_source_status.return_value = None

    response = client.get("/sources/missing/status")

    assert response.status_code == 404
    assert response.json() == {"detail": "Source not found: missing"}


def test_legacy_register_fields_return_422(client_and_manager):
    client, _, _ = client_and_manager

    response = client.post(
        "/register_source",
        json={"source_id": "cam_child", "rtsp_url": "rtsp://legacy", "use_case": "child_safety"},
    )

    assert response.status_code == 422
    assert {"rtsp_url", "use_case"} <= set(response.json()["unknown_fields"])