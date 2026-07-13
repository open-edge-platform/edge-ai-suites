"""Thin RAG pipeline façade.

Wires the modular services (``LLMService``, ``IngestionService``,
``RetrievalService``, ``PromptBuilder``) into a single object with the
public API consumed by ``main.py`` and ``test_streaming.py``. All real work
lives in the services package; this file is intentionally small.
"""
from __future__ import annotations

import logging
import threading
from typing import Generator

from langchain_chroma import Chroma

from components.chunker_component import SemanticChunker
from components.embedding_component import EmbeddingComponent
from services import (
    ChromaEmbeddingAdapter,
    IngestionService,
    LLMService,
    PromptBuilder,
    RetrievalRecord,
    RetrievalService,
)
from utils.config_loader import config
from utils.ensure_model import ensure_llm_model, ensure_reranker_model, get_llm_model_path


logger = logging.getLogger(__name__)

_SHARED_PIPELINE: "RagPipeline | None" = None
_SHARED_PIPELINE_LOCK = threading.Lock()


__all__ = [
    "RagPipeline",
    "RetrievalRecord",
    "get_shared_pipeline",
    "close_shared_pipeline",
]


class RagPipeline:
    def __init__(self) -> None:
        # Ensure model is exported to OpenVINO IR before anything else
        ensure_llm_model()

        self.embedding_component = EmbeddingComponent()

        storage_cfg = config.storage
        self.persist_directory = storage_cfg.persist_directory
        self.collection_name = storage_cfg.collection_name

        llm_cfg = config.models.llm
        self._llm_service = LLMService(
            model_path=get_llm_model_path(),
            hf_id=llm_cfg.hf_id,
            device=str(getattr(llm_cfg, "device", "CPU")),
            temperature=float(getattr(llm_cfg, "temperature", 0.0)),
            default_max_new_tokens=int(getattr(config.answering, "max_tokens", 192)),
            max_generations_before_reload=int(
                getattr(config.answering, "max_generations_before_reload", 25)
            ),
            generation_timeout=float(getattr(config.answering, "generation_timeout_secs", 90.0)),
            cache_dir=getattr(llm_cfg, "cache_dir", None),
        )

        self.vectorstore = self._build_vectorstore()

        self.chunker = SemanticChunker(
            self.embedding_component,
            self._llm_service.as_text_generator(),
            llm_tokenizer=self._llm_service.tokenizer,
        )

        self._ingestion = IngestionService(
            vectorstore_provider=lambda: self.vectorstore,
            chunker=self.chunker,
        )

        reranker = None
        reranker_cfg = getattr(config.retrieval, "reranker", None)
        if reranker_cfg is not None and bool(getattr(reranker_cfg, "enabled", False)):
            from components.reranker_component import RerankerComponent

            rr_backend = (getattr(reranker_cfg, "backend", "") or "").lower()
            if rr_backend != "openvino":
                ensure_reranker_model()
            reranker = RerankerComponent()

        self._retrieval = RetrievalService(
            vectorstore_provider=lambda: self.vectorstore,
            top_k=int(getattr(config.retrieval, "top_k", 3)),
            fetch_k=int(getattr(config.retrieval, "fetch_k", 6)),
            score_threshold=getattr(config.retrieval, "score_threshold", None),
            reranker=reranker,
        )
        self._prompt_builder = PromptBuilder(
            system_prompt=config.answering.system_prompt,
            max_context_chars=int(getattr(config.retrieval, "max_context_chars", 16000)),
            history_turns=int(getattr(config.answering, "history_turns", 2)),
            include_source_markers=bool(getattr(config.answering, "include_source_markers", False)),
            fallback_to_general_knowledge=bool(
                getattr(config.answering, "fallback_to_general_knowledge", True)
            ),
        )

    # ── vectorstore ──────────────────────────────────────────────────

    def _build_vectorstore(self) -> Chroma:
        return Chroma(
            collection_name=self.collection_name,
            persist_directory=self.persist_directory,
            embedding_function=ChromaEmbeddingAdapter(self.embedding_component),
        )

    # ── lifecycle ────────────────────────────────────────────────────

    def close(self) -> None:
        self._llm_service.close()

    # ── tokenization helper (legacy passthrough) ─────────────────────

    def count_tokens(self, text: str) -> int:
        return self._llm_service.count_tokens(text)

    # ── ingestion ────────────────────────────────────────────────────

    def ingest_text(self, text: str, source: str = "api", metadata: dict | None = None) -> int:
        return self._ingestion.ingest_text(text, source=source, metadata=metadata)

    def clear_context(self) -> None:
        client = getattr(self.vectorstore, "_client", None)
        if client is None:
            raise RuntimeError("Vector store client is not available")
        try:
            client.delete_collection(self.collection_name)
        except Exception:  # noqa: BLE001
            logger.info(
                "Collection %s did not exist yet during clear_context", self.collection_name,
            )
        self.vectorstore = self._build_vectorstore()

    def get_stats(self) -> dict:
        collection = getattr(self.vectorstore, "_collection", None)
        count = collection.count() if collection is not None else None
        reranker_cfg = getattr(config.retrieval, "reranker", None)
        reranker_id = None
        if reranker_cfg is not None and getattr(reranker_cfg, "enabled", True):
            reranker_id = getattr(reranker_cfg, "hf_id", None)
        return {
            "collection_name": self.collection_name,
            "persist_directory": self.persist_directory,
            "document_count": count,
            "chunking_strategy": "semantic_llm+markdown_aware",
            "llm_model": config.models.llm.hf_id,
            "embedding_model": config.models.embedding.hf_id,
            "reranker_model": reranker_id,
        }

    # ── retrieval ────────────────────────────────────────────────────

    def retrieve(self, question: str, top_k: int | None = None) -> list[RetrievalRecord]:
        return self._retrieval.retrieve(question, top_k=top_k)

    # ── answering ────────────────────────────────────────────────────

    def answer_question(
        self,
        question: str,
        context_text: str | None = None,
        top_k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> dict:
        prompt, sources = self.plan_answer(
            question,
            context_text=context_text,
            top_k=top_k,
            system_prompt=system_prompt,
            history=history,
        )
        answer = self.generate_from_prompt(prompt, max_tokens=max_tokens, temperature=temperature)
        return {
            "answer": answer.strip(),
            "sources": self.source_payloads(sources),
        }

    def stream_answer(
        self,
        question: str,
        context_text: str | None = None,
        top_k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_prompt: str | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> Generator[str, None, None]:
        prompt, _ = self.plan_answer(
            question,
            context_text=context_text,
            top_k=top_k,
            system_prompt=system_prompt,
            history=history,
        )
        yield from self.stream_from_prompt(prompt, max_tokens=max_tokens, temperature=temperature)

    def plan_answer(
        self,
        question: str,
        context_text: str | None = None,
        top_k: int | None = None,
        system_prompt: str | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> tuple[str, list[RetrievalRecord]]:
        sources = self.retrieve(question, top_k=top_k)
        prompt = self._prompt_builder.build(
            question,
            sources,
            context_text=context_text,
            system_prompt=system_prompt,
            history=history,
        )
        return prompt, sources

    def generate_from_prompt(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        return self._llm_service.generate(prompt, max_tokens=max_tokens, temperature=temperature)

    def stream_from_prompt(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        yield from self._llm_service.generate_stream(
            prompt, max_tokens=max_tokens, temperature=temperature,
        )

    # ── source serialization ─────────────────────────────────────────

    @staticmethod
    def source_payload(record: RetrievalRecord) -> dict:
        return {
            "source": record.source,
            "score": record.score,
            "metadata": record.metadata,
            "content": record.content,
        }

    def source_payloads(self, records: list[RetrievalRecord]) -> list[dict]:
        return [self.source_payload(record) for record in records]


def close_shared_pipeline() -> None:
    global _SHARED_PIPELINE
    with _SHARED_PIPELINE_LOCK:
        if _SHARED_PIPELINE is not None:
            _SHARED_PIPELINE.close()
            _SHARED_PIPELINE = None


def get_shared_pipeline() -> RagPipeline:
    global _SHARED_PIPELINE
    if _SHARED_PIPELINE is not None:
        return _SHARED_PIPELINE

    with _SHARED_PIPELINE_LOCK:
        if _SHARED_PIPELINE is None:
            _SHARED_PIPELINE = RagPipeline()
        return _SHARED_PIPELINE
