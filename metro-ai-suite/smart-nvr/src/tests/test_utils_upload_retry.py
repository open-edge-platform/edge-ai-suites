# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Retry & batch upload utility tests."""
import os
import requests
import types
from unittest.mock import patch, MagicMock
from utils.utils import upload_single_video_with_retry, upload_videos_to_dataprep


class DummyResp:
    def __init__(self, json_data=None, status_code=200):
        self._json = json_data or {}
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=MagicMock(status_code=self.status_code, text='err'))


def test_upload_single_video_with_retry_success(tmp_path, monkeypatch):
    # Create temp file
    f = tmp_path / 'video.mp4'
    f.write_bytes(b'0' * 1024)

    calls = []

    def side_effect(*args, **kwargs):
        calls.append(args[0])
        # First attempt fails (simulate network issue)
        if len(calls) == 1:
            raise Exception('net fail')
        # Second attempt: first POST (video upload)
        if 'videos/' in args[0] and len(calls) == 2:
            return DummyResp({'videoId': 'vid123'})
        # Second attempt: second POST (embedding)
        if 'search-embeddings' in args[0]:
            return DummyResp({'message': 'ok'})
        return DummyResp({})

    monkeypatch.setattr('time.sleep', lambda x: None)
    with patch('utils.utils.requests.post', side_effect=side_effect):
        assert upload_single_video_with_retry(str(f), max_retries=3) is True


def test_upload_single_video_with_retry_exhaust(tmp_path, monkeypatch):
    f = tmp_path / 'video2.mp4'
    f.write_bytes(b'1' * 2048)

    monkeypatch.setattr('time.sleep', lambda x: None)
    with patch('utils.utils.requests.post', side_effect=Exception('always fail')):
        assert upload_single_video_with_retry(str(f), max_retries=2) is False


def test_upload_videos_to_dataprep_skips_duplicates(tmp_path, monkeypatch):
    f1 = tmp_path / 'clip1.mp4'
    f2 = tmp_path / 'clip2.mp4'
    f1.write_bytes(b'2' * 1024)
    f2.write_bytes(b'3' * 1024)

    # Arrange: first upload success, second file duplicate path scenario
    posted = []

    def post_side(url, files=None):
        posted.append(url)
        # Simulate sequential success for video and embedding endpoints
        if 'videos/search-embeddings' in url:
            return DummyResp({'message': 'embeddings ok'})
        return DummyResp({'videoId': 'vidXYZ'})

    monkeypatch.setattr('utils.utils.requests.post', post_side)
    # First batch: both files processed
    assert upload_videos_to_dataprep([str(f1), str(f2)]) is True
    # Second batch: skip both (already uploaded)
    assert upload_videos_to_dataprep([str(f1), str(f2)]) is True