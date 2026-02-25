# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from chromadb import Where
from PIL import Image
import base64
import io
import os

from multimodal_embedding_serving import get_model_handler, EmbeddingModel
from llama_index.embeddings.huggingface_openvino import OpenVINOEmbedding

from chromadb_wrapper.chroma_client import ChromaClientWrapper

VISUAL_EMBEDDING_MODEL_NAME = os.getenv("VISUAL_EMBEDDING_MODEL_NAME", "CLIP/clip-vit-b-16")
DOC_EMBEDDING_MODEL_NAME = os.getenv("DOC_EMBEDDING_MODEL_NAME", "BAAI/bge-small-en-v1.5")
DEVICE = os.getenv("DEVICE", "CPU")

class ChromaRetriever:
    def __init__(self, collection_name="default"):
        self.client = ChromaClientWrapper()

        self.visual_collection_name = collection_name
        self.client.load_collection(self.visual_collection_name)
        handler = get_model_handler(VISUAL_EMBEDDING_MODEL_NAME)
        handler.load_model()
        self.visual_embedding_model = EmbeddingModel(handler)

        self.document_collection_name = f"{collection_name}_documents"
        self.client.load_collection(self.document_collection_name)
        self.document_embedding_model = OpenVINOEmbedding(
            model_id_or_path=DOC_EMBEDDING_MODEL_NAME,
            device=DEVICE,
        )

    def get_text_embedding(self, query):
        embedding_tensor = self.visual_embedding_model.handler.encode_text(query)
        embedding_list = embedding_tensor.cpu().numpy().tolist()
        return embedding_list
        
    def get_document_embedding(self, text):
        if not self.document_embedding_model:
            raise RuntimeError("Document embedding model not available.")
        embedding = self.document_embedding_model.get_text_embedding(text)
        return embedding

    def get_image_embedding(self, image_base64):
        img_data = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        embedding_tensor = self.visual_embedding_model.handler.encode_image(img)
        embedding_list = embedding_tensor.cpu().numpy().tolist()
        return embedding_list

    def search(self, query=None, image_base64=None, filters=None, top_k=5):
        if not query and not image_base64:
            raise ValueError("Either 'query' or 'image_base64' must be provided.")
        if query and image_base64:
            raise ValueError("Provide only one of 'query' or 'image_base64', not both.")

        if query:
            # Get both visual and document embeddings to search in both collections
            embedding = self.get_text_embedding(query)
            document_embedding = self.get_document_embedding(query)
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

        where = where_clause if where_clause else None

        # Search visual collection
        results = self.client.query(
            collection_name=self.visual_collection_name,
            query_embeddings=embedding,
            where=where,
            n_results=top_k,
        )

        # If text query, also search document collection and combine results
        if query:
            doc_results = self.client.query(
                collection_name=self.document_collection_name,
                query_embeddings=[document_embedding],
                where=where,
                n_results=top_k,
            )
            results = self._merge_results(results, doc_results)

        return results

    def _merge_results(self, visual_results, doc_results):
        """Merge and sort results from visual and document collections by distance."""
        merged_ids = []
        merged_metadatas = []
        merged_distances = []

        vis_ids = visual_results.get("ids", [[]])[0]
        vis_metas = visual_results.get("metadatas", [[]])[0]
        vis_dists = visual_results.get("distances", [[]])[0]

        doc_ids = doc_results.get("ids", [[]])[0]
        doc_metas = doc_results.get("metadatas", [[]])[0]
        doc_dists = doc_results.get("distances", [[]])[0]

        combined = list(zip(vis_dists, vis_ids, vis_metas)) + list(zip(doc_dists, doc_ids, doc_metas))
        combined.sort(key=lambda x: x[0])

        for dist, id_, meta in combined:
            merged_distances.append(dist)
            merged_ids.append(id_)
            merged_metadatas.append(meta)

        return {
            "ids": [merged_ids],
            "metadatas": [merged_metadatas],
            "distances": [merged_distances],
        }
