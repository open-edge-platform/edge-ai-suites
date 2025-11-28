# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for VmsService summarization and search operations."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from service.vms_service import VmsService
from api.endpoints.frigate_api import FrigateService
from api.endpoints.summarization_api import SummarizationService
from fastapi import HTTPException
import types


class DummyStream:
    def __init__(self, chunks):
        async def iterator():
            for c in chunks:
                yield c
        self.body_iterator = iterator()


@pytest.mark.asyncio
async def test_upload_video_small_file(monkeypatch, tmp_path):
    # Frigate returns tiny stream -> triggers 404 logic path (size <=100)
    fs = FrigateService(base_url='x')
    ss = SummarizationService()
    v = VmsService(fs, ss)
    monkeypatch.setattr(fs, 'get_clip_from_timestamps', lambda *a, **k: DummyStream([b'xx']))
    resp = await v.upload_video_to_summarizer('cam', 1, 2, False)
    assert resp['status'] == 404


@pytest.mark.asyncio
async def test_upload_video_success(monkeypatch, tmp_path):
    fs = FrigateService(base_url='x')
    ss = SummarizationService()
    v = VmsService(fs, ss)
    # Provide large enough stream
    monkeypatch.setattr(fs, 'get_clip_from_timestamps', lambda *a, **k: DummyStream([b'a' * 150]))
    monkeypatch.setattr(ss, 'video_upload', lambda path, base: {'videoId': 'vid123'})
    resp = await v.upload_video_to_summarizer('cam', 1, 5, False)
    assert resp['status'] == 200 and resp['message'] == 'vid123'


@pytest.mark.asyncio
async def test_summary_empty_frames(monkeypatch):
    fs = FrigateService(base_url='x')
    ss = SummarizationService()
    v = VmsService(fs, ss)
    with patch('service.vms_service.summarization_service.get_summary_result', return_value={'frameSummaries': [{'startFrame':1,'endFrame':2,'status':'processing','summary':None}]}):
        result = v.summary('pipe123')
        assert 'Final summary is being generated' in result['summary']
        assert result['frameSummaries'][0]['status'] == 'processing'


@pytest.mark.asyncio
async def test_search_embeddings_success(monkeypatch):
    fs = FrigateService(base_url='x')
    ss = SummarizationService()
    v = VmsService(fs, ss)
    async def fake_upload(*a, **k):
        return {'status':200,'message':'vid77'}
    monkeypatch.setattr(v, 'upload_video_to_summarizer', fake_upload)
    with patch('service.vms_service.requests.post') as mpost:
        mpost.return_value = MagicMock(status_code=200, json=lambda: {'message':'ok'}, raise_for_status=lambda: None)
        resp = await v.search_embeddings('cam',1,2)
        assert resp['status'] == 200 and resp['video_id'] == 'vid77'


@pytest.mark.asyncio
async def test_search_embeddings_failure(monkeypatch):
    fs = FrigateService(base_url='x')
    ss = SummarizationService()
    v = VmsService(fs, ss)
    async def fake_upload(*a, **k):
        return {'status':200,'message':'vid99'}
    monkeypatch.setattr(v, 'upload_video_to_summarizer', fake_upload)
    with patch('service.vms_service.requests.post', side_effect=Exception('fail')):
        with pytest.raises(Exception):
            await v.search_embeddings('cam',1,2)
