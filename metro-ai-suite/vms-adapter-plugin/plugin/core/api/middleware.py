# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""X-API-Key middleware.

Auth is plugin-internal (the App→Plugin contract). The middleware is
enabled only when ``config.api.api_key`` is non-empty; otherwise it is
a pass-through. ``/v1/health``, ``/v1/ready``, and the OpenAPI/docs
endpoints are always exempt.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

_EXEMPT_PATHS = frozenset({
    "/v1/health", "/v1/ready",
    "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect",
})


def install_api_key_middleware(app: FastAPI, api_key: str) -> None:
    if not api_key:
        return

    @app.middleware("http")
    async def _api_key_check(request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS or request.url.path.startswith("/docs"):
            return await call_next(request)
        if request.headers.get("X-API-Key") != api_key:
            return JSONResponse(
                {"detail": "Invalid or missing X-API-Key"}, status_code=401,
            )
        return await call_next(request)
