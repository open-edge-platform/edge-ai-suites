# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from pathlib import Path
from typing import Optional

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

        visual_model_name = os.getenv("VISUAL_EMBEDDING_MODEL", "CLIP/clip-vit-b-16")
        logger.info(f"Initializing visual embedding model: {visual_model_name}")

        handler = get_model_handler(visual_model_name)
        handler.load_model()
        _visual_embedding_model = EmbeddingModel(handler)

        logger.info("Visual embedding model initialized and cached")
    return _visual_embedding_model


def get_document_embedding_model():
    """
    Lazy load and cache the document embedding model (OpenVINOEmbedding) once.

    Returns:
        OpenVINOEmbedding: Cached document embedding model
    """
    global _document_embedding_model
    if _document_embedding_model is None:
        from llama_index.embeddings.huggingface_openvino import OpenVINOEmbedding

        doc_model_path = os.getenv("DOC_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        run_device = os.getenv("INGEST_DEVICE", "CPU")

        local_path = Path(os.getcwd()).parent / "models" / "openvino" / doc_model_path
        if local_path.exists():
            logger.info(f"Loading document embedding OV IR from {local_path}")
            _document_embedding_model = OpenVINOEmbedding(
                model_id_or_path=str(local_path),
                device=run_device,
            )
        else:
            logger.info(f"Converting document embedding model {doc_model_path} to OV IR and saving to {local_path}")
            _document_embedding_model = OpenVINOEmbedding(
                model_id_or_path=doc_model_path,
                device=run_device,
            )
            local_path.mkdir(parents=True, exist_ok=True)
            _document_embedding_model._model.save_pretrained(str(local_path))
            _document_embedding_model._tokenizer.save_pretrained(str(local_path))

        logger.info(f"Document embedding model {doc_model_path} initialized and cached on device {run_device}")
    return _document_embedding_model
