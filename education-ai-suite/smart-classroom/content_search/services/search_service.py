# services/search_service.py
import httpx
import logging
from config import settings

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self):
        self.base_url = settings.SEARCH_SERVICE_BASE_URL
        self.ingest_url = f"{self.base_url}/v1/dataprep/ingest"
        self.retrieval_url = f"{self.base_url}/v1/retrieval"
        self.default_bucket = settings.MINIO_DEFAULT_BUCKET

    async def trigger_ingest(self, file_path: str, bucket_name: str = None):
        target_bucket = bucket_name or self.default_bucket
        payload = {"bucket_name": target_bucket, "file_path": file_path}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.ingest_url, json=payload, timeout=120.0)
                response.raise_for_status()
                logger.info(f"Successfully triggered ingest for {file_path}")
                return response.json()
            except Exception as e:
                logger.error(f"Search service ingest error: {str(e)}")
                return None

    async def semantic_search(self, query: str, limit: int = 3):
        payload = {"query": query, "max_num_results": limit}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.retrieval_url, json=payload)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Search service retrieval error: {str(e)}")
                return {"results": []}

search_service = SearchService()