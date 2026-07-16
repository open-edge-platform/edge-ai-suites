# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import threading
from pathlib import Path
from typing import Any, List

import openvino_genai as ov_genai
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.embeddings import BaseEmbedding

from providers.utils.model_utils import resolve_model_max_length


class OpenVINOGenAIEmbedding(BaseEmbedding):
    """LlamaIndex ``BaseEmbedding`` wrapping ``ov_genai.TextEmbeddingPipeline``."""

    _pipe: Any = PrivateAttr()
    _lock: Any = PrivateAttr()
    _model_path: str = PrivateAttr()
    _max_length: int = PrivateAttr()
    _tokenizer: Any = PrivateAttr(default=None)
    _tokenizer_lock: Any = PrivateAttr()

    def __init__(
        self,
        model_path: str,
        device: str = "CPU",
        query_instruction: str = "query: ",
        text_instruction: str = "passage: ",
        embed_batch_size: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(embed_batch_size=embed_batch_size, **kwargs)

        self._model_path = str(model_path)
        self._max_length = resolve_model_max_length(model_path)

        config = ov_genai.TextEmbeddingPipeline.Config()
        config.pooling_type = ov_genai.TextEmbeddingPipeline.PoolingType.CLS
        config.normalize = True
        # Cap tokenization to the model's context length. Encoder models have a
        # fixed position-embedding table, so a chunk longer than this overflows it
        # and crashes ("Eltwise shape infer ... mismatch"); truncating here
        # mirrors HuggingFace's truncation=True. Chunkers use count_tokens() to
        # split text to fit this budget so nothing is lost to truncation.
        config.max_length = self._max_length
        if query_instruction is not None:
            config.query_instruction = query_instruction
        if text_instruction is not None:
            config.embed_instruction = text_instruction

        self._pipe = ov_genai.TextEmbeddingPipeline(str(model_path), device.upper(), config)
        self._lock = threading.Lock()
        self._tokenizer_lock = threading.Lock()

    @classmethod
    def class_name(cls) -> str:
        return "OpenVINOGenAIEmbedding"

    @property
    def max_length(self) -> int:
        """Max input token length the model accepts before truncation."""
        return self._max_length

    def count_tokens(self, text: str) -> int:
        """Token count for ``text`` using the model's own tokenizer.

        Lets chunkers keep chunks within ``max_length`` so content is split
        rather than tail-truncated at embedding time. Falls back to a
        character-count upper bound if the tokenizer can't be loaded.
        """
        tokenizer = self._get_tokenizer()
        if tokenizer is None:
            # ~1 token/char is the worst case (CJK); this over-counts latin text
            # but never under-counts, so chunks stay within the model limit.
            return len(text)
        return len(tokenizer.encode(text).ids)

    def _get_tokenizer(self):
        """Lazily load the fast tokenizer saved beside the model IR (cached)."""
        if self._tokenizer is None:
            with self._tokenizer_lock:
                if self._tokenizer is None:
                    try:
                        from tokenizers import Tokenizer

                        self._tokenizer = Tokenizer.from_file(
                            str(Path(self._model_path) / "tokenizer.json")
                        )
                    except Exception:
                        # Tried and failed — False sentinel avoids retrying.
                        self._tokenizer = False
        return self._tokenizer or None

    def _get_query_embedding(self, query: str) -> List[float]:
        with self._lock:
            return list(self._pipe.embed_query(query))

    def _get_text_embedding(self, text: str) -> List[float]:
        with self._lock:
            return list(self._pipe.embed_documents([text])[0])

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        with self._lock:
            return [list(emb) for emb in self._pipe.embed_documents(list(texts))]

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)
