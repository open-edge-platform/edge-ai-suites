# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import chromadb

CHROMA_SERVER_HOST = os.getenv("CHROMA_SERVER_HOST", "localhost")
CHROMA_SERVER_PORT = os.getenv("CHROMA_SERVER_PORT", "9090")


class ChromaClientWrapper:
    def __init__(self, host: str = CHROMA_SERVER_HOST, port: int = CHROMA_SERVER_PORT):
        self.client = chromadb.HttpClient(host=host, port=port)
        self.collection = None

    def load_collection(self, collection_name: str):
        try:
            self.collection = self.client.get_or_create_collection(name=collection_name)
            return self.collection
        except Exception as e:
            print(f"Failed to load collection {collection_name}: {e}")
            return None

    def create_collection(self, collection_name: str = "default"):
        if self.load_collection(collection_name):
            print(f"Collection {collection_name} already exists and is loaded.")
            return
        
        self.collection = self.client.create_collection(name=collection_name)

    def insert(self, data: list, collection_name):
        if not self.collection or self.collection.name != collection_name:
            self.load_collection(collection_name)
        
        ids = [item['id'] for item in data]
        vectors = [item['vector'] for item in data]
        metas = [item['meta'] for item in data]

        self.collection.add(
            ids=[str(i) for i in ids],
            embeddings=vectors,
            metadatas=metas
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
