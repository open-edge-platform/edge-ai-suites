# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.http_client, HTTP JSON helper."""

from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

import pytest
from fastapi import HTTPException

from backend.services.http_client import http_json


class TestHttpJsonSuccess:
    """Happy-path tests for http_json."""

    def test_get_request_returns_body(self):
        """A successful GET returns the response body as a string."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch(
            "backend.services.http_client.urllib_request.urlopen",
            return_value=mock_resp,
        ):
            result = http_json("GET", "http://example.com/api")
        assert result == '{"ok": true}'

    def test_post_request_with_payload(self):
        """A POST request with a JSON payload returns the response body."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'"pipeline-123"'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch(
            "backend.services.http_client.urllib_request.urlopen",
            return_value=mock_resp,
        ) as mock_open:
            result = http_json("POST", "http://example.com/api", payload={"key": "val"})

        assert result == '"pipeline-123"'
        # Verify the request was constructed with data
        call_args = mock_open.call_args
        req_obj = call_args[0][0]
        assert req_obj.data is not None
        assert req_obj.get_method() == "POST"


class TestHttpJsonErrors:
    """Error-handling paths for http_json."""

    def test_http_error_raises_502(self):
        """An HTTPError from the upstream server is wrapped in a 502 HTTPException."""
        err = HTTPError(
            url="http://example.com",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=b"server broke")),
        )
        with patch(
            "backend.services.http_client.urllib_request.urlopen", side_effect=err
        ):
            with pytest.raises(HTTPException) as exc_info:
                http_json("GET", "http://example.com/api")
        assert exc_info.value.status_code == 502
        assert "Pipeline server error" in str(exc_info.value.detail)

    def test_url_error_raises_502(self):
        """A URLError (server unreachable) is wrapped in a 502 HTTPException."""
        with patch(
            "backend.services.http_client.urllib_request.urlopen",
            side_effect=URLError("Connection refused"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                http_json("GET", "http://unreachable:8080/api")
        assert exc_info.value.status_code == 502
        assert "unreachable" in str(exc_info.value.detail)

    def test_http_error_with_unreadable_body(self):
        """An HTTPError whose body cannot be read still raises 502."""
        err = HTTPError(
            url="http://example.com",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=MagicMock(read=MagicMock(side_effect=Exception("read failed"))),
        )
        with patch(
            "backend.services.http_client.urllib_request.urlopen", side_effect=err
        ):
            with pytest.raises(HTTPException) as exc_info:
                http_json("DELETE", "http://example.com/api")
        assert exc_info.value.status_code == 502
