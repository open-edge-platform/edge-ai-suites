# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import os

from chromadb import Where
from PIL import Image
import base64
import io

from providers.chromadb_wrapper.chroma_client import ChromaClientWrapper
from providers.file_ingest_and_retrieve.models import (
    get_visual_embedding_model,
    get_document_embedding_model,
)

logger = logging.getLogger(__name__)

class ChromaRetriever:
    def __init__(self, collection_name="default", visual_embedding_model=None, document_embedding_model=None, video_summary_id_map=None):
        self.client = ChromaClientWrapper()

        self.visual_collection_name = collection_name
        self.client.load_collection(self.visual_collection_name)

        self.visual_embedding_model = visual_embedding_model or get_visual_embedding_model()

        self.document_collection_name = f"{collection_name}_documents"
        self.client.load_collection(self.document_collection_name)

        self.document_embedding_model = document_embedding_model or get_document_embedding_model()

        # Post-processor (reranker + dedup + slot allocation)
        reranker_model = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-large")
        reranker_device = os.environ.get("RERANKER_DEVICE", "CPU")
        dedup_time_threshold = float(os.environ.get("RERANKER_DEDUP_TIME_THRESHOLD", "5.0"))
        overfetch_multiplier = int(os.environ.get("RERANKER_OVERFETCH_MULTIPLIER", "3"))
        from providers.file_ingest_and_retrieve.reranker import PostProcessor
        self.post_processor = PostProcessor(
            reranker_model=reranker_model,
            device=reranker_device,
            dedup_time_threshold=dedup_time_threshold,
            overfetch_multiplier=overfetch_multiplier,
            video_summary_id_map=video_summary_id_map if video_summary_id_map is not None else {},
            chroma_client=self.client,
            document_collection_name=self.document_collection_name,
        )
        self._overfetch_multiplier = overfetch_multiplier

        self.video_summary_id_map = video_summary_id_map if video_summary_id_map is not None else {}

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
                # Array metadata fields (e.g. tags) use $contains; scalar fields use $eq
                _ARRAY_FIELDS = {"tags"}
                if key in _ARRAY_FIELDS:
                    exprs = [{key: {"$contains": v}} for v in value]
                else:
                    exprs = [{key: v} for v in value]
                if len(exprs) == 1:
                    conditions.extend(exprs)
                elif list_filter_mode == "and":
                    conditions.append({"$and": exprs})
                else:
                    conditions.append({"$or": exprs})
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

        # Over-fetch when post-processor is active to compensate for dedup reduction
        fetch_k = top_k * self._overfetch_multiplier

        # Search visual collection
        results = self.client.query(
            collection_name=self.visual_collection_name,
            query_embeddings=embedding,
            where=where,
            n_results=fetch_k,
        )

        # If text query, also search document collection and combine results
        if query:
            doc_results = self.client.query(
                collection_name=self.document_collection_name,
                query_embeddings=[document_embedding],
                where=where,
                n_results=fetch_k,
            )
            results = self.post_processor.process_text_query_results(
                query, results, doc_results, top_k,
            )
        else:
            results = self.post_processor.process_image_query_results(results, top_k)

        return results

    def get_video_summaries(self, file_path):

        ids = self.video_summary_id_map.get(file_path, [])
        if not ids:
            return []
        return self.client.get(
            ids=ids,
            output_fields=["id", "meta"],
            collection_name=self.document_collection_name,
        )
