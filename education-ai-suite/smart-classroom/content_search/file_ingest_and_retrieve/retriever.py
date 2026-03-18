# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from chromadb import Where
from PIL import Image
import base64
import io

from multimodal_embedding_serving import get_model_handler, EmbeddingModel
from llama_index.embeddings.huggingface_openvino import OpenVINOEmbedding

from content_search.chromadb_wrapper.chroma_client import ChromaClientWrapper
from utils.config_loader import config

_cfg = config.content_search.file_ingest


class ChromaRetriever:
    def __init__(self, collection_name="default"):
        self.client = ChromaClientWrapper()

        self.visual_collection_name = collection_name
        self.client.load_collection(self.visual_collection_name)
        handler = get_model_handler(_cfg.visual_embedding_model)
        handler.load_model()
        self.visual_embedding_model = EmbeddingModel(handler)

        self.document_collection_name = f"{collection_name}_documents"
        self.client.load_collection(self.document_collection_name)
        self.document_embedding_model = OpenVINOEmbedding(
            model_id_or_path=_cfg.doc_embedding_model,
            device=_cfg.device,
        )

    def get_text_embedding(self, query):
        embedding_tensor = self.visual_embedding_model.handler.encode_text(query)
        return embedding_tensor.cpu().numpy().tolist()

    def get_document_embedding(self, text):
        if not self.document_embedding_model:
            raise RuntimeError("Document embedding model not available.")
        return self.document_embedding_model.get_text_embedding(text)

    def get_image_embedding(self, image_base64):
        img_data = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        embedding_tensor = self.visual_embedding_model.handler.encode_image(img)
        return embedding_tensor.cpu().numpy().tolist()

    def search(self, query=None, image_base64=None, filters=None, top_k=5):
        if not query and not image_base64:
            raise ValueError("Either 'query' or 'image_base64' must be provided.")
        if query and image_base64:
            raise ValueError("Provide only one of 'query' or 'image_base64', not both.")

        if query:
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
        vis_ids = visual_results.get("ids", [[]])[0]
        vis_metas = visual_results.get("metadatas", [[]])[0]
        vis_dists = visual_results.get("distances", [[]])[0]
        doc_ids = doc_results.get("ids", [[]])[0]
        doc_metas = doc_results.get("metadatas", [[]])[0]
        doc_dists = doc_results.get("distances", [[]])[0]

        combined = sorted(
            list(zip(vis_dists, vis_ids, vis_metas)) + list(zip(doc_dists, doc_ids, doc_metas)),
            key=lambda x: x[0]
        )
        return {
            "ids": [[c[1] for c in combined]],
            "metadatas": [[c[2] for c in combined]],
            "distances": [[c[0] for c in combined]],
        }
