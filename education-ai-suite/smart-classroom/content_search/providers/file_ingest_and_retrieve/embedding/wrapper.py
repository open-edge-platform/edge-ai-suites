# Derived from: edge-ai-libraries/microservices/multimodal-embedding-serving/src/wrapper.py
# Original package: multimodal-embedding-serving v0.1.1
# Only CLIP-related functionality retained; URL/base64/video helpers removed
# (callers use handler.encode_image() directly).
#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import List

from .base import BaseEmbeddingModel


class EmbeddingModel:
    """Application-level wrapper around a model handler."""

    def __init__(self, model_handler: BaseEmbeddingModel):
        self.handler = model_handler
        self.model_config = model_handler.model_config
        self.device = model_handler.device
        self.supported_modalities = set(model_handler.supported_modalities)

    def embed_query(self, text: str) -> List[float]:
        prepared_text = self.handler.prepare_query(text)
        embeddings = self.handler.encode_text([prepared_text])
        return embeddings[0].tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        prepared_texts = self.handler.prepare_documents(texts)
        embeddings = self.handler.encode_text(prepared_texts)
        return embeddings.tolist()

    def get_embedding_length(self) -> int:
        return self.handler.get_embedding_dim()
