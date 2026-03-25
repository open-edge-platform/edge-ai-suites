# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import pathlib
import shutil
from io import BytesIO
from datetime import datetime, timezone
from typing import Any, BinaryIO, Iterator, Optional, Union

from minio import Minio
from minio.error import S3Error

from utils.config_loader import config


class MinioStore:
    """Standard, service-friendly MinIO interface."""

    def __init__(self, client: Minio, bucket_name: str):
        self._client = client
        self._bucket = bucket_name

    @classmethod
    def from_config(cls) -> "MinioStore":
        """Create a MinioStore from the content_search.minio section of config.yaml."""
        cfg = config.content_search.minio

        server = cfg.server
        access_key = cfg.root_user
        secret_key = cfg.root_password
        secure = bool(getattr(cfg, "secure", False))
        bucket = cfg.bucket

        if not server:
            raise RuntimeError("Missing content_search.minio.server in config.yaml")
        if not access_key or not secret_key:
            raise RuntimeError("Missing content_search.minio.root_user/root_password in config.yaml")
        if not bucket:
            raise RuntimeError("Missing content_search.minio.bucket in config.yaml")

        client = Minio(str(server), str(access_key), str(secret_key), secure=secure)
        return cls(client, str(bucket))

    @property
    def client(self) -> Minio:
        return self._client

    @property
    def bucket(self) -> str:
        return self._bucket

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def list_buckets(self) -> list[str]:
        buckets = self._client.list_buckets()
        return [getattr(b, "name", "") for b in buckets if getattr(b, "name", "")]

    def object_exists(self, object_name: str) -> bool:
        try:
            self._client.stat_object(self._bucket, object_name)
            return True
        except S3Error as err:
            if getattr(err, "code", None) in {"NoSuchKey", "NoSuchObject"}:
                return False
            return False

    def get_bytes(self, object_name: str) -> bytes:
        try:
            resp = self._client.get_object(self._bucket, object_name)
            try:
                return resp.read()
            finally:
                resp.close()
                resp.release_conn()
        except S3Error as err:
            raise RuntimeError(f"Failed to read {self._bucket}/{object_name}: {err}") from err

    def put_bytes(self, object_name: str, data: bytes, *, content_type: str = "application/octet-stream") -> None:
        self._put_stream(object_name, BytesIO(data), length=len(data), content_type=content_type)

    def _put_stream(self, object_name: str, data: BinaryIO, *, length: int = 0,
                    content_type: str = "application/octet-stream") -> None:
        if not length:
            try:
                getbuffer = getattr(data, "getbuffer", None)
                if callable(getbuffer):
                    length = getbuffer().nbytes
                else:
                    cur = data.tell()
                    data.seek(0, 2)
                    end = data.tell()
                    data.seek(cur)
                    length = end - cur
            except Exception:
                raise RuntimeError("Stream length is required for upload")
        try:
            data.seek(0)
        except Exception:
            pass
        try:
            self._client.put_object(bucket_name=self._bucket, object_name=object_name,
                                    data=data, length=int(length), content_type=content_type)
        except S3Error as err:
            raise RuntimeError(f"Error occurred during saving to bucket: {err}") from err

    def put_file(self, object_name: str, file_path: Union[str, pathlib.Path], *,
                 content_type: Optional[str] = None) -> None:
        """Upload a local file to MinIO.
        Suitable for large originals (mp4, pdf, pptx, etc.) and derived artifacts.
        """
        p = pathlib.Path(file_path)
        if not p.exists() or not p.is_file():
            raise RuntimeError(f"File not found: {p}")
        with p.open("rb") as f:
            self._put_stream(object_name, f, length=p.stat().st_size,
                             content_type=content_type or "application/octet-stream")

    def get_file(self, object_name: str, file_path: Union[str, pathlib.Path]) -> None:
        """Download an object from MinIO to a local file path."""
        p = pathlib.Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            resp = self._client.get_object(self._bucket, object_name)
            try:
                with p.open("wb") as f:
                    shutil.copyfileobj(resp, f)
            finally:
                resp.close()
                resp.release_conn()
        except S3Error as err:
            raise RuntimeError(f"Failed to download {self._bucket}/{object_name}: {err}") from err

    def get_json(self, object_name: str, *, encoding: str = "utf-8") -> Any:
        import json
        return json.loads(self.get_bytes(object_name).decode(encoding))

    def put_json(self, object_name: str, payload: Any, *, encoding: str = "utf-8",
                 ensure_ascii: bool = False, indent: int = 2) -> None:
        import json
        raw = json.dumps(payload, ensure_ascii=ensure_ascii, indent=indent).encode(encoding)
        self.put_bytes(object_name, raw, content_type="application/json")

    def list_object_names(self, prefix: str, *, recursive: bool = True) -> Iterator[str]:
        for obj in self._client.list_objects(self._bucket, prefix=prefix, recursive=recursive):
            yield getattr(obj, "object_name", "")

    def delete_object(self, object_name: str, *, bucket_name: Optional[str] = None,
                      missing_ok: bool = True) -> bool:
        """Delete a single object.

        This supports user-provided bucket/object inputs by allowing a bucket override.

        Args:
            object_name: object key in the bucket.
            bucket_name: optional override; defaults to this store's bucket.
            missing_ok: if True, treat missing object as a non-error.

        Returns:
            True if deletion succeeded.
            False if missing_ok=True and the object was not found.
        """
        bkt = str(bucket_name) if bucket_name else self._bucket
        try:
            self._client.remove_object(bkt, object_name)
            return True
        except S3Error as err:
            if missing_ok and getattr(err, "code", None) in {"NoSuchKey", "NoSuchObject"}:
                return False
            raise RuntimeError(f"Failed to delete {bkt}/{object_name}: {err}") from err

    def delete_prefix(self, prefix: str, *, bucket_name: Optional[str] = None,
                      recursive: bool = True) -> int:
        """Delete all objects under a prefix.

        This supports user-provided bucket/prefix inputs by allowing a bucket override.

        Returns:
            Number of keys scheduled for deletion (best-effort count).
        """

        from minio.deleteobjects import DeleteObject
        bkt = str(bucket_name) if bucket_name else self._bucket
        names = [getattr(obj, "object_name", "")
                 for obj in self._client.list_objects(bkt, prefix=prefix, recursive=recursive)
                 if getattr(obj, "object_name", "")]
        if not names:
            return 0
        errors = self._client.remove_objects(bkt, (DeleteObject(n) for n in names))
        first_err = next(errors, None)
        if first_err is not None:
            raise RuntimeError(f"Failed to delete under {bkt}/{prefix}: {first_err}")
        return len(names)

    @staticmethod
    def build_raw_object_key(run_id: str, asset_type: str, asset_id: str, filename: str) -> str:
        """Build a run/batch-scoped key for an input (raw) object.

        Format:
            runs/{run_id}/raw/{asset_type}/{asset_id}/{filename}

        Notes:
        - Keys are POSIX-style regardless of OS.
        - Leading slashes in filename are ignored.
        """

        return (
            pathlib.PurePosixPath("runs") / str(run_id) / "raw"
            / str(asset_type) / str(asset_id) / pathlib.PurePosixPath(str(filename)).name
        ).as_posix()

    @staticmethod
    def build_derived_object_key(run_id: str, asset_type: str, asset_id: str,
                                  relative_path: Union[str, pathlib.PurePosixPath]) -> str:
        """Build a run/batch-scoped key for a derived artifact object.

        Format:
            runs/{run_id}/derived/{asset_type}/{asset_id}/{relative_path}

        relative_path convention (recommended):
        - Must be a relative POSIX-style path (do not start with `/`; use `/` separators)
        - Must not contain `..`
        - First path segment should be a pipeline namespace to avoid collisions
          between independent ingestion flows.

        Example relative_path values:
            "frames-v1/frames/chunk_0003/frame_000120.jpg"
            "embed-v1/embeddings/chunk_0003/frame_000120.f32"
            "chunksum-v1/summaries/chunk_0003/summary.txt"
        """

        rel = pathlib.PurePosixPath(str(relative_path))
        if rel.is_absolute():
            rel = pathlib.PurePosixPath(*rel.parts[1:])
        return (
            pathlib.PurePosixPath("runs") / str(run_id) / "derived"
            / str(asset_type) / str(asset_id) / rel
        ).as_posix()
