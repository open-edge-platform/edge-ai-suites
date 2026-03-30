# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from chromadb import Where
from PIL import Image
import base64
import io

from providers.file_ingest_and_retrieve.embedding import get_model_handler, EmbeddingModel
from llama_index.embeddings.huggingface_openvino import OpenVINOEmbedding

from providers.chromadb_wrapper.chroma_client import ChromaClientWrapper

import os

class ChromaRetriever:
    def __init__(self, collection_name="default"):
        self.client = ChromaClientWrapper()

        self.visual_collection_name = collection_name
        self.client.load_collection(self.visual_collection_name)
        visual_model_name = os.getenv("VISUAL_EMBEDDING_MODEL", "CLIP/clip-vit-b-16")
        handler = get_model_handler(visual_model_name)
        handler.load_model()
        self.visual_embedding_model = EmbeddingModel(handler)

        self.document_collection_name = f"{collection_name}_documents"
        self.client.load_collection(self.document_collection_name)

        doc_model_path = os.getenv("DOC_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        run_device = os.getenv("INGEST_DEVICE", "CPU")
        self.document_embedding_model = OpenVINOEmbedding(
            model_id_or_path=doc_model_path,
            device=run_device,
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

    def _build_where_clause(self, filters: dict, list_filter_mode: str = "or") -> dict:
        """Build a ChromaDB where clause from a filters dict.

        Different keys are always combined with $and regardless of list_filter_mode.
        list_filter_mode only controls the logic *within* a single list-valued field:
            "or"  (Option B): field must contain AT LEAST ONE of the filter values ($or).
            "and" (Option A): field must contain ALL of the filter values ($and).

        Example: {"course": "CS101", "tags": ["tag1", "tag2"]} with mode="or" →
            $and: [ {course: CS101}, $or: [{tags $contains "tag1"}, {tags $contains "tag2"}] ]
        """
        conditions = []
        for key, value in filters.items():
            if key == "timestamp_start":
                conditions.append({"timestamp": {"$gte": value}})
            elif key == "timestamp_end":
                conditions.append({"timestamp": {"$lte": value}})
            elif isinstance(value, list):
                # Use native ChromaDB $contains for array metadata fields (requires chromadb>=1.5.5)
                contains_exprs = [{key: {"$contains": v}} for v in value]
                if len(contains_exprs) == 1:
                    conditions.extend(contains_exprs)
                elif list_filter_mode == "and":
                    # Option A: ALL values must be present
                    conditions.append({"$and": contains_exprs})
                else:
                    # Option B (default): ANY value must be present
                    conditions.append({"$or": contains_exprs})
            else:
                conditions.append({key: value})

        if not conditions:
            return {}
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def search(self, query=None, image_base64=None, filters=None, top_k=5, list_filter_mode="or"):
        """Search the index.

        Args:
            list_filter_mode: How list-valued filter fields are matched.
                "or"  (Option B) — field must contain at least one of the filter values.
                "and" (Option A) — field must contain all of the filter values.
        """
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

        where = self._build_where_clause(filters, list_filter_mode) if filters else None

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
