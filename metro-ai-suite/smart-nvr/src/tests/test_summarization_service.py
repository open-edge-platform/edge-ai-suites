# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for summarization service video upload and summary retrieval."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import requests
from api.endpoints.summarization_api import SummarizationService
from model.model import Sampling, Evam, SummaryPayload


def test_video_upload_file_missing(tmp_path):
    svc = SummarizationService()
    with pytest.raises(Exception):
        svc.video_upload(tmp_path / 'nope.mp4', 'http://fake')


def test_video_upload_request_exception(tmp_path):
    svc = SummarizationService()
    f = tmp_path / 'clip.mp4'
    f.write_bytes(b'1234')
    err_resp = MagicMock()
    err_resp.status_code = 500
    err = requests.exceptions.RequestException('fail')
    with patch('api.endpoints.summarization_api.requests.post', side_effect=err):
        with pytest.raises(Exception):
            svc.video_upload(f, 'http://fake')


def test_video_upload_success(tmp_path):
    svc = SummarizationService()
    f = tmp_path / 'clip2.mp4'
    f.write_bytes(b'0' * 2048)
    with patch('api.endpoints.summarization_api.requests.post') as mpost:
        mpost.return_value = MagicMock(status_code=200, json=lambda: {'videoId': 'vid1'}, raise_for_status=lambda: None)
        resp = svc.video_upload(f, 'http://fake')
        assert resp['videoId'] == 'vid1'


def test_create_summary_success():
    svc = SummarizationService()
    payload = SummaryPayload(videoId='v1', title='t', sampling=Sampling(chunkDuration=8, samplingFrame=8), evam=Evam(evamPipeline='object_detection'))
    with patch('api.endpoints.summarization_api.requests.post') as mpost:
        mpost.return_value = MagicMock(status_code=200, json=lambda: {'summaryPipelineId': 'p1'}, raise_for_status=lambda: None)
        resp = svc.create_summary(payload, 'http://fake')
        assert resp['summaryPipelineId'] == 'p1'


def test_get_summary_result_success():
    svc = SummarizationService()
    with patch('api.endpoints.summarization_api.requests.get') as mget:
        mget.return_value = MagicMock(status_code=200, json=lambda: {'summary': 'done'}, raise_for_status=lambda: None)
        resp = svc.get_summary_result('abc', 'http://fake')
        assert resp['summary'] == 'done'