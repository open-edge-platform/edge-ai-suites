# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Retry & batch upload utility tests."""

import requests
from unittest.mock import patch, MagicMock
from utils.utils import (
    submit_embedding_batch,
    upload_single_video_with_retry,
    upload_videos_to_dataprep,
    wait_for_embedding_batch,
)


class DummyResp:
    def __init__(self, json_data=None, status_code=200):
        self._json = json_data or {}
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                response=MagicMock(status_code=self.status_code, text="err")
            )


def test_upload_single_video_with_retry_success(tmp_path, monkeypatch):
    # Create temp file
    f = tmp_path / "video.mp4"
    f.write_bytes(b"0" * 1024)

    calls = []

    def side_effect(*args, **kwargs):
        calls.append(args[0])
        # First attempt fails (simulate network issue)
        if len(calls) == 1:
            raise Exception("net fail")
        if "videos/" in args[0] and len(calls) == 2:
            return DummyResp({"videoId": "vid123"})
        return DummyResp({})

    monkeypatch.setattr("time.sleep", lambda x: None)
    with patch("utils.utils.requests.post", side_effect=side_effect):
        assert upload_single_video_with_retry(str(f), max_retries=3) == "vid123"


def test_upload_single_video_with_retry_exhaust(tmp_path, monkeypatch):
    f = tmp_path / "video2.mp4"
    f.write_bytes(b"1" * 2048)

    monkeypatch.setattr("time.sleep", lambda x: None)
    with patch("utils.utils.requests.post", side_effect=Exception("always fail")):
        assert upload_single_video_with_retry(str(f), max_retries=2) is None


def test_upload_videos_to_dataprep_skips_duplicates(tmp_path, monkeypatch):
    f1 = tmp_path / "clip1.mp4"
    f2 = tmp_path / "clip2.mp4"
    f1.write_bytes(b"2" * 1024)
    f2.write_bytes(b"3" * 1024)

    video_ids = {
        str(f1): "vid-1",
        str(f2): "vid-2",
    }

    monkeypatch.setattr(
        "utils.utils.upload_single_video_with_retry",
        lambda path, max_retries=3: video_ids[path],
    )
    monkeypatch.setattr(
        "utils.utils.submit_embedding_batch",
        lambda ids, max_retries=3: "job-1",
    )
    monkeypatch.setattr(
        "utils.utils.wait_for_embedding_batch",
        lambda job_id: {
            "state": "completed",
            "items": [
                {"video_id": "vid-1", "status": "success"},
                {"video_id": "vid-2", "status": "success"},
            ],
        },
    )

    assert upload_videos_to_dataprep([str(f1), str(f2)]) is True
    assert upload_videos_to_dataprep([str(f1), str(f2)]) is True


def test_submit_embedding_batch(monkeypatch):
    posted = {}

    def fake_post(url, json):
        posted["url"] = url
        posted["json"] = json
        return DummyResp({"job_id": "job-7", "accepted": 2})

    monkeypatch.setattr("utils.utils.requests.post", fake_post)

    assert submit_embedding_batch(["vid-1", "vid-2"]) == "job-7"
    assert posted["url"].endswith("/manager/videos/search-embeddings-batch")
    assert posted["json"] == {"videoIds": ["vid-1", "vid-2"]}


def test_wait_for_embedding_batch(monkeypatch):
    responses = iter(
        [
            DummyResp({"state": "running"}),
            DummyResp(
                {
                    "state": "completed_with_errors",
                    "items": [
                        {"video_id": "vid-1", "status": "success"},
                        {"video_id": "vid-2", "status": "error"},
                    ],
                }
            ),
        ]
    )
    monkeypatch.setattr("utils.utils.requests.get", lambda url: next(responses))
    monkeypatch.setattr("utils.utils.time.sleep", lambda _: None)

    status = wait_for_embedding_batch("job-8")

    assert status["state"] == "completed_with_errors"


def test_batch_only_marks_successful_items(tmp_path, monkeypatch):
    f1 = tmp_path / "success.mp4"
    f2 = tmp_path / "failure.mp4"
    f1.write_bytes(b"1")
    f2.write_bytes(b"2")

    video_ids = {str(f1): "vid-success", str(f2): "vid-failure"}
    monkeypatch.setattr(
        "utils.utils.upload_single_video_with_retry",
        lambda path, max_retries=3: video_ids[path],
    )
    monkeypatch.setattr(
        "utils.utils.submit_embedding_batch",
        lambda ids, max_retries=3: "job-partial",
    )
    monkeypatch.setattr(
        "utils.utils.wait_for_embedding_batch",
        lambda job_id: {
            "state": "completed_with_errors",
            "items": [
                {"video_id": "vid-success", "status": "success"},
                {
                    "video_id": "vid-failure",
                    "status": "error",
                    "message": "processing failed",
                },
            ],
        },
    )

    assert upload_videos_to_dataprep([str(f1), str(f2)]) is False


def test_watcher_group_is_split_by_configured_batch_size(tmp_path, monkeypatch):
    paths = []
    video_ids = {}
    for index in range(3):
        path = tmp_path / f"clip-{index}.mp4"
        path.write_bytes(b"video")
        paths.append(str(path))
        video_ids[str(path)] = f"vid-{index}"

    submitted = []

    def fake_submit(ids, max_retries=3):
        submitted.append(ids)
        return f"job-{len(submitted)}"

    def fake_wait(job_id):
        batch_index = int(job_id.removeprefix("job-")) - 1
        return {
            "state": "completed",
            "items": [
                {"video_id": video_id, "status": "success"}
                for video_id in submitted[batch_index]
            ],
        }

    monkeypatch.setattr(
        "utils.utils.upload_single_video_with_retry",
        lambda path, max_retries=3: video_ids[path],
    )
    monkeypatch.setattr("utils.utils.submit_embedding_batch", fake_submit)
    monkeypatch.setattr("utils.utils.wait_for_embedding_batch", fake_wait)
    monkeypatch.setattr("utils.utils.settings.WATCH_BATCH_SIZE", 2)

    assert upload_videos_to_dataprep(paths) is True
    assert submitted == [["vid-0", "vid-1"], ["vid-2"]]
