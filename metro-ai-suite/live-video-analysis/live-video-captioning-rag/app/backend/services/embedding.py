# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from langchain_vdms.vectorstores import VDMS, VDMS_Client
from typing import Any, Dict, Optional
import logging
import requests
import uuid

from ..config import (
    EMBEDDING_HOST,
    EMBEDDING_HOST_PORT,
    EMBEDDING_MODEL,
    VDMS_HOST,
    VDMS_PORT,
    SCORE_THRESHOLD,
    TOP_K,
)
from .embedding_wrapper import EmbeddingAPI

logger = logging.getLogger("app.embedding")

class CaptionEmbeddings:
    """
    Caption Embeddings service that interfaces with VDMS to store
    image-caption pairs.
    """

    def __init__(self):

        self.embedding_endpoint = f"http://{EMBEDDING_HOST}:{EMBEDDING_HOST_PORT}/embeddings"

        logger.info(f"Initializing CaptionEmbeddings with embedding endpoint: {self.embedding_endpoint}")
        # Initialize embedding resources
        self.embeddings = EmbeddingAPI(
            api_url=self.embedding_endpoint,
            model_name=EMBEDDING_MODEL
        )

        self.vector_dimensions = self.embeddings.get_embedding_length()

        self._init_vdms_store()

        self._http = requests.Session()
        self._http.headers.update({'Content-Type': 'application/json'})

    def _init_vdms_store(self):
        """Initialize or reinitialize VDMS client/store instances."""

        logger.info(f"VDMS_HOST: {VDMS_HOST}, VDMS_PORT: {VDMS_PORT}")
        self.vdms_client = VDMS_Client(
            host = VDMS_HOST,
            port = VDMS_PORT,
        )

        self.vdms_store = VDMS(
            client=self.vdms_client,
            embedding=self.embeddings,
            collection_name="captions_collection",
            engine="FaissFlat",
            distance_strategy="IP",
            embedding_dimensions=self.vector_dimensions,
        )

    def _reinitialize_vdms_store(self, reason: Exception):
        """Reconnect VDMS after transient or idle disconnection failures."""
        logger.warning("VDMS operation failed; reinitializing client/store. Error: %s", reason)
        self._init_vdms_store()

    def reconnect_vdms(self, reason: Optional[Exception] = None):
        """Public reconnect hook for query-side recovery from stale retrievers."""
        if reason is None:
            logger.warning("Reinitializing VDMS client/store due to explicit reconnect request")
            self._init_vdms_store()
            return

        self._reinitialize_vdms_store(reason)

    @staticmethod
    def _build_embedding_metadata(img_blob: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize metadata stored with the vector payload."""

        resolution = metadata.get("resolution") or {}

        return {
            "frame_id": metadata.get("frame_id", ""),
            "frame_format": metadata.get("img_format", ""),
            "frame_width": resolution.get("width"),
            "frame_height": resolution.get("height"),
            "frame_data": img_blob,
        }

    def process_embeddings(self, img_blob: str, metadata: Dict[str, Any] = None):
        """
        Add an image-caption pair to the VDMS vector store.
        """
        metadata = metadata or {}
        caption_text = str(metadata.get("result", "")).strip()

        if not caption_text:
            raise ValueError("Metadata field 'result' is required and cannot be empty.")

        payload = {
            "input": {"type": "text", "text": caption_text},
            "model": EMBEDDING_MODEL,
            "encoding_format": "float"
        }

        resp = self._http.post(self.embedding_endpoint, json=payload, timeout=(1.0, 15.0))
        resp.raise_for_status()
        rj = resp.json()
        emb = rj.get("embedding")

        if emb is None:
            raise ValueError("Missing 'embedding' in response")

        if not isinstance(emb, (list, tuple)) or not emb:
            raise TypeError(f"Embedding must be a non-empty list/tuple, got {type(emb)}")

        vector = [float(x) for x in emb]
        emb_metadata = self._build_embedding_metadata(img_blob, metadata)
        ids = str(uuid.uuid4())

        try:
            self.vdms_store.add_from(
                texts=[caption_text],
                metadatas=[emb_metadata],
                embeddings=[vector],
                ids=[ids],
            )
        except Exception as exc:
            self._reinitialize_vdms_store(exc)
            self.vdms_store.add_from(
                texts=[caption_text],
                metadatas=[emb_metadata],
                embeddings=[vector],
                ids=[ids],
            )

        return ids

    def get_retriever(self):
        """
        Return a LangChain retriever object for querying the VDMS store.
        """

        # Return no docs when nothing passes this similarity floor.
        try:
            retriever = self.vdms_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"k": TOP_K, "score_threshold": SCORE_THRESHOLD},
            )
        except Exception as exc:
            self._reinitialize_vdms_store(exc)
            retriever = self.vdms_store.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"k": TOP_K, "score_threshold": SCORE_THRESHOLD},
            )

        return retriever