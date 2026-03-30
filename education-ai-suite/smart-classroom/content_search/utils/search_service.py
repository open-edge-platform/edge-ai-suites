#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import httpx
import logging
from utils.config import settings

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self):
        self.base_url = settings.SEARCH_SERVICE_BASE_URL
        self.ingest_url = f"{self.base_url}/v1/dataprep/ingest"
        self.ingest_text_url = f"{self.base_url}/v1/dataprep/ingest_text"
        self.retrieval_url = f"{self.base_url}/v1/retrieval"
        self.default_bucket = settings.MINIO_DEFAULT_BUCKET

    async def trigger_ingest(self, file_path: str, bucket_name: str = None, meta: dict = None, is_directory: bool = False):
        target_bucket = bucket_name or self.default_bucket
        path_key = "folder_path" if is_directory else "file_path"
        payload = {
            "bucket_name": target_bucket,
            path_key: file_path,
            "meta": meta or {}
        }
        async with httpx.AsyncClient() as client:
            try:
                # Ingest maybe slow
                response = await client.post(self.ingest_url, json=payload, timeout=300.0)
                response.raise_for_status()
                logger.info(f"Successfully triggered ingest for {file_path}")
                return response.json()
            except Exception as e:
                logger.error(f"Search service ingest error: {str(e)}")
                return {"error": str(e)}

    async def ingest_text(self, text: str, file_path: str = None, bucket_name: str = None, meta: dict = None):
        payload = {
            "text": text,
            "file_path": file_path,
            "bucket_name": bucket_name or self.default_bucket,
            "meta": meta or {}
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.ingest_text_url, json=payload, timeout=60.0)
                response.raise_for_status()
                logger.info(f"Successfully ingested raw text for {file_path}")
                return response.json()
            except Exception as e:
                logger.error(f"Search service ingest_text error: {str(e)}")
                return {"error": str(e)}

    async def semantic_search(self, query: str, limit: int = 3, filters: dict = None):
        payload = {
            "query": query, 
            "max_num_results": limit
        }
        if filters:
            payload["filter"] = filters

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.retrieval_url, json=payload)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Search service retrieval error: {str(e)}")
                return {"results": []}

search_service = SearchService()
