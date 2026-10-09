# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for static helpers in backend.services.object_storage.SeaweedFSStorage.

These are exercised via the class directly (no instantiation) since
SeaweedFSStorage.__init__ creates a real boto3 client and touches the bucket.
"""

from __future__ import annotations

import tempfile
import threading
import uuid

import pytest
from backend.services import object_storage as object_storage_module
from backend.services.object_storage import SeaweedFSStorage


class TestBackoffDelay:
    def test_scales_linearly_with_attempt(self, monkeypatch):
        monkeypatch.setattr(object_storage_module.settings, "SEAWEEDFS_RETRY_DELAY_SECONDS", 1.0)
        monkeypatch.setattr(object_storage_module.settings, "SEAWEEDFS_MAX_RETRY_DELAY_SECONDS", 10.0)

        assert SeaweedFSStorage._backoff_delay(1) == 1.0
        assert SeaweedFSStorage._backoff_delay(3) == 3.0

    def test_caps_at_configured_maximum(self, monkeypatch):
        monkeypatch.setattr(object_storage_module.settings, "SEAWEEDFS_RETRY_DELAY_SECONDS", 1.0)
        monkeypatch.setattr(object_storage_module.settings, "SEAWEEDFS_MAX_RETRY_DELAY_SECONDS", 2.0)

        assert SeaweedFSStorage._backoff_delay(10) == 2.0


class TestToS3MetadataValue:
    def test_plain_string_is_unchanged(self):
        assert SeaweedFSStorage._to_s3_metadata_value("hello world") == "hello world"

    def test_non_string_is_stringified(self):
        assert SeaweedFSStorage._to_s3_metadata_value(42) == "42"

    @pytest.mark.parametrize("bad_char", ["\n", "\r", "\t"])
    def test_normalizes_whitespace_control_characters(self, bad_char):
        value = f"line one{bad_char}line two"
        assert SeaweedFSStorage._to_s3_metadata_value(value) == "line one line two"


class TestIsBucketMissingError:
    def test_true_for_404_status_code(self):
        exc = Exception("boom")
        exc.response = {"ResponseMetadata": {"HTTPStatusCode": 404}, "Error": {}}
        assert SeaweedFSStorage._is_bucket_missing_error(exc) is True

    @pytest.mark.parametrize("code", ["404", "NoSuchBucket", "NotFound"])
    def test_true_for_known_error_codes(self, code):
        exc = Exception("boom")
        exc.response = {"ResponseMetadata": {"HTTPStatusCode": 400}, "Error": {"Code": code}}
        assert SeaweedFSStorage._is_bucket_missing_error(exc) is True

    def test_false_when_no_response_attribute(self):
        assert SeaweedFSStorage._is_bucket_missing_error(Exception("boom")) is False

    def test_false_for_unrelated_error(self):
        exc = Exception("boom")
        exc.response = {"ResponseMetadata": {"HTTPStatusCode": 500}, "Error": {"Code": "InternalError"}}
        assert SeaweedFSStorage._is_bucket_missing_error(exc) is False


import uuid


class TestBuildObjectKeys:
    def test_builds_expected_storage_keys(self):
        frame_id = uuid.UUID("12345678-1234-4234-8234-123456789abc")
        storage = object.__new__(SeaweedFSStorage)

        keys = storage._build_object_keys("stream-42", "segments/segment_0012.mp4", frame_id)

        assert keys == (
            "stream-42/segment_0012-12345678-1234-4234-8234-123456789abc.mp4",
            "stream-42/segment_0012-12345678-1234-4234-8234-123456789abc.analysis.json",
            "stream-42/segment_0012-12345678-1234-4234-8234-123456789abc.thumb.jpg",
        )

    def test_uses_segment_stem_as_prefix(self):
        frame_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        storage = object.__new__(SeaweedFSStorage)

        video_key, _, _ = storage._build_object_keys("alpha", "segments/clip-010.mp4", frame_id)

        assert video_key.startswith("alpha/clip-010-")
        assert video_key.endswith(".mp4")


class TestStorageRetryAndBucketSetup:
    def test_run_with_retries_retries_and_succeeds(self):
        storage = object.__new__(SeaweedFSStorage)
        storage._backoff_delay = lambda attempt: 0.0
        calls = {"count": 0}

        def flaky():
            calls["count"] += 1
            if calls["count"] < 2:
                raise RuntimeError("transient")
            return "ok"

        assert storage._run_with_retries(flaky, "upload_video") == "ok"
        assert calls["count"] == 2

    def test_ensure_bucket_creates_when_missing(self, monkeypatch):
        storage = object.__new__(SeaweedFSStorage)
        storage._bucket_ready = False
        storage._lock = threading.Lock()
        storage._ensure_lifecycle = lambda: None
        storage._run_with_retries = lambda fn, operation_name: fn()

        client = type(
            "Client",
            (),
            {
                "head_bucket": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("missing")),
                "create_bucket": lambda self, **kwargs: "created",
            },
        )()
        storage._client = client

        class _Missing(Exception):
            response = {"ResponseMetadata": {"HTTPStatusCode": 404}, "Error": {}}

        def head_bucket(**kwargs):
            raise _Missing()

        storage._client.head_bucket = head_bucket
        storage._client.create_bucket = lambda **kwargs: "created"
        storage._ensure_bucket()
        assert storage._bucket_ready is True

    def test_upload_segment_and_metadata_returns_payload(self, monkeypatch, tmp_path):
        storage = object.__new__(SeaweedFSStorage)
        storage._client = type("Client", (), {})()
        storage._upload_executor = __import__("concurrent.futures").futures.ThreadPoolExecutor(max_workers=2)
        storage._lock = threading.Lock()
        monkeypatch.setattr(object_storage_module.settings, "SEAWEEDFS_BUCKET", "demo-bucket")

        segment_path = tmp_path / "segment_0001.mp4"
        segment_path.write_bytes(b"video")
        frame_id = uuid.uuid4()

        calls = []

        def upload_file(**kwargs):
            calls.append(("upload_file", kwargs["Key"], kwargs["ExtraArgs"]))

        def put_object(**kwargs):
            calls.append(("put_object", kwargs["Key"], kwargs["ContentType"]))

        storage._client.upload_file = upload_file
        storage._client.put_object = put_object
        storage._run_with_retries = lambda fn, name: fn()

        payload = storage.upload_segment_and_metadata(
            stream_id="stream-1",
            segment_path=str(segment_path),
            frame_id=frame_id,
            description="Visible fire.",
            metrics={"frames_sampled": 5.0},
            deep_model="model",
            deep_device="cpu",
        )

        assert payload is not None
        assert payload["stream_id"] == "stream-1"
        assert payload["description"] == "Visible fire."
        assert len(calls) >= 2
        storage._upload_executor.shutdown(wait=True)
