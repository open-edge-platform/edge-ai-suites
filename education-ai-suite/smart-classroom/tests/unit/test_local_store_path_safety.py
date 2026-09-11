# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Containment tests for the local object store.

Object names and bucket names reach the store straight from unauthenticated HTTP
input (multipart filenames and ``file_key`` query/body fields), so every path
built from them must stay inside the bucket root.
"""

import pytest

from content_search.providers.local_storage.store import (
    LocalStore,
    UnsafeObjectKeyError,
    safe_filename,
)
from content_search.utils.file_validator import FileValidator


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


def test_windows_style_upload_filename_is_reduced_to_a_basename(store):
    """The reported attack: a multipart filename whose separators are backslashes."""
    key = LocalStore.build_raw_object_key(
        "11111111-2222-3333-4444-555555555555",
        "video",
        "default",
        r"..\..\..\..\..\..\Users\Public\evil.py",
    )
    assert key == "runs/11111111-2222-3333-4444-555555555555/raw/video/default/evil.py"
    assert store._object_path(key).resolve().is_relative_to(store._bucket_path().resolve())


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("lesson1.mp4", "lesson1.mp4"),
        ("第一课 板书.pdf", "第一课 板书.pdf"),
        (r"..\..\..\Users\Public\evil.py", "evil.py"),
        ("../../../etc/passwd", "passwd"),
        (r"C:\Windows\win.ini", "win.ini"),
        ("notes.txt:evil.exe", "notes.txt_evil.exe"),
        ("bad\x00name.pdf", "bad_name.pdf"),
        ("trailing.pdf...", "trailing.pdf"),
        ("trailing.pdf   ", "trailing.pdf"),
        ("CON.txt", "_CON.txt"),
        ("con", "_con"),
        ("LPT1.pdf", "_LPT1.pdf"),
        ("..", "unnamed"),
        (".", "unnamed"),
        ("", "unnamed"),
        (None, "unnamed"),
        ("/", "unnamed"),
        ("a<b>c|d?e*f.pdf", "a_b_c_d_e_f.pdf"),
    ],
)
def test_safe_filename(filename, expected):
    assert safe_filename(filename) == expected


def test_safe_filename_truncates_but_keeps_the_extension():
    result = safe_filename("x" * 500 + ".mp4")
    assert len(result) <= 180
    assert result.endswith(".mp4")


def test_safe_filename_output_is_always_a_valid_key_segment(store):
    for candidate in [r"..\..\evil.py", "notes.txt:evil.exe", "CON.txt", "..", "a|b.pdf"]:
        key = LocalStore.build_raw_object_key("run-1", "video", "default", candidate)
        assert store._object_path(key).resolve().is_relative_to(store._bucket_path().resolve())


@pytest.mark.parametrize("run_id", ["..", "../..", r"..\..\..\Users\Public", "a/b", "", "."])
def test_run_path_rejects_traversal(store, run_id):
    """Callers rmtree this directory, so run_id must never point outside the bucket."""
    with pytest.raises(UnsafeObjectKeyError):
        store.run_path(run_id)


def test_run_path_resolves_inside_the_bucket(store):
    run_dir = store.run_path("11111111-2222-3333-4444-555555555555")
    assert run_dir == store._bucket_path() / "runs" / "11111111-2222-3333-4444-555555555555"
    assert run_dir.resolve().is_relative_to(store._bucket_path().resolve())


@pytest.mark.parametrize(
    "bad",
    ["../../../etc/passwd", r"..\..\Users\Public\x.txt", "/etc/passwd", r"C:\Windows\win.ini", ".."],
)
def test_build_keys_reject_traversal_in_run_id_and_relative_path(bad):
    with pytest.raises(UnsafeObjectKeyError):
        LocalStore.build_derived_object_key("run-1", "video", "default", bad)
    with pytest.raises(UnsafeObjectKeyError):
        LocalStore.build_raw_object_key(bad, "video", "default", "lesson1.mp4")
    with pytest.raises(UnsafeObjectKeyError):
        LocalStore.build_raw_object_key("run-1", bad, "default", "lesson1.mp4")
    with pytest.raises(UnsafeObjectKeyError):
        LocalStore.build_raw_object_key("run-1", "video", bad, "lesson1.mp4")


@pytest.mark.parametrize("ext", [".py", ".bat", ".cmd", ".ps1", ".exe", ".dll", ".lnk", ".js", ".zip", ""])
def test_validator_rejects_types_outside_the_allowlist(ext):
    ok, error = FileValidator.validate_basic_file(f"payload{ext}", None, 10)
    assert ok is False
    assert "Unsupported file type" in error


@pytest.mark.parametrize(
    "filename", ["lesson1.mp4", "notes.pdf", "notes.txt", "slides.pptx", "page.html", "readme.md",
                 "data.xml", "photo.jpg", "clip.mkv"]
)
def test_validator_still_accepts_supported_types(filename):
    ok, error = FileValidator.validate_basic_file(filename, None, 10)
    assert ok is True, error


def test_validator_allowlist_covers_everything_the_ui_offers():
    """The UI file picker must not offer types the backend rejects."""
    ui_accepts = {".mp4", ".jpg", ".png", ".jpeg", ".txt", ".pdf", ".docx", ".doc",
                  ".pptx", ".ppt", ".xlsx", ".xls", ".html", ".htm", ".xml", ".md"}
    assert ui_accepts <= FileValidator.ALLOWED_EXTENSIONS


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
