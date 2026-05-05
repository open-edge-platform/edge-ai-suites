#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import hashlib
import uuid
import logging
from fastapi import HTTPException, UploadFile
from typing import Optional

# Stream in 1 MiB chunks so memory stays bounded even for multi-GB uploads.
_STREAM_CHUNK_SIZE = 1024 * 1024

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self._store = None
        self._error_msg = None

        self._try_initialize()

    def _try_initialize(self):
        try:
            from providers.local_storage.store import LocalStore
            self._store = LocalStore.from_config()
            self._error_msg = None
        except (ImportError, ModuleNotFoundError) as e:
            self._error_msg = f"Component missing: {str(e)}"
            logger.error(f"Storage component load failed: {self._error_msg}")
        except Exception as e:
            self._error_msg = f"Initialization failed: {str(e)}"
            logger.error(f"Storage initialization failed: {self._error_msg}")

    @property
    def is_available(self) -> bool:
        return self._store is not None

    async def upload_and_prepare_payload(
        self,
        file: UploadFile,
        asset_id: str = "default",
        max_size_bytes: Optional[int] = None,
    ) -> dict:
        if not self.is_available:
            raise RuntimeError(f"Storage Service is unavailable: {self._error_msg}")
        run_id = str(uuid.uuid4())
        main_type = file.content_type.split('/')[0]
        object_key = self._store.build_raw_object_key(
            run_id=run_id,
            asset_type=main_type,
            asset_id=asset_id,
            filename=file.filename
        )

        # Stream the upload to disk while computing the hash in one pass.
        # Avoids loading the whole file into memory (previously ~2x file size).
        dst_path = self._store._object_path(object_key)
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        total_bytes = 0
        try:
            with open(dst_path, "wb") as out:
                while True:
                    chunk = await file.read(_STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if max_size_bytes is not None and total_bytes > max_size_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File exceeds maximum size of {max_size_bytes} bytes",
                        )
                    hasher.update(chunk)
                    out.write(chunk)
        except HTTPException:
            # Remove the partial file so we don't leave junk on disk.
            try:
                dst_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise

        return {
            "source": "local",
            "file_key": object_key,
            "bucket": self._store.bucket,
            "filename": file.filename,
            "run_id": run_id,
            "file_hash": hasher.hexdigest(),
            "size_bytes": total_bytes,
        }

    def get_file_disk_path(self, file_key: str):
        if not self.is_available:
            raise RuntimeError(f"Storage Service is unavailable: {self._error_msg}")
        return self._store._object_path(file_key)

    async def get_file_stream(self, file_key: str):
        if not self.is_available:
            raise RuntimeError(f"Storage Service unavailable: {self._error_msg}")
        try:
            return self._store.get_object_stream(file_key)
        except Exception as e:
            logger.error(f"Failed to get file {file_key}: {str(e)}")
            raise e

    async def get_file_content(self, file_key: str, bucket_name: Optional[str] = None) -> bytes:
        if not self.is_available:
            raise RuntimeError(f"Storage Service is unavailable: {self._error_msg}")
        try:
            return self._store.get_bytes(file_key)
        except Exception as e:
            logger.error(f"Failed to read content for {file_key}: {str(e)}")
            raise e

    def file_exists(self, file_key: str) -> bool:
        if not self.is_available:
            raise RuntimeError(f"Storage Service is unavailable: {self._error_msg}")
        try:
            return self._store.object_exists(file_key)
        except Exception as e:
            logger.error(f"Error checking existence for {file_key}: {str(e)}")
            return False

    def get_file_size(self, file_key: str) -> int:
        """Get the size of a file in bytes"""
        if not self.is_available:
            raise RuntimeError(f"Storage Service is unavailable: {self._error_msg}")
        try:
            # For LocalStore, we can get the file path and check its size
            file_path = self._store._object_path(file_key)
            if not file_path.is_file():
                raise RuntimeError(f"File not found: {file_key}")
            return file_path.stat().st_size
        except Exception as e:
            logger.error(f"Failed to get file size for {file_key}: {str(e)}")
            raise e

    def delete_file(self, file_key: str, missing_ok: bool = True) -> bool:
        if not self.is_available:
            raise RuntimeError(f"Storage Service is unavailable: {self._error_msg}")
        try:
            result = self._store.delete_object(file_key, missing_ok=missing_ok)
            if result:
                logger.info(f"Successfully deleted file: {file_key}")
            return result
        except Exception as e:
            logger.error(f"Failed to delete file {file_key}: {str(e)}")
            raise e

    def list_all_files(self) -> list[str]:
        if not self.is_available:
            logger.warning(f"Storage Service is unavailable: {self._error_msg}")
            return []

        try:
            all_files = []
            buckets = self._store.list_buckets()

            for bucket in buckets:
                from providers.local_storage.store import LocalStore
                store = LocalStore(self._store._data_dir, bucket)

                for object_name in store.list_object_names("", recursive=True):
                    all_files.append(object_name)

            logger.info(f"Found {len(all_files)} files in LocalStorage across {len(buckets)} buckets")
            return all_files
        except Exception as e:
            logger.error(f"Error listing all files: {str(e)}")
            return []

storage_service = StorageService()
