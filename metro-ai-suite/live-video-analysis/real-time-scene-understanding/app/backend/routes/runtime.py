# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import Response


def build_runtime_config_router(settings) -> APIRouter:
    """Builds a runtime config router for the FastAPI application"""
    router = APIRouter(prefix="/api", tags=["runtime config"])

    @router.get("/runtime-config.js", response_class=Response, summary="Runtime config for browser")
    async def runtime_config() -> Response:
        """Runtime config endpoint for browser"""
        payload = {
            "webrtcSignalingUrl": settings.WEBRTC_SIGNALING_URL,
            "webrtcSignalingPort": settings.WEBRTC_SIGNALING_PORT,
            "metricsServicePort": settings.METRICS_SERVICE_PORT,
            "alertVlmModel": settings.ALERT_VLM_MODEL,
            "alertVlmDevice": settings.ALERT_VLM_DEVICE,
            "alertVlmMaxTokens": settings.ALERT_VLM_MAX_TOKENS,
            "deepAnalyzerEnabled": settings.DEEP_ANALYZER_ENABLED,
            "deepAnalyzerModel": settings.DEEP_ANALYZER_MODEL,
            "deepAnalyzerDevice": settings.DEEP_ANALYZER_DEVICE,
            "deepAnalyzerMaxFrames": settings.DEEP_ANALYZER_MAX_FRAMES,
            "deepAnalyzerMaxTokens": settings.DEEP_ANALYZER_MAX_TOKENS,
        }
        body = f"window.RUNTIME_CONFIG = {json.dumps(payload)};"
        return Response(content=body, media_type="application/javascript")

    return router
