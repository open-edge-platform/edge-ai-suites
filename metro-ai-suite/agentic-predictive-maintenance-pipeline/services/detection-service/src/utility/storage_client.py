# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Storage client — HTTP calls to the storage-service REST API."""

import os
import logging
from typing import Optional
import requests

log = logging.getLogger(__name__)

_STORAGE_URL = os.environ.get("STORAGE_SERVICE_URL", "http://apm-storage:5001")
_API_KEY = os.environ.get("APM_API_KEY", "")
_TIMEOUT = 10
_NO_PROXY = {"http": None, "https": None}  # bypass system proxy for internal Docker calls
_HEADERS = {"X-API-Key": _API_KEY} if _API_KEY else {}


def get_detections(
    label: str | None = None,
    min_confidence: float | None = None,
    min_id: int | None = None,
    max_id: int | None = None,
    limit: int | None = 500,
) -> list[dict]:
    params: dict = {}
    if label:
        params["label"] = label
    if min_confidence is not None:
        params["min_confidence"] = min_confidence
    if min_id is not None:
        params["min_id"] = min_id
    if max_id is not None:
        params["max_id"] = max_id
    if limit is not None:
        params["limit"] = limit
    r = requests.get(
        f"{_STORAGE_URL}/detections",
        params=params,
        headers=_HEADERS,
        timeout=_TIMEOUT,
        proxies=_NO_PROXY,
    )
    r.raise_for_status()
    return r.json()


def get_summary(min_id: int | None = None, max_id: int | None = None) -> dict:
    params: dict = {}
    if min_id is not None:
        params["min_id"] = min_id
    if max_id is not None:
        params["max_id"] = max_id
    r = requests.get(
        f"{_STORAGE_URL}/detections/summary",
        params=params,
        headers=_HEADERS,
        timeout=_TIMEOUT,
        proxies=_NO_PROXY,
    )
    r.raise_for_status()
    return r.json()


def get_max_id() -> dict:
    """Return the current detection watermark: {"max_id": int, "total_count": int}."""
    r = requests.get(
        f"{_STORAGE_URL}/detections/max_id",
        headers=_HEADERS,
        timeout=_TIMEOUT,
        proxies=_NO_PROXY,
    )
    r.raise_for_status()
    return r.json()


def post_detection(payload: dict) -> dict:
    r = requests.post(
        f"{_STORAGE_URL}/detections",
        json=payload,
        headers=_HEADERS,
        timeout=_TIMEOUT,
        proxies=_NO_PROXY,
    )
    r.raise_for_status()
    return r.json()
