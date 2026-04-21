# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.http_client, HTTP JSON helper."""

from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

import pytest
from fastapi import HTTPException

from backend.services.http_client import http_json, try_get_json


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

    def test_os_error_raises_502(self):
        """A low-level OSError is wrapped in a 502 HTTPException."""
        with patch(
            "backend.services.http_client.urllib_request.urlopen",
            side_effect=OSError("broken pipe"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                http_json("GET", "http://example.com/api")

        assert exc_info.value.status_code == 502
        assert "connection failed" in str(exc_info.value.detail)


class TestTryGetJson:
    """Non-raising JSON GET helper behavior."""

    def test_success_returns_status_and_json(self):
        """Valid JSON body returns (status, parsed_dict)."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch(
            "backend.services.http_client.urllib_request.urlopen",
            return_value=mock_resp,
        ):
            status, body = try_get_json("http://example.com/status")

        assert status == 200
        assert body == {"ok": True}

    def test_success_with_invalid_json_returns_none_body(self):
        """Invalid JSON response body returns (status, None)."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"not-json"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch(
            "backend.services.http_client.urllib_request.urlopen",
            return_value=mock_resp,
        ):
            status, body = try_get_json("http://example.com/status")

        assert status == 200
        assert body is None

    def test_http_error_returns_status_and_parsed_body(self):
        """HTTPError is converted into (status, body) instead of raising."""
        err = HTTPError(
            url="http://example.com",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=b'{"error": "down"}')),
        )

        with patch(
            "backend.services.http_client.urllib_request.urlopen", side_effect=err
        ):
            status, body = try_get_json("http://example.com/status")

        assert status == 503
        assert body == {"error": "down"}

    def test_http_error_with_invalid_body_returns_none_body(self):
        """HTTPError with non-JSON body returns (status, None)."""
        err = HTTPError(
            url="http://example.com",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=b"oops")),
        )

        with patch(
            "backend.services.http_client.urllib_request.urlopen", side_effect=err
        ):
            status, body = try_get_json("http://example.com/status")

        assert status == 500
        assert body is None

    def test_connection_failure_returns_none_tuple(self):
        """URLError and OSError both return (None, None)."""
        with patch(
            "backend.services.http_client.urllib_request.urlopen",
            side_effect=URLError("connection refused"),
        ):
            status, body = try_get_json("http://example.com/status")
        assert status is None
        assert body is None

        with patch(
            "backend.services.http_client.urllib_request.urlopen",
            side_effect=OSError("network down"),
        ):
            status, body = try_get_json("http://example.com/status")
        assert status is None
        assert body is None
