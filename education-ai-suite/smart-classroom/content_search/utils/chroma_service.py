# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
from providers.chromadb_wrapper.chroma_client import ChromaClientWrapper
from utils.config_loader import config

logger = logging.getLogger(__name__)

class ChromaService:
    def __init__(self):
        self.wrapper = ChromaClientWrapper()
        self.default_collection = config.content_search.chromadb.collection_name

    async def collection_info(self, collection_name: str = None):
        target = collection_name or self.default_collection
        coll = self.wrapper.load_collection(target)
        if not coll:
            return {"exists": False, "count": 0}
        return {
            "exists": True,
            "name": coll.name,
            "count": coll.count(),
            "metadata": coll.metadata
        }

    async def search_vectors(self, vectors: list, collection_name: str = None, limit: int = 5, filters: dict = None):
        target = collection_name or self.default_collection
        try:
            raw_results = self.wrapper.query(
                collection_name=target,
                query_embeddings=vectors,
                where=filters,
                n_results=limit
            )

            formatted_results = []
            if raw_results and raw_results['ids']:
                for i in range(len(raw_results['ids'][0])):
                    formatted_results.append({
                        "id": raw_results['ids'][0][i],
                        "distance": raw_results['distances'][0][i],
                        "meta": raw_results['metadatas'][0][i]
                    })
            return formatted_results
        except Exception as e:
            logger.error(f"Chroma search error: {e}")
            return []

    async def delete_by_ids(self, ids: list, collection_name: str = None):
        target = collection_name or self.default_collection
        return self.wrapper.delete(ids=ids, collection_name=target)

    async def list_all_documents(self, collection_name: str = None):
        target = collection_name or self.default_collection
        return self.wrapper.query_all(collection_name=target)

chroma_service = ChromaService()