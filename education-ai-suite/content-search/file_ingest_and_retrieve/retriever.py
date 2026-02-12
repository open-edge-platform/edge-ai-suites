# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from chromadb import Where
from PIL import Image
import base64
import io
import os

from multimodal_embedding_serving import get_model_handler, EmbeddingModel

from chromadb_wrapper.chroma_client import ChromaClientWrapper

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "CLIP/clip-vit-b-16")

class ChromaRetriever:
    def __init__(self, collection_name="default"):
        self.collection_name = collection_name
        self.client = ChromaClientWrapper()
        self.client.load_collection(collection_name)
        self.model_name = EMBEDDING_MODEL_NAME
        
        handler = get_model_handler(self.model_name)
        handler.load_model()
        self.embedding_model = EmbeddingModel(handler)

    def get_text_embedding(self, query):
        embedding_tensor = self.embedding_model.handler.encode_text(query)
        embedding_list = embedding_tensor.cpu().numpy().tolist()
        return embedding_list
        
    def get_image_embedding(self, image_base64):
        img_data = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        embedding_tensor = self.embedding_model.handler.encode_image(img)
        embedding_list = embedding_tensor.cpu().numpy().tolist()
        return embedding_list

    def search(self, query=None, image_base64=None, filters=None, top_k=5):
        # Validate input
        if not query and not image_base64:
            raise ValueError("Either 'query' or 'image_base64' must be provided.")
        if query and image_base64:
            raise ValueError("Provide only one of 'query' or 'image_base64', not both.")

        # Get the embedding for the query or image
        if query:
            embedding = self.get_text_embedding(query)
        else:
            embedding = self.get_image_embedding(image_base64)

        if embedding is None:
            raise Exception("Failed to get embedding for the input.")

        where_clause: Where = {}
        if filters:
            for key, value in filters.items():
                if key == "timestamp_start":
                    where_clause["timestamp"] = where_clause.get("timestamp", {})
                    where_clause["timestamp"]["$gte"] = value
                elif key == "timestamp_end":
                    where_clause["timestamp"] = where_clause.get("timestamp", {})
                    where_clause["timestamp"]["$lte"] = value
                else:
                    where_clause[key] = value

        results = self.client.query(
            collection_name=self.collection_name,
            query_embeddings=embedding,
            where=where_clause if where_clause else None,
            n_results=top_k,
        )
        
        return results
