# Derived from: edge-ai-libraries/microservices/multimodal-embedding-serving/src/models/registry.py
#              + edge-ai-libraries/microservices/multimodal-embedding-serving/src/models/config.py
# Original package: multimodal-embedding-serving v0.1.1
# Only CLIP model configs retained; other handlers removed.
#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from typing import Dict, Any

from .base import BaseEmbeddingModel
from .clip_handler import CLIPHandler

logger = logging.getLogger(__name__)

# ── CLIP model configurations ────────────────────────────────────────
CLIP_CONFIGS: Dict[str, Dict[str, Any]] = {
    "clip-vit-b-32": {
        "model_name": "ViT-B-32",
        "pretrained": "laion2b_s34b_b79k",
        "image_size": 224,
    },
    "clip-vit-b-16": {
        "model_name": "ViT-B-16",
        "pretrained": "openai",
        "image_size": 224,
    },
    "clip-vit-l-14": {
        "model_name": "ViT-L-14",
        "pretrained": "datacomp_xl_s13b_b90k",
        "image_size": 224,
    },
    "clip-vit-h-14": {
        "model_name": "ViT-H-14",
        "pretrained": "laion2b_s32b_b79k",
        "image_size": 224,
    },
}


def get_model_handler(
    model_id: str,
    device: str | None = None,
) -> BaseEmbeddingModel:
    """Create a CLIPHandler for the given *model_id*.

    Accepted formats:
        "CLIP/clip-vit-b-16"   (type/name)
        "clip-vit-b-16"        (name only)
    """
    # Strip optional "CLIP/" prefix
    if "/" in model_id:
        _, model_name = model_id.split("/", 1)
    else:
        model_name = model_id

    if model_name not in CLIP_CONFIGS:
        raise ValueError(
            f"Model '{model_id}' not found. "
            f"Available: {', '.join(CLIP_CONFIGS)}"
        )

    config = CLIP_CONFIGS[model_name].copy()
    config["device"] = device or os.getenv("EMBEDDING_DEVICE", "CPU")

    logger.info(f"Creating CLIPHandler for {model_id} with config: {config}")
    return CLIPHandler(config)
