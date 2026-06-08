import json
from typing import Any, Optional, Tuple
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from fastapi import HTTPException
from ..config import PIPELINE_SERVER_URL


def _effective_port(scheme: str, port: Optional[int]) -> Optional[int]:
    if port is not None:
        return port
    if scheme == "http":
        return 80
    if scheme == "https":
        return 443
    return None


def _assert_trusted_pipeline_url(url: str) -> None:
    """Reject outbound requests that do not target the configured pipeline server."""
    candidate = urlsplit((url or "").strip())
    trusted = urlsplit(PIPELINE_SERVER_URL.strip())

    if (
        candidate.scheme not in {"http", "https"}
        or candidate.scheme != trusted.scheme
        or not candidate.hostname
        or not trusted.hostname
        or candidate.hostname.lower() != trusted.hostname.lower()
        or _effective_port(candidate.scheme, candidate.port)
        != _effective_port(trusted.scheme, trusted.port)
    ):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Outbound URL is not allowed",
            },
        )


def http_json(method: str, url: str, payload: Optional[dict[str, Any]] = None) -> str:
    """Make an HTTP request with JSON payload and return response text."""
    _assert_trusted_pipeline_url(url)
    headers = {
        "Accept": "application/json",
    }
    data = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        data = body
        headers["Content-Type"] = "application/json"
    req = urllib_request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib_request.urlopen(req, timeout=120) as resp:
            return resp.read().decode("utf-8")
    except HTTPError as err:
        details = None
        try:
            details = err.read().decode("utf-8")
        except Exception:
            details = None
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Pipeline server error",
                "status": err.code,
                "body": details,
            },
        )
    except URLError as err:
        raise HTTPException(
            status_code=502,
            detail={"message": "Pipeline server unreachable", "error": str(err)},
        )
    except OSError as err:
        raise HTTPException(
            status_code=502,
            detail={"message": "Pipeline server connection failed", "error": str(err)},
        )


def try_get_json(url: str, timeout: int = 10) -> Tuple[Optional[int], Optional[dict]]:
    """Attempt a GET request and return (http_status_code, parsed_body).

    Unlike http_json, this function never raises. It returns (None, None) when
    the server is unreachable or the connection fails, allowing callers to treat
    network failures differently from HTTP error responses.

    Args:
        url: The URL to GET.
        timeout: Request timeout in seconds.

    Returns:
        A tuple of (status_code, body). status_code is None on connection
        failure; body is None when the response is not valid JSON.
    """
    try:
        _assert_trusted_pipeline_url(url)
    except HTTPException:
        return None, None
    req = urllib_request.Request(
        url=url, headers={"Accept": "application/json"}, method="GET"
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            try:
                body = json.loads(resp.read().decode("utf-8"))
            except Exception:
                body = None
            return resp.status, body
    except HTTPError as err:
        try:
            body = json.loads(err.read().decode("utf-8"))
        except Exception:
            body = None
        return err.code, body
    except (URLError, OSError):
        return None, None
