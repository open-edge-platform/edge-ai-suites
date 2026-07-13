"""Top-level chunking orchestrator.

This file is intentionally small: each phase of chunking lives in its own
module under ``components.chunking`` (markdown splitter, LLM marker splitter,
size splitter, semantic merger, atomic-block detector, document profile
detector, debug). ``SemanticChunker`` reads config, instantiates each
component, and wires them into a pipeline.

Pipeline per document:
  1. normalize text
  2. detect document profile (filename hint, else LLM)
  3. markdown heading split  →  LCA-aware section merge
  4. for each section body:
       a. coarse passage split (token-window or char-window)
       b. for each passage:
            - if small enough → keep as-is (no LLM call)
            - else → LLM marker split, with atomic-block snapping
            - on LLM failure → deterministic recursive char splitter fallback
       c. repair any oversized chunk along atomic-aware units
       d. apply sentence-boundary overlap
  5. similarity-aware merge of below-min chunks across sections
"""
from __future__ import annotations

import logging
import os
import time
from typing import Callable

from utils.config_loader import config

from .chunking import (
    AtomicBlockDetector,
    ChunkRecord,
    DocumentProfileDetector,
    LLMMarkerSplitter,
    MarkdownHeadingSplitter,
    RecursiveCharSplitter,
    SemanticMerger,
    SizeSplitter,
    save_debug_chunks,
)
from .chunking.text_utils import apply_overlap, cleanup_chunks, normalize_text


logger = logging.getLogger(__name__)


__all__ = ["SemanticChunker", "ChunkRecord"]


class SemanticChunker:
    def __init__(
        self,
        embedding_component,
        llm_text_generator: Callable[[str, int | None, float | None], str],
        llm_tokenizer=None,
    ) -> None:
        chunk_cfg = config.chunking
        self.max_chunk_chars = int(getattr(chunk_cfg, "max_chunk_chars", 1200))
        self.min_chunk_chars = int(getattr(chunk_cfg, "min_chunk_chars", 180))
        self.overlap_chars = int(getattr(chunk_cfg, "overlap_chars", 120))
        # Below this size a passage is emitted as a single chunk without invoking
        # the LLM: it already fits the chunk cap, so splitting it would only
        # produce orphan-heading fragments. Defaults to max_chunk_chars.
        self.llm_min_passage_chars = int(
            getattr(chunk_cfg, "llm_min_passage_chars", self.max_chunk_chars)
        )
        _debug_dir = getattr(chunk_cfg, "save_chunks_debug", None)
        self.save_chunks_debug: str | None = str(_debug_dir) if _debug_dir else None

        atomic_detector = AtomicBlockDetector()
        self._markdown = MarkdownHeadingSplitter()
        self._profile = DocumentProfileDetector(llm_text_generator)
        self._llm_splitter = LLMMarkerSplitter(
            llm_text_generator=llm_text_generator,
            atomic_detector=atomic_detector,
            min_chunk_chars=self.min_chunk_chars,
            max_chunk_chars=self.max_chunk_chars,
        )
        self._size_splitter = SizeSplitter(
            max_chunk_chars=self.max_chunk_chars,
            llm_passage_chars=int(getattr(chunk_cfg, "llm_passage_chars", 6000)),
            llm_passage_tokens=int(getattr(chunk_cfg, "llm_passage_tokens", 0)),
            llm_passage_overlap_tokens=int(getattr(chunk_cfg, "llm_passage_overlap_tokens", 0)),
            atomic_detector=atomic_detector,
            llm_tokenizer=llm_tokenizer,
        )
        self._merger = SemanticMerger(
            embedding_component=embedding_component,
            min_chunk_chars=self.min_chunk_chars,
            max_chunk_chars=self.max_chunk_chars,
            semantic_similarity_threshold=float(
                getattr(chunk_cfg, "semantic_similarity_threshold", 0.72)
            ),
        )
        self._recursive = RecursiveCharSplitter(
            max_chunk_chars=self.max_chunk_chars,
            min_chunk_chars=self.min_chunk_chars,
        )

    def chunk_text(self, text: str, source_hint: str | None = None) -> list[ChunkRecord]:
        normalized = normalize_text(text)
        if not normalized:
            return []

        t0 = time.monotonic()
        logger.info(
            "[CHUNKER] Starting chunking | strategy=semantic_llm | input_chars=%d | hint=%s",
            len(normalized), source_hint,
        )

        profile = self._profile.detect(normalized, source_hint)

        sections = self._markdown.split(normalized)
        logger.info("[CHUNKER] Markdown pre-split | sections=%d", len(sections))
        sections = self._markdown.merge_small(sections, self.max_chunk_chars)
        logger.info("[CHUNKER] After section merge | sections=%d", len(sections))

        all_items: list[tuple[str, dict]] = []
        for heading_path, body in sections:
            if not body.strip():
                continue
            section_chunks = self._chunk_body(body, profile)
            section_chunks = self._size_splitter.repair_oversized(section_chunks)
            section_chunks = apply_overlap(section_chunks, self.overlap_chars)
            for c in section_chunks:
                md: dict = {"domain": profile.get("domain", "generic")}
                if heading_path:
                    md["section"] = heading_path
                # Contextual prefix: every chunk carries its full ancestor
                # heading path so embeddings encode document+section context,
                # not just the local body. Mitigates intro/boilerplate chunks
                # monopolising rank 1 on brand-suffixed queries.
                prefixed = f"[Context: {heading_path}]\n\n{c}" if heading_path else c
                all_items.append((prefixed, md))

        all_items = self._merger.merge_small_chunks(all_items)

        if self.save_chunks_debug and all_items:
            service_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            save_debug_chunks(
                [c for c, _ in all_items], self.save_chunks_debug, service_root,
            )

        records = [
            ChunkRecord(text=c, index=i, metadata=md)
            for i, (c, md) in enumerate(all_items)
        ]
        elapsed = time.monotonic() - t0
        logger.info(
            "[CHUNKER] Done | total_chunks=%d | elapsed=%.1fs",
            len(records), elapsed,
        )
        return records

    def _chunk_body(self, text: str, profile: dict) -> list[str]:
        coarse_passages = self._size_splitter.coarse_split(text)
        total = len(coarse_passages)
        logger.info(
            "[CHUNKER] semantic_llm | passages=%d | domain=%s | %s",
            total, profile["domain"], profile["structure"],
        )

        results: list[str] = []
        for p_idx, passage in enumerate(coarse_passages, start=1):
            passage_chars = len(passage)
            tag = f"Passage {p_idx}/{total} |"

            if passage_chars <= self.llm_min_passage_chars:
                logger.info(
                    "[CHUNKER] %s chars=%d | <= llm_min_passage_chars (%d), keeping as one chunk",
                    tag, passage_chars, self.llm_min_passage_chars,
                )
                results.append(passage)
                continue

            logger.info(
                "[CHUNKER] %s chars=%d | requesting split markers",
                tag, passage_chars,
            )
            logger.info("[CHUNKER] %s preview: %r", tag, passage[:200])

            chunks = self._llm_splitter.split_passage(passage, profile, passage_log_tag=tag)
            if chunks is not None:
                for ci, c in enumerate(chunks, start=1):
                    logger.info(
                        "[CHUNKER] %s chunk %d/%d | chars=%d | preview: %r",
                        tag, ci, len(chunks), len(c), c[:120],
                    )
                results.extend(chunks)
                continue

            fb = self._recursive.split(passage)
            logger.info("[CHUNKER] %s recursive fallback → %d chunks", tag, len(fb))
            results.extend(fb)

        return cleanup_chunks(results)
