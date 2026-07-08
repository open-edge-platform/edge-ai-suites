# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for backend.services.http_client, HTTP JSON helper."""

import io
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest
from fastapi import HTTPException

from backend.services.http_client import _effective_port, http_json, try_get_json


TRUSTED_BASE = "http://dlstreamer-pipeline-server:8080"


def _mock_response(body: bytes, status: int = 200):
    """Build a context-manager mock mimicking urllib's urlopen response."""
    resp = MagicMock()
    resp.read.return_value = body
    resp.status = status
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


class TestHttpJsonSuccess:
    """Happy-path tests for http_json."""

    def test_get_request_returns_body(self):
        """A successful GET returns the response body as a string."""
        with patch(
            "backend.services.http_client.urllib_request.urlopen"
        ) as mock_urlopen:
            mock_urlopen.return_value = _mock_response(b'{"ok": true}')
            result = http_json("GET", f"{TRUSTED_BASE}/api")
        assert result == '{"ok": true}'

    def test_post_request_with_payload(self):
        """A POST request with a JSON payload is sent and its response returned."""
        with patch(
            "backend.services.http_client.urllib_request.urlopen"
        ) as mock_urlopen:
            mock_urlopen.return_value = _mock_response(b'"pipeline-123"')
            result = http_json("POST", f"{TRUSTED_BASE}/api", payload={"key": "val"})

        assert result == '"pipeline-123"'
        sent_req = mock_urlopen.call_args.args[0]
        assert sent_req.data == b'{"key": "val"}'
        assert sent_req.get_header("Content-type") == "application/json"


class TestHttpJsonErrors:
    """Error-handling paths for http_json."""

    def test_http_status_error_raises_502(self):
        """A non-2xx upstream response is wrapped in a 502 HTTPException."""
        err = HTTPError(
            url=f"{TRUSTED_BASE}/api",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=io.BytesIO(b"server broke"),
        )
        with patch(
            "backend.services.http_client.urllib_request.urlopen", side_effect=err
        ):
            with pytest.raises(HTTPException) as exc_info:
                http_json("GET", f"{TRUSTED_BASE}/api")

        assert exc_info.value.status_code == 502
        assert "Pipeline server error" in str(exc_info.value.detail)

    def test_http_status_error_with_unreadable_body_sets_none(self):
        """Unreadable upstream error bodies are reported as body=None."""
        err = HTTPError(
            url=f"{TRUSTED_BASE}/api",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=io.BytesIO(b"ignored"),
        )
        with patch.object(err, "read", side_effect=ValueError("cannot read")), patch(
            "backend.services.http_client.urllib_request.urlopen", side_effect=err
        ):
            with pytest.raises(HTTPException) as exc_info:
                http_json("GET", f"{TRUSTED_BASE}/api")

        assert exc_info.value.status_code == 502
        assert exc_info.value.detail["status"] == 500
        assert exc_info.value.detail["body"] is None

    def test_request_error_raises_502(self):
        """A network-level URLError is wrapped in a 502 HTTPException."""
        with patch(
            "backend.services.http_client.urllib_request.urlopen",
            side_effect=URLError("Connection refused"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                http_json("GET", f"{TRUSTED_BASE}/api")

        assert exc_info.value.status_code == 502
        assert "unreachable" in str(exc_info.value.detail)

    def test_os_error_raises_502(self):
        """A low-level OSError is wrapped in a 502 HTTPException."""
        with patch(
            "backend.services.http_client.urllib_request.urlopen",
            side_effect=OSError("socket closed"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                http_json("GET", f"{TRUSTED_BASE}/api")

        assert exc_info.value.status_code == 502
        assert "connection failed" in str(exc_info.value.detail)

    def test_untrusted_url_rejected_before_request(self):
        """Requests to non-configured hosts are rejected without making network calls."""
        with patch(
            "backend.services.http_client.urllib_request.urlopen"
        ) as mock_urlopen:
            with pytest.raises(HTTPException) as exc_info:
                http_json("GET", "http://example.com/api")

        assert exc_info.value.status_code == 400
        assert "not allowed" in str(exc_info.value.detail)
        mock_urlopen.assert_not_called()


class TestTryGetJson:
    """Non-raising JSON GET helper behavior."""

    def test_success_returns_status_and_json(self):
        """Valid JSON body returns (status, parsed_dict)."""
        with patch(
            "backend.services.http_client.urllib_request.urlopen"
        ) as mock_urlopen:
            mock_urlopen.return_value = _mock_response(b'{"ok": true}')
            status, body = try_get_json(f"{TRUSTED_BASE}/status")

        assert status == 200
        assert body == {"ok": True}

    def test_success_with_invalid_json_returns_none_body(self):
        """Invalid JSON response body returns (status, None)."""
        with patch(
            "backend.services.http_client.urllib_request.urlopen"
        ) as mock_urlopen:
            mock_urlopen.return_value = _mock_response(b"not-json")
            status, body = try_get_json(f"{TRUSTED_BASE}/status")

        assert status == 200
        assert body is None

    def test_http_status_error_returns_status_and_body(self):
        """HTTPError is converted into (status, body) instead of raising."""
        err = HTTPError(
            url=f"{TRUSTED_BASE}/status",
            code=503,
            msg="down",
            hdrs=None,
            fp=io.BytesIO(b'{"error": "down"}'),
        )
        with patch(
            "backend.services.http_client.urllib_request.urlopen", side_effect=err
        ):
            status, body = try_get_json(f"{TRUSTED_BASE}/status")

        assert status == 503
        assert body == {"error": "down"}

    def test_http_status_error_with_invalid_body_returns_none_body(self):
        """HTTPError with non-JSON body returns (status, None)."""
        err = HTTPError(
            url=f"{TRUSTED_BASE}/status",
            code=500,
            msg="oops",
            hdrs=None,
            fp=io.BytesIO(b"oops"),
        )
        with patch(
            "backend.services.http_client.urllib_request.urlopen", side_effect=err
        ):
            status, body = try_get_json(f"{TRUSTED_BASE}/status")

        assert status == 500
        assert body is None

    def test_connection_failure_returns_none_tuple(self):
        """Network-level URLError returns (None, None)."""
        with patch(
            "backend.services.http_client.urllib_request.urlopen",
            side_effect=URLError("connection refused"),
        ):
            status, body = try_get_json(f"{TRUSTED_BASE}/status")

        assert status is None
        assert body is None

    def test_untrusted_url_returns_none_tuple(self):
        """Untrusted target URLs are rejected as connection failures for callers."""
        status, body = try_get_json("https://example.com/status")
        assert status is None
        assert body is None


class TestEffectivePort:
    """Unit tests for effective-port normalization."""

    def test_infers_default_http_and_https_ports(self):
        """Missing standard scheme ports map to defaults."""
        assert _effective_port("http", None) == 80
        assert _effective_port("https", None) == 443

    def test_returns_none_for_unknown_scheme_without_port(self):
        """Unknown schemes with no explicit port return None."""
        assert _effective_port("ftp", None) is None


