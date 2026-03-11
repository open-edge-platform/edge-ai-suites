import uuid
from fastapi import UploadFile
from ext_components.storage_minio.content_search_minio.minio_client import MinioStore

class StorageService:
    def __init__(self):
        # Auto-detect config.json under symlinked path
        self.store = MinioStore.from_config()
        self.store.ensure_bucket()

    async def upload_and_prepare_payload(self, file: UploadFile, asset_id: str = "default") -> dict:
        """Upload a file and build the payload expected by the Worker."""
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        
        # 1. Build MinIO standard path
        object_key = self.store.build_raw_object_key(
            run_id=run_id,
            asset_type="video",
            asset_id=asset_id,
            filename=file.filename
        )
        
        # 2. Write to MinIO
        content = await file.read()
        self.store.put_bytes(object_key, content, content_type=file.content_type)
        
        # 3. Return payload dict for database usage
        return {
            "source": "minio",
            "video_key": object_key,
            "bucket": self.store.bucket,
            "filename": file.filename,
            "run_id": run_id
        }

storage_service = StorageService()