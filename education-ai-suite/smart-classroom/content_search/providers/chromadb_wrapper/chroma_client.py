#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import logging
import chromadb
import os

logger = logging.getLogger(__name__)

_MAX_BATCH_SIZE = 5000

class ChromaClientWrapper:
    def __init__(self, host: str = None, port: int = None):

        if host is None:
            host = os.getenv("CHROMA_HOST", "127.0.0.1")
        if port is None:
            env_port = os.getenv("CHROMA_PORT", "9090")
            try:
                port = int(env_port)
            except ValueError:
                port = 9090

        self.client = chromadb.HttpClient(host=host, port=port)
        self.collection = None

    def load_collection(self, collection_name: str):
        try:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                configuration={"hnsw": {"space": "cosine"}},
            )
            return self.collection
        except Exception as e:
            logger.error(f"Failed to load collection '{collection_name}' (is ChromaDB running?): {e}")
            return None

    def create_collection(self, collection_name: str = "default"):
        if self.load_collection(collection_name):
            logger.info(f"Collection '{collection_name}' already exists and is loaded.")
            return
        
        self.collection = self.client.create_collection(
            name=collection_name,
            configuration={"hnsw": {"space": "cosine"}},
        )

    def insert(self, data: list, collection_name):
        if not self.collection or self.collection.name != collection_name:
            self.load_collection(collection_name)

        ids = [str(item['id']) for item in data]
        vectors = [item['vector'] for item in data]
        metas = [item['meta'] for item in data]

        for start in range(0, len(ids), _MAX_BATCH_SIZE):
            end = start + _MAX_BATCH_SIZE
            self.collection.add(
                ids=ids[start:end],
                embeddings=vectors[start:end],
                metadatas=metas[start:end],
            )

        return {"insert_count": len(ids)}
    
    def delete(self, ids: list, collection_name: str):
        if not self.collection or self.collection.name != collection_name:
            self.load_collection(collection_name)
        
        self.collection.delete(ids=[str(i) for i in ids])
        
        return {"delete_count": len(ids)}
    
    def get(self, ids: list, output_fields: list, collection_name: str):
        if not self.collection or self.collection.name != collection_name:
            self.load_collection(collection_name)
            
        res = self.collection.get(
                ids=[str(i) for i in ids],
                include=['metadatas', 'embeddings'] if 'vector' in output_fields else ['metadatas']
            )
        
        # Remap to match milvus output format
        results = []
        for i in range(len(res['ids'])):
            item = {'id': res['ids'][i], 'meta': res['metadatas'][i]}
            if 'embeddings' in res and res['embeddings']:
                item['vector'] = res['embeddings'][i]
            results.append(item)
        return results

    def query(self, collection_name: str, query_embeddings: list, where: dict = None, n_results: int = 5):
        if not self.collection or self.collection.name != collection_name:
            self.load_collection(collection_name)
        
        results = self.collection.query(
            query_embeddings=query_embeddings,
            where=where,
            n_results=n_results,
            include=["metadatas", "distances"]
        )
        return results

    def query_all(self, collection_name: str, output_fields: list = []):
        if not self.collection or self.collection.name != collection_name:
            self.load_collection(collection_name)

        count = self.collection.count()
        if count == 0:
            return []
            
        res = self.collection.get(
            limit=count,
            include=['metadatas']
        )
        
        # Remap to match milvus output format
        results = []
        for i in range(len(res['ids'])):
            item = {'id': res['ids'][i], 'meta': res['metadatas'][i]}
            results.append(item)
        return results
