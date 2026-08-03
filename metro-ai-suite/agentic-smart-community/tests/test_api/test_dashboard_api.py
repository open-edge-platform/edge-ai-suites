# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for docs/user-guide/get-started/api-reference-dashboard.md."""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from conftest import McpApiClient, http_json


def _http_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


@pytest.fixture
def dashboard_monitor(mcp_api: McpApiClient):
    monitor_id = "dashboard_api_cam"
    data_dir: Path = mcp_api.data_dir  # type: ignore[attr-defined]
    monitor_dir = data_dir / "segments" / monitor_id
    monitor_dir.mkdir(parents=True)
    (monitor_dir / "latest.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    full_clip = monitor_dir / "full.mp4"
    full_clip.write_bytes(b"full-video")
    cropped_clip = monitor_dir / "cropped.mp4"
    cropped_clip.write_bytes(b"cropped-video")
    outside_clip = data_dir / "outside.mp4"
    outside_clip.write_bytes(b"outside")

    database_path = data_dir / "smartbuilding.db"
    with sqlite3.connect(database_path) as database:
        database.execute(
            """
            INSERT INTO monitors
                (id, name, source_url, status, use_case, video_summary_task)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                monitor_id,
                "Dashboard API Camera",
                "rtsp://user:secret@localhost/live",
                "online",
                "child_safety",
                "child_safety_monitor",
            ),
        )
        event_id = database.execute(
            """
            INSERT INTO events
                (monitor_id, motion_type, start_time, duration_seconds, event_file_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (monitor_id, "motion", "2026-07-30T09:00:00", 4.0, str(full_clip)),
        ).lastrowid
        full_task_id = database.execute(
            """
            INSERT INTO video_summary_tasks
                (monitor_id, event_id, summary_clip_input, status)
            VALUES (?, ?, ?, ?)
            """,
            (monitor_id, event_id, str(cropped_clip), "completed"),
        ).lastrowid
        outside_task_id = database.execute(
            """
            INSERT INTO video_summary_tasks
                (monitor_id, summary_clip_input, status)
            VALUES (?, ?, ?)
            """,
            (monitor_id, str(outside_clip), "completed"),
        ).lastrowid

    yield {
        "id": monitor_id,
        "full_task_id": full_task_id,
        "outside_task_id": outside_task_id,
    }

    with sqlite3.connect(database_path) as database:
        database.execute("DELETE FROM video_summary_tasks WHERE monitor_id = ?", (monitor_id,))
        database.execute("DELETE FROM events WHERE monitor_id = ?", (monitor_id,))
        database.execute("DELETE FROM monitors WHERE id = ?", (monitor_id,))
    for path in monitor_dir.iterdir():
        path.unlink()
    monitor_dir.rmdir()
    outside_clip.unlink()


def test_dashboard_configuration_accepts_private_openclaw_gateway(mcp_api: McpApiClient):
    dashboard_url = mcp_api.url.removesuffix("/mcp")

    status, _, config = http_json(f"{dashboard_url}/api/dashboard/config")
    assert status == 200
    assert config["router"] == "unconfigured"
    assert config["chat"] == "unconfigured"
    assert [framework["id"] for framework in config["frameworks"]] == ["openclaw"]

    rejected_status, _, _ = http_json(
        f"{dashboard_url}/api/dashboard/chat/config",
        method="POST",
        body={"framework": "openclaw", "url": "https://example.com", "token": "secret"},
    )
    assert rejected_status == 400

    configured_status, headers, body = http_json(
        f"{dashboard_url}/api/dashboard/chat/config",
        method="POST",
        body={"framework": "openclaw", "url": "http://127.0.0.1:18789/", "token": "secret"},
    )
    assert configured_status == 200
    assert "secret" not in json.dumps(body)
    assert "HttpOnly" in headers["Set-Cookie"]


def test_dashboard_monitor_media_contract(mcp_api: McpApiClient, dashboard_monitor: dict):
    dashboard_url = mcp_api.url.removesuffix("/mcp")
    monitor_id = dashboard_monitor["id"]

    status, _, monitors = http_json(f"{dashboard_url}/api/monitors")
    assert status == 200
    monitor = next(item for item in monitors if item["id"] == monitor_id)
    assert "sourceUrl" not in monitor
    assert "secret" not in json.dumps(monitor)

    snapshot_status, snapshot_headers, snapshot = _http_bytes(
        f"{dashboard_url}/api/monitors/{monitor_id}/snapshot"
    )
    assert snapshot_status == 200
    assert snapshot_headers["Content-Type"] == "image/jpeg"
    assert snapshot == b"\xff\xd8\xff\xd9"

    clip_status, _, clip = _http_bytes(
        f"{dashboard_url}/api/tasks/{dashboard_monitor['full_task_id']}/clip"
        f"?monitor_id={monitor_id}"
    )
    assert clip_status == 200
    assert clip == b"full-video"

    outside_status, _, _ = _http_bytes(
        f"{dashboard_url}/api/tasks/{dashboard_monitor['outside_task_id']}/clip"
        f"?monitor_id={monitor_id}"
    )
    assert outside_status == 404

    wrong_monitor_status, _, _ = _http_bytes(
        f"{dashboard_url}/api/tasks/{dashboard_monitor['full_task_id']}/clip"
        "?monitor_id=another_monitor"
    )
    assert wrong_monitor_status == 404