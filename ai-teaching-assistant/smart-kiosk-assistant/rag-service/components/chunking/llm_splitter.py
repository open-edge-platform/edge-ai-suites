from __future__ import annotations

import json
import logging
import re
import time
from typing import Callable

from .atomic_blocks import AtomicBlockDetector


logger = logging.getLogger(__name__)


class LLMMarkerSplitter:
    """LLM-driven semantic splitter. Numbers each line of a passage, asks the
    LLM for an integer array of line indices that should START a new chunk,
    then slices the passage at those points after snapping markers out of any
    atomic block (lists/tables/code fences)."""

    # Marker-only output: a JSON integer array. ~50-100 tokens regardless of
    # passage size — no OOM risk.
    MARKER_MAX_TOKENS = 256

    def __init__(
        self,
        llm_text_generator: Callable[[str, int | None, float | None], str],
        atomic_detector: AtomicBlockDetector,
        min_chunk_chars: int,
        max_chunk_chars: int,
    ) -> None:
        self.llm_text_generator = llm_text_generator
        self.atomic_detector = atomic_detector
        self.min_chunk_chars = min_chunk_chars
        self.max_chunk_chars = max_chunk_chars

    def split_passage(
        self,
        passage: str,
        profile: dict,
        passage_log_tag: str = "",
    ) -> list[str] | None:
        """Returns chunks on success, or ``None`` if the LLM produced no usable
        markers (caller should fall back to an embedding-based splitter)."""
        lines, numbered = self._number_lines(passage)
        prompt = self._build_marker_prompt(numbered, profile, len(lines))
        t0 = time.monotonic()
        try:
            raw = self.llm_text_generator(prompt, self.MARKER_MAX_TOKENS, 0.0)
            elapsed = time.monotonic() - t0
            logger.info(
                "[CHUNKER] %s LLM markers (%.1fs, %d chars): %r",
                passage_log_tag, elapsed, len(raw), raw[:400],
            )
            markers = self._parse_line_markers(raw, len(lines))
            if not markers:
                logger.warning(
                    "[CHUNKER] %s no valid markers parsed (%.1fs)", passage_log_tag, elapsed,
                )
                return None
            markers = self.atomic_detector.snap_markers(markers, lines)
            chunks = self._split_by_line_markers(lines, markers)
            logger.info(
                "[CHUNKER] %s marker split → %d chunks | starts=%s",
                passage_log_tag, len(chunks), markers,
            )
            return chunks
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - t0
            logger.warning(
                "[CHUNKER] %s LLM error after %.1fs (%s)", passage_log_tag, elapsed, exc,
            )
            return None

    # ── prompt construction ──────────────────────────────────────────

    def _build_marker_prompt(self, numbered_text: str, profile: dict, n_lines: int) -> str:
        example = self._domain_example(profile.get("domain", "generic"))
        return (
            f"You are chunking a {profile['domain']} document for a RAG knowledge-base.\n"
            f"Document structure: {profile['structure']}\n"
            f"Chunking guidance: {profile['split_guidance']}\n\n"
            "Each line below is labeled [N]. Identify which line numbers should START a new knowledge chunk.\n\n"
            "Rules:\n"
            "- Split where the topic, section, or entity changes meaningfully\n"
            f"- Target chunk size: {self.min_chunk_chars}\u2013{self.max_chunk_chars} characters of content\n"
            "- NEVER split inside a numbered list, bullet list, pipe-delimited table, or fenced code block; split BEFORE such a block begins\n"
            "- Keep tightly related lines (a heading and the lines that describe it, an item and its price/options) together\n"
            "- Return ONLY a JSON integer array, nothing else. Example: [0, 12, 28, 45]\n"
            "- Do NOT reproduce any text from the document\n\n"
            f"{example}"
            f"NUMBERED TEXT ({n_lines} lines):\n{numbered_text}"
        )

    @staticmethod
    def _domain_example(domain: str) -> str:
        d = (domain or "").lower()
        if "restaurant" in d or "qsr" in d or "food" in d:
            return (
                "Example for a QSR menu: each menu category or item starts a new chunk; "
                "never split between an item, its price, its description, or its option list.\n\n"
            )
        if "retail" in d or "store" in d or "commerce" in d:
            return (
                "Example for retail: each product, policy, or service starts a new chunk; "
                "keep hours tables, return policies, and shipping tables intact.\n\n"
            )
        if "bank" in d:
            return (
                "Example for banking: each account type, fee schedule, or policy starts a new chunk; "
                "keep fee tables intact.\n\n"
            )
        return ""

    # ── marker parsing ───────────────────────────────────────────────

    @staticmethod
    def _number_lines(text: str) -> tuple[list[str], str]:
        lines = text.split("\n")
        numbered = "\n".join(f"[{i}] {line}" for i, line in enumerate(lines))
        return lines, numbered

    @staticmethod
    def _parse_line_markers(raw: str, n_lines: int) -> list[int]:
        match = re.search(r"\[[\d,\s]+\]", raw)
        if match:
            try:
                parsed = json.loads(match.group(0))
                valid = sorted({int(x) for x in parsed if 0 <= int(x) < n_lines})
                if valid:
                    return valid
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        nums = [int(m) for m in re.findall(r"\b(\d+)\b", raw) if 0 <= int(m) < n_lines]
        valid = sorted(set(nums))
        return valid if len(valid) >= 2 else []

    @staticmethod
    def _split_by_line_markers(lines: list[str], start_lines: list[int]) -> list[str]:
        if not start_lines or start_lines[0] != 0:
            start_lines = [0] + list(start_lines)
        start_lines = sorted(set(start_lines))
        chunks: list[str] = []
        for i, start in enumerate(start_lines):
            end = start_lines[i + 1] if i + 1 < len(start_lines) else len(lines)
            chunk = "\n".join(lines[start:end]).strip()
            if chunk:
                chunks.append(chunk)
        return chunks
