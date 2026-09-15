# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for upload utility functions."""

from unittest.mock import MagicMock

from utils.utils import (
    upload_single_video_with_retry,
    upload_videos_to_dataprep,
)


def test_upload_single_success(tmp_path, monkeypatch):
    fp = tmp_path / "file.mp4"
    fp.write_bytes(b"0" * 600_000)

    def fake_post(url, files=None, data=None):
        m = MagicMock()
        m.raise_for_status.return_value = None
        m.json.return_value = {"videoId": "vid123"}
        return m

    monkeypatch.setattr("utils.utils.requests.post", fake_post)

    assert upload_single_video_with_retry(str(fp), max_retries=2) == "vid123"


def test_upload_single_failure(tmp_path, monkeypatch):
    fp = tmp_path / "file.mp4"
    fp.write_bytes(b"0" * 600_000)

    def fake_post(url, files=None, data=None):  # signature alignment
        raise Exception("boom")

    monkeypatch.setattr("utils.utils.requests.post", fake_post)

    monkeypatch.setattr("utils.utils.time.sleep", lambda _: None)
    assert upload_single_video_with_retry(str(fp), max_retries=2) is None


def test_upload_batch(tmp_path, monkeypatch):
    f1 = tmp_path / "f1.mp4"
    f1.write_bytes(b"0" * 600_000)
    f2 = tmp_path / "f2.mp4"
    f2.write_bytes(b"0" * 600_000)

    video_ids = {
        str(f1): "vid-1",
        str(f2): "vid-2",
    }
    submitted = []

    def fake_single(path, max_retries=3):
        return video_ids[path]

    def fake_submit(ids, max_retries=3):
        submitted.append(ids)
        return "job-1"

    def fake_wait(job_id):
        assert job_id == "job-1"
        return {
            "state": "completed",
            "items": [
                {"video_id": "vid-1", "status": "success"},
                {"video_id": "vid-2", "status": "success"},
            ],
        }

    monkeypatch.setattr("utils.utils.upload_single_video_with_retry", fake_single)
    monkeypatch.setattr("utils.utils.submit_embedding_batch", fake_submit)
    monkeypatch.setattr("utils.utils.wait_for_embedding_batch", fake_wait)
    assert upload_videos_to_dataprep([str(f1), str(f2)]) is True
    assert submitted == [["vid-1", "vid-2"]]
