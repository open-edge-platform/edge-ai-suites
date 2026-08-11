# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for api-reference-mcp-webhook-event.md."""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request

import pytest

from conftest import McpApiClient, http_json


def _post_event(mcp_api: McpApiClient, event_type: str, payload: dict):
    return http_json(
        f"{mcp_api.events_url}/events",  # type: ignore[attr-defined]
        method="POST",
        body={
            "sourceId": "cam_child",
            "type": event_type,
            "timestamp": "2026-06-25T14:30:45Z",
            "payload": payload,
        },
    )


def _post_raw(url: str, body: bytes, content_type: str) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_health_probe(mcp_api: McpApiClient):
    status, _, body = http_json(f"{mcp_api.events_url}/health")  # type: ignore[attr-defined]

    assert status == 200
    assert body == {"status": "healthy"}


@pytest.mark.parametrize(
    ("prefilter_passed", "expected_status"),
    [(None, "pending"), (1, "pending"), (0, "ignored")],
)
def test_motion_examples_create_event_and_task(
    mcp_api: McpApiClient,
    prefilter_passed: int | None,
    expected_status: str,
):
    payload = {
        "event_file_path": "/data/cam_child/motion_events/segment.mp4",
        "summary_clip_input": "/data/cam_child/motion_events/segment_input.mp4",
        "start_time": "2026-06-25T14:30:30Z",
        "end_time": "2026-06-25T14:30:45Z",
        "duration_seconds": 15.0,
    }
    if prefilter_passed is not None:
        payload["prefilter_passed"] = prefilter_passed

    status, _, body = _post_event(mcp_api, "motion", payload)

    assert status == 200
    assert body["status"] == "ok"
    with sqlite3.connect(mcp_api.data_dir / "smart-community.db") as database:  # type: ignore[attr-defined]
        task_status = database.execute(
            "SELECT status FROM video_summary_tasks WHERE id = ?",
            (body["task_id"],),
        ).fetchone()[0]
    assert task_status == expected_status


def test_static_example_creates_event_without_task(mcp_api: McpApiClient):
    status, _, body = _post_event(
        mcp_api,
        "static",
        {
            "start_time": "2026-06-25T14:31:10Z",
            "end_time": "2026-06-25T14:31:25Z",
            "duration_seconds": 15.0,
        },
    )

    assert status == 200
    assert "event_id" in body
    assert "task_id" not in body


def test_recording_example_creates_recording(mcp_api: McpApiClient):
    status, _, body = _post_event(
        mcp_api,
        "recording",
        {
            "recording_path": "/data/cam_child/recordings/recording.mp4",
            "recording_start": "2026-06-25T14:30:00Z",
            "recording_end": "2026-06-25T14:31:00Z",
            "duration_seconds": 60.0,
            "file_size_bytes": 8192000,
        },
    )

    assert status == 200
    assert isinstance(body["recording_id"], int)


@pytest.mark.parametrize(
    ("body", "expected_code"),
    [
        (
            {"sourceId": "cam_child", "type": "motion", "payload": {}},
            "missing_required_fields",
        ),
        (
            {"sourceId": "cam_child", "type": "audio", "payload": {}},
            "unknown_event_type",
        ),
        (
            {"sourceId": 123, "type": "motion", "payload": {}},
            "invalid_envelope",
        ),
    ],
)
def test_semantic_and_envelope_errors(mcp_api: McpApiClient, body: dict, expected_code: str):
    status, _, response = http_json(
        f"{mcp_api.events_url}/events",  # type: ignore[attr-defined]
        method="POST",
        body=body,
    )

    assert status in {400, 422}
    assert response["code"] == expected_code


def test_malformed_json_and_wrong_content_type(mcp_api: McpApiClient):
    url = f"{mcp_api.events_url}/events"  # type: ignore[attr-defined]

    malformed_status, malformed = _post_raw(url, b"not json", "application/json")
    media_status, media = _post_raw(url, b"{}", "text/plain")

    assert malformed_status == 400
    assert malformed["code"] == "invalid_json"
    assert media_status == 415
    assert media["code"] == "unsupported_media_type"