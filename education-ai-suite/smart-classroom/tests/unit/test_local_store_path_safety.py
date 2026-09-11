# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Containment tests for the local object store.

Object names and bucket names reach the store straight from unauthenticated HTTP
input (multipart filenames and ``file_key`` query/body fields), so every path
built from them must stay inside the bucket root.
"""

import pytest

from content_search.providers.local_storage.store import LocalStore, UnsafeObjectKeyError


@pytest.fixture
def store(tmp_path):
    s = LocalStore(tmp_path / "data", "content-search")
    s.ensure_bucket()
    return s


@pytest.fixture
def outside_file(tmp_path):
    target = tmp_path / "outside_store" / "id_rsa"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"-----BEGIN OPENSSH PRIVATE KEY-----")
    return target


UNSAFE_KEYS = [
    "../outside_store/id_rsa",
    r"..\outside_store\id_rsa",
    "runs/../../outside_store/id_rsa",
    r"runs/abc/..\..\..\Users\Public\evil.py",
    "/etc/passwd",
    r"C:\Windows\win.ini",
    r"\\attacker\share\payload.txt",
    r"\\?\C:\Windows\win.ini",
    "runs/notes.txt:evil.exe",
    "runs/notes\x00.txt",
    "runs/trailing.",
    "runs/trailing ",
    "..",
    "",
]


@pytest.mark.parametrize("key", UNSAFE_KEYS)
def test_object_path_rejects_unsafe_keys(store, key):
    with pytest.raises(UnsafeObjectKeyError):
        store._object_path(key)


@pytest.mark.parametrize("key", UNSAFE_KEYS)
def test_read_write_delete_reject_unsafe_keys(store, key):
    with pytest.raises(UnsafeObjectKeyError):
        store.put_bytes(key, b"payload")
    with pytest.raises(UnsafeObjectKeyError):
        store.get_bytes(key)
    with pytest.raises(UnsafeObjectKeyError):
        store.get_object_stream(key)
    with pytest.raises(UnsafeObjectKeyError):
        store.delete_object(key)


def test_windows_style_upload_filename_cannot_escape(store):
    """The reported attack: a multipart filename whose separators are backslashes."""
    key = LocalStore.build_raw_object_key(
        "11111111-2222-3333-4444-555555555555",
        "video",
        "default",
        r"..\..\..\..\..\..\Users\Public\evil.py",
    )
    with pytest.raises(UnsafeObjectKeyError):
        store._object_path(key)


def test_absolute_key_cannot_read_outside_store(store, outside_file):
    with pytest.raises(UnsafeObjectKeyError):
        store.get_object_stream(str(outside_file))
    assert store.object_exists(str(outside_file)) is False


def test_absolute_key_cannot_delete_outside_store(store, outside_file):
    with pytest.raises(UnsafeObjectKeyError):
        store.delete_object(str(outside_file))
    assert outside_file.exists()


@pytest.mark.parametrize("bucket", ["../..", "..", r"C:\Windows", "a/b", r"a\b", "."])
def test_bucket_name_traversal_is_rejected(store, bucket):
    with pytest.raises(UnsafeObjectKeyError):
        store._bucket_path(bucket)
    assert store.bucket_exists(bucket) is False


def test_empty_bucket_name_falls_back_to_the_default_bucket(store):
    assert store._bucket_path("") == store._bucket_path()
    assert store._bucket_path(None) == store._bucket_path()


def test_delete_prefix_rejects_traversal_and_empty_prefix(store, outside_file):
    with pytest.raises(UnsafeObjectKeyError):
        store.delete_prefix("../outside_store")
    assert outside_file.exists()
    # An empty prefix would resolve to the bucket root and wipe the whole bucket.
    with pytest.raises(UnsafeObjectKeyError):
        store.delete_prefix("")


def test_list_object_names_stays_inside_bucket(store, outside_file):
    with pytest.raises(UnsafeObjectKeyError):
        list(store.list_object_names("../outside_store"))
    # An empty prefix lists the bucket, never the data dir above it.
    store.put_bytes("runs/r1/raw/video/default/lesson1.mp4", b"video")
    assert list(store.list_object_names("")) == ["runs/r1/raw/video/default/lesson1.mp4"]


def test_normal_object_lifecycle_still_works(store, tmp_path):
    key = LocalStore.build_raw_object_key(
        "11111111-2222-3333-4444-555555555555", "video", "default", "lesson1.mp4"
    )
    assert key == "runs/11111111-2222-3333-4444-555555555555/raw/video/default/lesson1.mp4"

    store.put_bytes(key, b"video-bytes")
    assert store.object_exists(key) is True
    assert store.get_bytes(key) == b"video-bytes"

    resolved = store._object_path(key).resolve()
    assert resolved.is_relative_to(store._bucket_path().resolve())

    copied = tmp_path / "copied.mp4"
    store.get_file(key, copied)
    assert copied.read_bytes() == b"video-bytes"

    assert store.delete_object(key) is True
    assert store.delete_object(key) is False


def test_derived_keys_and_prefix_operations_still_work(store):
    derived = LocalStore.build_derived_object_key(
        "run-1", "video", "default", "chunksum-v1/summaries/chunk_0001/summary.txt"
    )
    store.put_json(derived, {"chunk": 1})
    assert store.get_json(derived) == {"chunk": 1}

    store.put_bytes("runs/run-1/raw/video/default/lesson1.mp4", b"video")
    assert sorted(store.list_object_names("runs/run-1")) == [derived, "runs/run-1/raw/video/default/lesson1.mp4"]
    # A partial (non-directory) prefix matches by name, as before.
    assert list(store.list_object_names("runs/run-1/raw/video/default/lesson")) == [
        "runs/run-1/raw/video/default/lesson1.mp4"
    ]
    assert list(store.list_object_names("runs/does-not-exist")) == []
    assert store.delete_prefix("runs/run-1") == 2
