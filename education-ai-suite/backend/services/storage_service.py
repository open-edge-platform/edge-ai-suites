import uuid
import uuid
import logging
from fastapi import UploadFile

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self._store = None
        self._error_msg = None

        self._try_initialize()

    def _try_initialize(self):
        try:
            from ext_components.content_search_minio.minio_client import MinioStore
            self._store = MinioStore.from_config()
            self._store.ensure_bucket()
            self._error_msg = None
        except (ImportError, ModuleNotFoundError) as e:
            self._error_msg = f"Component missing: {str(e)}"
            logger.error(f"❌ MinIO component load failed: {self._error_msg}")
        except Exception as e:
            self._error_msg = f"Initialization failed: {str(e)}"
            logger.error(f"❌ MinIO connection failed: {self._error_msg}")

    @property
    def is_available(self) -> bool:
        return self._store is not None

    async def upload_and_prepare_payload(self, file: UploadFile, asset_id: str = "default") -> dict:
        if not self.is_available:
            raise RuntimeError(f"Storage Service is unavailable: {self._error_msg}")
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        # 1. Build MinIO standard path
        object_key = self._store.build_raw_object_key(
            run_id=run_id,
            asset_type="video",
            asset_id=asset_id,
            filename=file.filename
        )
        content = await file.read()
        self._store.put_bytes(object_key, content, content_type=file.content_type)

        return {
            "source": "minio",
            "video_key": object_key,
            "bucket": self._store.bucket,
            "filename": file.filename,
            "run_id": run_id
        }

storage_service = StorageService()