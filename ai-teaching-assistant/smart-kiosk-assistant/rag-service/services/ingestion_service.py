"""Ingestion: chunk a text blob and upsert into the vector store."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from langchain_core.documents import Document

from components.chunker_component import SemanticChunker


logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        vectorstore_provider: Callable[[], object],
        chunker: SemanticChunker,
    ) -> None:
        self._vectorstore_provider = vectorstore_provider
        self._chunker = chunker

    @property
    def vectorstore(self):
        return self._vectorstore_provider()

    def ingest_text(
        self,
        text: str,
        source: str = "api",
        metadata: dict | None = None,
    ) -> int:
        logger.info("[INGEST] Starting | source=%s | input_chars=%d", source, len(text))
        t0 = time.monotonic()

        # Remove any existing docs for this source so re-ingestion replaces
        # rather than accumulates (prevents stale duplicates across runs).
        try:
            collection = getattr(self.vectorstore, "_collection", None)
            if collection is not None:
                existing = collection.get(where={"source": source}, include=[])
                if existing["ids"]:
                    collection.delete(ids=existing["ids"])
                    logger.info(
                        "[INGEST] Removed %d stale docs for source=%s",
                        len(existing["ids"]), source,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[INGEST] Could not purge old docs for source=%s: %s", source, exc)

        chunks = self._chunker.chunk_text(text)
        t_chunk = time.monotonic()
        logger.info(
            "[INGEST] Chunking done | chunks=%d | elapsed=%.1fs",
            len(chunks), t_chunk - t0,
        )

        if not chunks:
            logger.warning("[INGEST] No chunks produced — ingestion aborted")
            return 0

        docs = [
            Document(
                page_content=chunk.text,
                metadata={
                    "source": source,
                    "chunk_index": chunk.index,
                    **(metadata or {}),
                },
                id=str(uuid.uuid4()),
            )
            for chunk in chunks
        ]

        logger.info("[INGEST] Embedding + upserting %d docs into vectorstore...", len(docs))
        self.vectorstore.add_documents(docs)
        t_done = time.monotonic()
        logger.info(
            "[INGEST] Done | docs_added=%d | embed+upsert=%.1fs | total=%.1fs",
            len(docs), t_done - t_chunk, t_done - t0,
        )
        return len(docs)
