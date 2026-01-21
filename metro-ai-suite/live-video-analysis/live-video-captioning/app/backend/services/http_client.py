import json
from typing import Any, Optional
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from fastapi import HTTPException


def http_json(method: str, url: str, payload: Optional[dict[str, Any]] = None) -> str:
    """Make an HTTP request with JSON payload and return response text."""
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
