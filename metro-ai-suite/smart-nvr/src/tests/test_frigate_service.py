# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for FrigateService interactions with external Frigate API."""
import pytest
from unittest.mock import patch, MagicMock
from api.endpoints.frigate_api import FrigateService
import requests


def test_get_camera_names_success():
    service = FrigateService(base_url='http://fake')
    fake_cfg = {"cameras": {"garage": {"objects": {"track": ["person"]}}, "yard": {"objects": {"track": []}}}}
    with patch('api.endpoints.frigate_api.requests.get') as mget:
        mget.return_value = MagicMock(status_code=200, json=lambda: fake_cfg)
        result = service.get_camera_names()
        assert result == {"garage": ["person"], "yard": []}


def test_get_camera_names_error():
    service = FrigateService(base_url='http://fake')
    with patch('api.endpoints.frigate_api.requests.get') as mget:
        mget.side_effect = requests.exceptions.RequestException('boom')
        with pytest.raises(Exception):
            service.get_camera_names()


def test_get_clip_from_timestamps_404():
    service = FrigateService(base_url='http://fake')
    fake_resp = MagicMock()
    fake_resp.status_code = 404
    fake_resp.text = 'not found'
    http_err = requests.exceptions.HTTPError(response=fake_resp)
    with patch('api.endpoints.frigate_api.requests.get', side_effect=http_err):
        with pytest.raises(Exception) as exc:
            service.get_clip_from_timestamps('garage', 1, 2)
        assert 'Clip not found' in str(exc.value)


def test_get_clip_from_timestamps_stream_success():
    service = FrigateService(base_url='http://fake')
    fake_stream = MagicMock()
    fake_stream.iter_content = lambda chunk_size: [b'a', b'b']
    fake_stream.headers = {'Content-Disposition': 'inline'}
    fake_stream.raise_for_status = lambda: None
    with patch('api.endpoints.frigate_api.requests.get', return_value=fake_stream):
        resp = service.get_clip_from_timestamps('garage', 1, 3)
        assert resp.media_type == 'video/mp4'