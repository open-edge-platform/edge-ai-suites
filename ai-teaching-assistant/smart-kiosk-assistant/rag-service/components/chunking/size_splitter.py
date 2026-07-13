from __future__ import annotations

import re

from .atomic_blocks import AtomicBlockDetector


class SizeSplitter:
    """Coarse size-based splitting and post-hoc repair of oversized chunks.

    ``coarse_split`` produces the large "passages" that the LLM splitter then
    refines. ``repair_oversized`` is a safety net that re-splits any chunk
    larger than ``max_chunk_chars`` along atomic-aware units (sentences /
    list blocks / tables / code fences), hard-cutting only when a single
    indivisible unit exceeds the cap."""

    def __init__(
        self,
        max_chunk_chars: int,
        llm_passage_chars: int,
        llm_passage_tokens: int,
        llm_passage_overlap_tokens: int,
        atomic_detector: AtomicBlockDetector,
        llm_tokenizer=None,
    ) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.llm_passage_chars = llm_passage_chars
        self.llm_passage_tokens = llm_passage_tokens
        self.llm_passage_overlap_tokens = llm_passage_overlap_tokens
        self.atomic_detector = atomic_detector
        self.llm_tokenizer = llm_tokenizer

    def coarse_split(self, text: str) -> list[str]:
        if self.llm_tokenizer is not None and self.llm_passage_tokens > 0:
            return self._split_by_tokens(
                text, self.llm_passage_tokens, self.llm_passage_overlap_tokens,
            )
        return self._split_by_size(text, self.llm_passage_chars)

    def repair_oversized(self, chunks: list[str]) -> list[str]:
        out: list[str] = []
        for c in chunks:
            if len(c) <= self.max_chunk_chars:
                out.append(c)
            else:
                out.extend(self._split_oversized(c))
        return out

    # ── internals ────────────────────────────────────────────────────

    def _split_oversized(self, text: str) -> list[str]:
        units = self.atomic_detector.split_into_units(text)
        out: list[str] = []
        buf = ""
        for u in units:
            cand = f"{buf}\n{u}".strip() if buf else u
            if len(cand) <= self.max_chunk_chars:
                buf = cand
                continue
            if buf:
                out.append(buf)
            if len(u) <= self.max_chunk_chars:
                buf = u
                continue
            # Single unit larger than the cap (e.g. a giant table). Hard-split
            # at the last whitespace before the cap to avoid mid-word breaks.
            remaining = u
            while len(remaining) > self.max_chunk_chars:
                cut = remaining.rfind(" ", 0, self.max_chunk_chars)
                if cut <= 0:
                    cut = self.max_chunk_chars
                out.append(remaining[:cut].strip())
                remaining = remaining[cut:].strip()
            buf = remaining
        if buf:
            out.append(buf)
        return out

    def _split_by_size(self, text: str, max_chars: int) -> list[str]:
        from .text_utils import split_sentences

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            return []

        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            if len(paragraph) <= max_chars:
                current = paragraph
                continue

            sentence_buffer = ""
            for sentence in split_sentences(paragraph):
                sentence_candidate = (
                    f"{sentence_buffer} {sentence}".strip() if sentence_buffer else sentence
                )
                if len(sentence_candidate) <= max_chars:
                    sentence_buffer = sentence_candidate
                    continue
                if sentence_buffer:
                    chunks.append(sentence_buffer)
                sentence_buffer = sentence
            current = sentence_buffer

        if current:
            chunks.append(current)
        return chunks

    def _split_by_tokens(self, text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
        tokenizer = self.llm_tokenizer
        if tokenizer is None:
            return self._split_by_size(text, self.llm_passage_chars)

        token_ids = tokenizer.encode(text, add_special_tokens=False)
        if not token_ids:
            return []

        chunks: list[str] = []
        start = 0
        step = max(max_tokens - max(overlap_tokens, 0), 1)
        while start < len(token_ids):
            end = min(start + max_tokens, len(token_ids))
            window_ids = token_ids[start:end]
            chunk_text = tokenizer.decode(window_ids, skip_special_tokens=True).strip()
            if chunk_text:
                chunks.append(chunk_text)
            if end >= len(token_ids):
                break
            start += step
        return chunks
