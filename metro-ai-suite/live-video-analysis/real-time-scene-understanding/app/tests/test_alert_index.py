# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.services.alert_index.AlertIndexStore."""

from __future__ import annotations

import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from unittest.mock import MagicMock

import backend.services.alert_index as alert_index_module
from backend.services.alert_index import AlertIndexStore
from backend.services.alert_index import get_alert_index


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _record(stream_id="stream-a", frame_id="frame-1", uploaded_at=None, **extra) -> dict:
    uploaded_at = uploaded_at or _iso(datetime.now(timezone.utc))
    return {"stream_id": stream_id, "frame_id": frame_id, "uploaded_at": uploaded_at, **extra}


class TestIsRetained:
    def test_recent_record_is_retained(self):
        record = _record(uploaded_at=_iso(datetime.now(timezone.utc)))
        assert AlertIndexStore._is_retained(record) is True

    def test_expired_record_is_not_retained(self, monkeypatch):
        monkeypatch.setattr(alert_index_module.settings, "S3_RETENTION_DAYS", 10)
        old = datetime.now(timezone.utc) - timedelta(days=11)
        record = _record(uploaded_at=_iso(old))
        assert AlertIndexStore._is_retained(record) is False

    def test_missing_uploaded_at_is_not_retained(self):
        assert AlertIndexStore._is_retained({"stream_id": "s"}) is False

    def test_unparsable_timestamp_is_not_retained(self):
        assert AlertIndexStore._is_retained(_record(uploaded_at="not-a-date")) is False


class TestAdd:
    def test_add_inserts_newest_first(self):
        store = AlertIndexStore()
        older = _record(frame_id="older", uploaded_at=_iso(datetime.now(timezone.utc) - timedelta(seconds=5)))
        newer = _record(frame_id="newer", uploaded_at=_iso(datetime.now(timezone.utc)))

        store.add(older)
        store.add(newer)

        assert [r["frame_id"] for r in store._by_stream["stream-a"]] == ["newer", "older"]

    def test_add_ignores_falsy_record(self):
        store = AlertIndexStore()
        store.add(None)
        store.add({})
        assert store._by_stream == {}

    def test_add_ignores_record_missing_stream_id(self):
        store = AlertIndexStore()
        store.add({"frame_id": "x", "uploaded_at": _iso(datetime.now(timezone.utc))})
        assert store._by_stream == {}

    def test_add_ignores_expired_record(self, monkeypatch):
        monkeypatch.setattr(alert_index_module.settings, "S3_RETENTION_DAYS", 10)
        expired = _record(uploaded_at=_iso(datetime.now(timezone.utc) - timedelta(days=30)))
        store = AlertIndexStore()
        store.add(expired)
        assert store._by_stream == {}

    def test_add_trims_to_max_per_stream(self, monkeypatch):
        monkeypatch.setattr(alert_index_module.settings, "ALERT_INDEX_MAX_PER_STREAM", 2)
        store = AlertIndexStore()
        for i in range(5):
            store.add(_record(frame_id=f"frame-{i}"))
        assert len(store._by_stream["stream-a"]) == 2


class TestListCountGet:
    def _seeded_store(self, records) -> AlertIndexStore:
        store = AlertIndexStore()
        store._by_stream["stream-a"] = records
        store._hydrated.add("stream-a")  # bypass network hydration
        return store

    def test_list_paginates_newest_first(self):
        records = [_record(frame_id=f"frame-{i}") for i in range(5)]
        store = self._seeded_store(records)

        page, total = store.list("stream-a", limit=2, offset=1)

        assert total == 5
        assert [r["frame_id"] for r in page] == ["frame-1", "frame-2"]

    def test_list_filters_out_expired_entries(self, monkeypatch):
        monkeypatch.setattr(alert_index_module.settings, "S3_RETENTION_DAYS", 10)
        fresh = _record(frame_id="fresh")
        expired = _record(frame_id="expired", uploaded_at=_iso(datetime.now(timezone.utc) - timedelta(days=30)))
        store = self._seeded_store([fresh, expired])

        page, total = store.list("stream-a")

        assert total == 1
        assert [r["frame_id"] for r in page] == ["fresh"]

    def test_count_returns_number_of_retained_entries(self):
        store = self._seeded_store([_record(frame_id="a"), _record(frame_id="b")])
        assert store.count("stream-a") == 2

    def test_get_returns_matching_record(self):
        store = self._seeded_store([_record(frame_id="a"), _record(frame_id="b")])
        assert store.get("stream-a", "b")["frame_id"] == "b"

    def test_get_returns_none_when_not_found(self):
        store = self._seeded_store([_record(frame_id="a")])
        assert store.get("stream-a", "missing") is None

    def test_list_on_unseeded_stream_triggers_hydration(self):
        store = AlertIndexStore()
        store._get_client = MagicMock(side_effect=RuntimeError("should not be reached"))
        # Hydration failures are swallowed; an unreachable store degrades to empty results.
        page, total = store.list("never-seen-stream")
        assert page == []
        assert total == 0


class TestHydrate:
    def _fake_client(self, keys_and_bodies):
        client = MagicMock()
        page = {"Contents": [{"Key": key} for key, _ in keys_and_bodies]}
        paginator = MagicMock()
        paginator.paginate.return_value = [page]
        client.get_paginator.return_value = paginator

        bodies_by_key = {key: body for key, body in keys_and_bodies}

        def _get_object(Bucket, Key):  # noqa: N803 - matches boto3's call signature
            body = MagicMock()
            body.read.return_value = json.dumps(bodies_by_key[Key]).encode("utf-8")
            return {"Body": body}

        client.get_object.side_effect = _get_object
        return client

    def test_hydrate_merges_sidecars_from_s3(self):
        store = AlertIndexStore()
        record = _record(frame_id="s3-frame")
        client = self._fake_client([("stream-a/s3-frame.analysis.json", record)])
        store._get_client = MagicMock(return_value=client)

        page, total = store.list("stream-a")

        assert total == 1
        assert page[0]["frame_id"] == "s3-frame"
        assert "stream-a" in store._hydrated

    def test_hydrate_ignores_non_sidecar_keys(self):
        store = AlertIndexStore()
        client = self._fake_client([("stream-a/video.mp4", {})])
        store._get_client = MagicMock(return_value=client)

        _page, total = store.list("stream-a")

        assert total == 0

    def test_hydrate_only_runs_once_per_stream(self):
        store = AlertIndexStore()
        client = self._fake_client([])
        get_client = MagicMock(return_value=client)
        store._get_client = get_client

        store.list("stream-a")
        store.list("stream-a")

        assert get_client.call_count == 1

    def test_hydrate_swallows_client_errors(self):
        store = AlertIndexStore()
        store._get_client = MagicMock(side_effect=RuntimeError("s3 unreachable"))

        page, total = store.list("stream-a")

        assert page == []
        assert total == 0
        # Not marked hydrated, so a later attempt can retry.
        assert "stream-a" not in store._hydrated


class TestSingleton:
    def test_get_alert_index_returns_same_instance(self, monkeypatch):
        monkeypatch.setattr(alert_index_module, "_index", None)
        first = get_alert_index()
        second = get_alert_index()
        assert first is second
