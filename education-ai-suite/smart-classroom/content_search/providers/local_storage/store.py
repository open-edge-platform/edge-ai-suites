# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
import pathlib
import shutil
import os
from io import BytesIO
from typing import Any, BinaryIO, Iterator, Optional, Union


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
        return self._data_dir / (bucket or self._bucket)

    def _object_path(self, object_name: str, bucket: Optional[str] = None) -> pathlib.Path:
        return self._bucket_path(bucket) / object_name

    # ---- bucket operations ------------------------------------------------

    def ensure_bucket(self) -> None:
        self._bucket_path().mkdir(parents=True, exist_ok=True)

    def bucket_exists(self, bucket_name: str) -> bool:
        return self._bucket_path(bucket_name).is_dir()

    def list_buckets(self) -> list[str]:
        if not self._data_dir.exists():
            return []
        return [p.name for p in self._data_dir.iterdir() if p.is_dir()]

    # ---- object existence -------------------------------------------------

    def object_exists(self, object_name: str) -> bool:
        return self._object_path(object_name).is_file()

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
        search_dir = base / prefix if (base / prefix).is_dir() else (base / prefix).parent
        if not search_dir.exists():
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
        target = base / prefix
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

    # ---- key builders (unchanged) -----------------------------------------

    @staticmethod
    def build_raw_object_key(run_id: str, asset_type: str, asset_id: str, filename: str) -> str:
        return (
            pathlib.PurePosixPath("runs") / str(run_id) / "raw"
            / str(asset_type) / str(asset_id) / pathlib.PurePosixPath(str(filename)).name
        ).as_posix()

    @staticmethod
    def build_derived_object_key(run_id: str, asset_type: str, asset_id: str,
                                  relative_path: Union[str, pathlib.PurePosixPath]) -> str:
        rel = pathlib.PurePosixPath(str(relative_path))
        if rel.is_absolute():
            rel = pathlib.PurePosixPath(*rel.parts[1:])
        return (
            pathlib.PurePosixPath("runs") / str(run_id) / "derived"
            / str(asset_type) / str(asset_id) / rel
        ).as_posix()
