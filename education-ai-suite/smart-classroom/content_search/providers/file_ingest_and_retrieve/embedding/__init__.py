# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from typing import List

from .clip_handler import CLIPHandler

__all__ = ["get_model_handler", "EmbeddingModel", "CLIPHandler"]

MODEL_ID = "clip-xlm-roberta-base-vit-b-32"


def get_model_handler(model_id: str = None, device: str = None) -> CLIPHandler:
    """Create the CLIP handler for xlm-roberta-base-ViT-B-32."""
    if model_id:
        name = model_id.split("/", 1)[-1] if "/" in model_id else model_id
        if name != MODEL_ID:
            raise ValueError(f"Only '{MODEL_ID}' is supported, got '{model_id}'")

    config = {
        "model_name": "xlm-roberta-base-ViT-B-32",
        "pretrained": "laion5b_s13b_b90k",
        "image_size": 224,
        "device": device or os.getenv("EMBEDDING_DEVICE", "CPU"),
    }
    return CLIPHandler(config)


class EmbeddingModel:
    """Application-level wrapper around the CLIP handler."""

    def __init__(self, model_handler: CLIPHandler):
        self.handler = model_handler
        self.model_config = model_handler.model_config
        self.device = model_handler.device
        self.supported_modalities = {"text", "image"}

    def embed_query(self, text: str) -> List[float]:
        embeddings = self.handler.encode_text([text])
        return embeddings[0].tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.handler.encode_text(texts)
        return embeddings.tolist()

    def get_embedding_length(self) -> int:
        return self.handler.get_embedding_dim()
