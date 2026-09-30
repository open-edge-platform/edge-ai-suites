# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import pathlib
import shutil
import os
from typing import Any, BinaryIO, Iterator, Optional, Union


class UnsafeObjectKeyError(ValueError):
    """Raised when a bucket or object name would resolve outside the storage root."""


def _has_control_chars(value: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def _validate_segment(segment: str, *, kind: str) -> str:
    """Validate a single path component (bucket name or one object-key segment)."""
    if not segment or segment in (".", ".."):
        raise UnsafeObjectKeyError(f"Invalid {kind}: {segment!r}")
    if _has_control_chars(segment):
        raise UnsafeObjectKeyError(f"Invalid {kind}: control characters are not allowed")
    if "/" in segment or "\\" in segment:
        raise UnsafeObjectKeyError(f"Invalid {kind}: path separators are not allowed: {segment!r}")
    # A colon would introduce a drive reference ("C:") or an NTFS alternate data
    # stream ("file.txt:evil.exe"), both of which escape the intended target.
    if ":" in segment:
        raise UnsafeObjectKeyError(f"Invalid {kind}: {segment!r}")
    # Windows silently strips trailing dots and spaces, so "foo." and "foo" would
    # name the same entry while comparing as different keys.
    if segment != segment.rstrip(". "):
        raise UnsafeObjectKeyError(f"Invalid {kind}: trailing dots or spaces are not allowed: {segment!r}")
    return segment


def _normalize_object_name(object_name: Any, *, allow_empty: bool = False) -> str:
    """Return a validated bucket-relative POSIX key, or raise ``UnsafeObjectKeyError``.

    Backslashes are treated as separators because this service also runs on
    Windows, where ``..\\..\\evil.py`` is a traversal rather than a plain filename.
    """
    if object_name is None:
        raise UnsafeObjectKeyError("Object name is required")
    raw = str(object_name)
    if not raw:
        if allow_empty:
            return ""
        raise UnsafeObjectKeyError("Object name must not be empty")
    if _has_control_chars(raw):
        raise UnsafeObjectKeyError("Invalid object name: control characters are not allowed")

    normalized = raw.replace("\\", "/")
    if normalized.startswith("/"):
        raise UnsafeObjectKeyError(f"Absolute object names are not allowed: {raw!r}")

    segments = [
        _validate_segment(segment, kind="object name segment")
        for segment in normalized.split("/")
        if segment not in ("", ".")
    ]
    if not segments:
        if allow_empty:
            return ""
        raise UnsafeObjectKeyError(f"Object name must not be empty: {raw!r}")
    return "/".join(segments)


def _is_within(base: pathlib.Path, candidate: pathlib.Path) -> bool:
    """True if ``candidate`` resolves to ``base`` or somewhere beneath it."""
    base_resolved = base.resolve()
    candidate_resolved = candidate.resolve()
    return candidate_resolved == base_resolved or candidate_resolved.is_relative_to(base_resolved)


# Names Windows resolves to devices rather than files, with or without a suffix.
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

_ILLEGAL_FILENAME_CHARS = '<>:"/\\|?*'

# Leaves room for the "runs/<uuid>/raw/<type>/<id>/" prefix inside Windows' path limit.
_MAX_FILENAME_LENGTH = 180


def safe_filename(filename: Any, *, fallback: str = "unnamed") -> str:
    """Reduce a client-supplied filename to one safe path component.

    The basename is taken for both separator conventions because an upload may be
    sent by any client, and this service runs on Windows where ``\\`` separates
    directories. The extension is preserved: downstream validation and content-type
    routing key off it.
    """
    raw = "" if filename is None else str(filename)
    base = raw.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(
        "_" if ch in _ILLEGAL_FILENAME_CHARS or ord(ch) < 32 or ord(ch) == 127 else ch
        for ch in base
    ).rstrip(". ")
    if cleaned in ("", ".", ".."):
        return fallback

    if cleaned.partition(".")[0].upper() in _WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"

    if len(cleaned) > _MAX_FILENAME_LENGTH:
        stem, dot, ext = cleaned.rpartition(".")
        if not dot or len(ext) > 20:
            stem, ext = cleaned, ""
        stem = stem[: max(1, _MAX_FILENAME_LENGTH - len(ext) - 1)].rstrip(". ")
        if not stem:
            return fallback
        cleaned = f"{stem}.{ext}" if ext else stem
    return cleaned


class LocalStore:
    """Local-filesystem object store.

    Objects are stored under ``<data_dir>/<bucket>/<object_name>``.
    """

    def __init__(self, data_dir: Union[str, pathlib.Path], bucket_name: str):
        self._data_dir = pathlib.Path(data_dir).resolve()
        self._bucket = bucket_name

    @classmethod
    def from_config(cls) -> "LocalStore":
        data_dir = os.environ["STORAGE_DATA_DIR"]
        bucket = os.environ["STORAGE_BUCKET"]
        store = cls(data_dir, bucket)
        store.ensure_bucket()
        return store

    @property
    def bucket(self) -> str:
        return self._bucket

    def _bucket_path(self, bucket: Optional[str] = None) -> pathlib.Path:
        name = _validate_segment(str(bucket or self._bucket), kind="bucket name")
        return self._data_dir / name

    def _contained_path(self, base: pathlib.Path, relative: str) -> pathlib.Path:
        """Join ``relative`` onto ``base`` and assert the result stays inside ``base``.

        The resolved comparison is the actual containment guarantee: it also covers
        symlinks and platform-specific normalisation that plain string checks miss.
        """
        candidate = base / relative if relative else base
        if not _is_within(base, candidate):
            raise UnsafeObjectKeyError(f"Object name escapes the storage root: {relative!r}")
        return candidate

    def _object_path(self, object_name: str, bucket: Optional[str] = None) -> pathlib.Path:
        key = _normalize_object_name(object_name)
        return self._contained_path(self._bucket_path(bucket), key)

    # ---- bucket operations ------------------------------------------------

    def ensure_bucket(self) -> None:
        self._bucket_path().mkdir(parents=True, exist_ok=True)

    def bucket_exists(self, bucket_name: str) -> bool:
        try:
            return self._bucket_path(bucket_name).is_dir()
        except UnsafeObjectKeyError:
            return False

    def list_buckets(self) -> list[str]:
        if not self._data_dir.exists():
            return []
        return [p.name for p in self._data_dir.iterdir() if p.is_dir()]

    # ---- object existence -------------------------------------------------

    def object_exists(self, object_name: str) -> bool:
        try:
            return self._object_path(object_name).is_file()
        except UnsafeObjectKeyError:
            return False

    # ---- read operations --------------------------------------------------

    def get_bytes(self, object_name: str) -> bytes:
        p = self._object_path(object_name)
        if not p.is_file():
            raise RuntimeError(f"Object not found: {self._bucket}/{object_name}")
        return p.read_bytes()

    def get_file(self, object_name: str, file_path: Union[str, pathlib.Path]) -> None:
        """Download an object to a local file path."""
        src = self._object_path(object_name)
        if not src.is_file():
            raise RuntimeError(f"Object not found: {self._bucket}/{object_name}")
        dst = pathlib.Path(file_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))

    def get_json(self, object_name: str, *, encoding: str = "utf-8") -> Any:
        return json.loads(self.get_bytes(object_name).decode(encoding))

    def get_object_stream(self, object_name: str) -> BinaryIO:
        """Return an open file handle for streaming reads."""
        p = self._object_path(object_name)
        if not p.is_file():
            raise RuntimeError(f"Object not found: {self._bucket}/{object_name}")
        return open(p, "rb")

    # ---- write operations -------------------------------------------------

    def put_bytes(self, object_name: str, data: bytes, *, content_type: str = "application/octet-stream") -> None:
        p = self._object_path(object_name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def _put_stream(self, object_name: str, data: BinaryIO, *, length: int = 0,
                    content_type: str = "application/octet-stream") -> None:
        p = self._object_path(object_name)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            data.seek(0)
        except Exception:
            pass
        with open(p, "wb") as f:
            shutil.copyfileobj(data, f)

    def put_file(self, object_name: str, file_path: Union[str, pathlib.Path], *,
                 content_type: Optional[str] = None) -> None:
        """Upload a local file to the store."""
        src = pathlib.Path(file_path)
        if not src.exists() or not src.is_file():
            raise RuntimeError(f"File not found: {src}")
        dst = self._object_path(object_name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))

    def put_json(self, object_name: str, payload: Any, *, encoding: str = "utf-8",
                 ensure_ascii: bool = False, indent: int = 2) -> None:
        raw = json.dumps(payload, ensure_ascii=ensure_ascii, indent=indent).encode(encoding)
        self.put_bytes(object_name, raw, content_type="application/json")

    # ---- list / delete ----------------------------------------------------

    def list_object_names(self, prefix: str, *, recursive: bool = True) -> Iterator[str]:
        base = self._bucket_path()
        prefix = _normalize_object_name(prefix, allow_empty=True)
        target = self._contained_path(base, prefix)
        search_dir = target if target.is_dir() else target.parent
        # A partial prefix walks up to the parent directory, which must not be
        # allowed to step above the bucket root.
        if not search_dir.exists() or not _is_within(base, search_dir):
            return
        if recursive:
            for p in sorted(search_dir.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(base).as_posix()
                    if rel.startswith(prefix):
                        yield rel
        else:
            for p in sorted(search_dir.iterdir()):
                if p.is_file():
                    rel = p.relative_to(base).as_posix()
                    if rel.startswith(prefix):
                        yield rel

    def delete_object(self, object_name: str, *, bucket_name: Optional[str] = None,
                      missing_ok: bool = True) -> bool:
        p = self._object_path(object_name, bucket=bucket_name)
        if not p.is_file():
            if missing_ok:
                return False
            raise RuntimeError(f"Object not found: {bucket_name or self._bucket}/{object_name}")
        p.unlink()
        return True

    def delete_prefix(self, prefix: str, *, bucket_name: Optional[str] = None,
                      recursive: bool = True) -> int:
        base = self._bucket_path(bucket_name)
        # An empty prefix would resolve to the bucket root and wipe the whole bucket.
        prefix = _normalize_object_name(prefix)
        target = self._contained_path(base, prefix)
        if target.is_dir():
            count = sum(1 for _ in target.rglob("*") if _.is_file())
            shutil.rmtree(str(target))
            return count
        # prefix may be a partial path — delete matching files
        count = 0
        for name in list(self.list_object_names(prefix, recursive=recursive)):
            self.delete_object(name, bucket_name=bucket_name)
            count += 1
        return count

    # ---- key builders -----------------------------------------------------

    def run_path(self, run_id: str, *, bucket_name: Optional[str] = None) -> pathlib.Path:
        """Return the directory holding every object of one run.

        Callers delete this directory recursively, so the ``run_id`` must never be
        able to point outside the bucket; building the path here keeps that check
        in the same place as every other path this store hands out.
        """
        run_id = _validate_segment(str(run_id), kind="run id")
        return self._object_path(f"runs/{run_id}", bucket=bucket_name)

    @staticmethod
    def build_raw_object_key(run_id: str, asset_type: str, asset_id: str, filename: str) -> str:
        return "/".join([
            "runs",
            _validate_segment(str(run_id), kind="run id"),
            "raw",
            _validate_segment(str(asset_type), kind="asset type"),
            _validate_segment(str(asset_id), kind="asset id"),
            safe_filename(filename),
        ])

    @staticmethod
    def build_derived_object_key(run_id: str, asset_type: str, asset_id: str,
                                  relative_path: Union[str, pathlib.PurePosixPath]) -> str:
        # Validates every segment and rejects "..", absolute and Windows-style paths.
        rel = _normalize_object_name(relative_path)
        return "/".join([
            "runs",
            _validate_segment(str(run_id), kind="run id"),
            "derived",
            _validate_segment(str(asset_type), kind="asset type"),
            _validate_segment(str(asset_id), kind="asset id"),
            rel,
        ])
