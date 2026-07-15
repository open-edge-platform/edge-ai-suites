# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from pathlib import Path
from typing import Optional

from providers.utils.model_utils import is_model_ready

logger = logging.getLogger(__name__)

# Global model cache to avoid duplicate loading
_visual_embedding_model: Optional[object] = None
_document_embedding_model: Optional[object] = None


def get_visual_embedding_model():
    """
    Lazy load and cache the visual embedding model (CLIP) once.

    Returns:
        EmbeddingModel: Cached CLIP embedding model
    """
    global _visual_embedding_model
    if _visual_embedding_model is None:
        from providers.file_ingest_and_retrieve.embedding import get_model_handler, EmbeddingModel

        visual_model_name = os.getenv("VISUAL_EMBEDDING_MODEL", "CLIP/clip-xlm-roberta-base-vit-b-32")
        logger.info(f"Initializing visual embedding model: {visual_model_name}")

        handler = get_model_handler(visual_model_name)
        handler.load_model()
        _visual_embedding_model = EmbeddingModel(handler)

        logger.info("Visual embedding model initialized and cached")
    return _visual_embedding_model


def get_document_embedding_model():
    """
    Lazy load and cache the document embedding model once.

    Returns:
        OpenVINOGenAIEmbedding: Cached document embedding model
    """
    global _document_embedding_model
    if _document_embedding_model is None:
        from providers.file_ingest_and_retrieve.openvino_genai_embedding import (
            OpenVINOGenAIEmbedding,
        )

        doc_model_path = os.getenv("DOC_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
        run_device = os.getenv("INGEST_DEVICE", "CPU")

        local_path = Path(os.getcwd()).parent / "models" / "openvino" / doc_model_path
        if not is_model_ready(local_path):
            from providers.vlm_openvino_serving.utils.utils import convert_model

            logger.info(f"Converting document embedding model {doc_model_path} to OV IR (first run)")
            convert_model(doc_model_path, str(local_path), model_type="embedding")

        logger.debug(f"Loading document embedding OV IR from {local_path}")
        _document_embedding_model = OpenVINOGenAIEmbedding(
            model_path=str(local_path),
            device=run_device,
            query_instruction="query: ",
            text_instruction="passage: ",
        )

        logger.info(f"Document embedding model initialized: {doc_model_path} on {run_device}")
    return _document_embedding_model
