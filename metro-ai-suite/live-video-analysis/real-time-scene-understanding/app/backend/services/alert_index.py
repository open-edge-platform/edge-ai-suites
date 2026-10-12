# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""In-memory, per-stream audit index of uploaded deep-analysis alerts.

The index follows the configured S3 lifecycle retention period so expired
segment references are hidden even before the object store removes them. It is
not persisted: on first access for a given stream, it lazily hydrates itself by
listing that stream's sidecars from SeaweedFS, then stays current as new alerts
are uploaded via `add()`.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import Optional

import boto3
from botocore.config import Config

from ..config import settings

logger = logging.getLogger(__name__)


class AlertIndexStore:
    """Thread-safe, per-stream newest-first list of alert records."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_stream: dict[str, list[dict[str, Any]]] = {}
        self._hydrated: set[str] = set()
        self._client = None

    def _get_client(self):
        """Initialize a SeaweedFS S3 client for listing and reading sidecars."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.SEAWEEDFS_ENDPOINT_URL,
                aws_access_key_id=settings.SEAWEEDFS_ACCESS_KEY,
                aws_secret_access_key=settings.SEAWEEDFS_SECRET_KEY,
                use_ssl=settings.SEAWEEDFS_USE_SSL,
                verify=settings.SEAWEEDFS_VERIFY_SSL,
            )
        return self._client

    @staticmethod
    def _is_retained(record: dict[str, Any]) -> bool:
        uploaded_at = record.get("uploaded_at")
        if not uploaded_at:
            return False
        try:
            timestamp = datetime.fromisoformat(str(uploaded_at).replace("Z", "+00:00"))
        except ValueError:
            return False
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.S3_RETENTION_DAYS)
        return timestamp >= cutoff

    def _retained_entries(self, stream_id: str) -> list[dict[str, Any]]:
        entries = self._by_stream.get(stream_id, [])
        retained = [record for record in entries if self._is_retained(record)]
        self._by_stream[stream_id] = retained
        return retained

    def add(self, record: Optional[dict[str, Any]]) -> None:
        """Insert a freshly uploaded alert record at the front of its stream's list."""
        if not record:
            return
        stream_id = record.get("stream_id")
        if not stream_id or not self._is_retained(record):
            return
        with self._lock:
            entries = self._by_stream.setdefault(stream_id, [])
            entries.insert(0, record)
            del entries[settings.ALERT_INDEX_MAX_PER_STREAM :]

    def _hydrate(self, stream_id: str) -> None:
        """Backfill this stream's history from SeaweedFS, once."""
        with self._lock:
            if stream_id in self._hydrated:
                return

        records: list[dict[str, Any]] = []
        try:
            client = self._get_client()
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=settings.SEAWEEDFS_BUCKET, Prefix=f"{stream_id}/"):
                for obj in page.get("Contents", []):
                    key = obj.get("Key", "")
                    if not key.endswith(".analysis.json"):
                        continue
                    try:
                        response = client.get_object(Bucket=settings.SEAWEEDFS_BUCKET, Key=key)
                        records.append(json.loads(response["Body"].read().decode("utf-8")))
                    except Exception as exc:  # noqa: BLE001 - skip unreadable sidecars, don't fail the whole listing
                        logger.warning("[%s] failed to read alert sidecar %s: %s", stream_id, key, exc)
        except Exception as exc:  # noqa: BLE001 - keep the index usable even if SeaweedFS is unreachable
            logger.warning("[%s] failed to hydrate alert index from SeaweedFS: %s", stream_id, exc)
            return

        records.sort(key=lambda r: r.get("uploaded_at", ""), reverse=True)

        with self._lock:
            if stream_id not in self._hydrated:
                existing = self._by_stream.get(stream_id, [])
                known_frame_ids = {r.get("frame_id") for r in existing}
                merged = existing + [
                    r
                    for r in records
                    if r.get("frame_id") not in known_frame_ids and self._is_retained(r)
                ]
                merged.sort(key=lambda r: r.get("uploaded_at", ""), reverse=True)
                self._by_stream[stream_id] = merged[: settings.ALERT_INDEX_MAX_PER_STREAM]
                self._hydrated.add(stream_id)

    def list(self, stream_id: str, limit: int = 20, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        """Return a page of alerts (newest first) and the total known count."""
        self._hydrate(stream_id)
        with self._lock:
            entries = self._retained_entries(stream_id)
            total = len(entries)
            page = entries[offset : offset + limit]
        return page, total

    def count(self, stream_id: str) -> int:
        """Total known alerts for this stream (hydrates from SeaweedFS once per stream)."""
        self._hydrate(stream_id)
        with self._lock:
            return len(self._retained_entries(stream_id))

    def get(self, stream_id: str, frame_id: str) -> Optional[dict[str, Any]]:
        self._hydrate(stream_id)
        with self._lock:
            for record in self._retained_entries(stream_id):
                if record.get("frame_id") == frame_id:
                    return record
        return None


_index: Optional[AlertIndexStore] = None
_index_lock = threading.Lock()


def get_alert_index() -> AlertIndexStore:
    global _index
    if _index is None:
        with _index_lock:
            if _index is None:
                _index = AlertIndexStore()
    return _index
