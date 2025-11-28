# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for upload utility functions."""
from unittest.mock import patch, MagicMock
from utils.utils import upload_single_video_with_retry, upload_videos_to_dataprep


def test_upload_single_success(tmp_path, monkeypatch):
    fp = tmp_path / "file.mp4"
    fp.write_bytes(b"0" * 600_000)

    post_calls = []

    def fake_post(url, files=None):
        m = MagicMock()
        if "search-embeddings" in url:
            m.raise_for_status.return_value = None
            m.json.return_value = {"status": "ok"}
        else:
            m.raise_for_status.return_value = None
            m.json.return_value = {"videoId": "vid123"}
        post_calls.append(url)
        return m

    monkeypatch.setattr("utils.utils.requests.post", fake_post)

    assert upload_single_video_with_retry(str(fp), max_retries=2) is True
    assert any("videos/" in c for c in post_calls)
    assert any("search-embeddings" in c for c in post_calls)


def test_upload_single_failure(tmp_path, monkeypatch):
    fp = tmp_path / "file.mp4"
    fp.write_bytes(b"0" * 600_000)

    def fake_post(url, files=None):
        raise Exception("boom")

    monkeypatch.setattr("utils.utils.requests.post", fake_post)

    assert upload_single_video_with_retry(str(fp), max_retries=2) is False


def test_upload_batch(tmp_path, monkeypatch):
    f1 = tmp_path / "f1.mp4"
    f1.write_bytes(b"0" * 600_000)
    f2 = tmp_path / "f2.mp4"
    f2.write_bytes(b"0" * 600_000)

    def fake_single(path, max_retries=3):
        return True

    monkeypatch.setattr("utils.utils.upload_single_video_with_retry", fake_single)
    assert upload_videos_to_dataprep([str(f1), str(f2)]) is True
