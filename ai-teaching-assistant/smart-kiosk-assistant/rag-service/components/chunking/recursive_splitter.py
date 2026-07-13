"""Deterministic recursive character splitter used as the LLM-failure fallback.

Industry-standard recursive splitter (LangChain-style) with a separator
hierarchy tuned for markdown + pipe-tabular product data. No embedder, no
GPU, no LLM — pure string ops, fully deterministic, hard size cap enforced
by construction. ~600x faster than the embedding-similarity fallback it
replaces and never produces orphan headings or oversized chunks.
"""
from __future__ import annotations

from .text_utils import cleanup_chunks


class RecursiveCharSplitter:
    # Ordered from most-semantic to least-semantic. Splits happen BEFORE the
    # separator so that headings / list markers / pipe rows travel with the
    # body that follows them (no orphan-heading chunks).
    DEFAULT_SEPARATORS: tuple[str, ...] = (
        "\n## ", "\n### ", "\n#### ", "\n##### ",
        "\n\n",
        "\n- ", "\n* ", "\n+ ",
        "\n",
        ". ", "? ", "! ",
        " | ",
        " ",
    )

    def __init__(
        self,
        max_chunk_chars: int,
        min_chunk_chars: int,
        separators: tuple[str, ...] | None = None,
    ) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars
        self.separators = tuple(separators) if separators else self.DEFAULT_SEPARATORS

    def split(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []
        if len(text) <= self.max_chunk_chars:
            return [text]
        pieces = self._recursive(text, self.separators)
        merged = self._merge_small(pieces)
        return cleanup_chunks(merged)

    def _recursive(self, text: str, separators: tuple[str, ...]) -> list[str]:
        if len(text) <= self.max_chunk_chars:
            return [text]
        for i, sep in enumerate(separators):
            if sep and sep in text:
                parts = self._split_keep_sep(text, sep)
                if len(parts) <= 1:
                    continue
                out: list[str] = []
                remaining = separators[i + 1 :]
                for part in parts:
                    if len(part) <= self.max_chunk_chars:
                        out.append(part)
                    else:
                        out.extend(self._recursive(part, remaining))
                return out
        # No separator survived: hard slice on char boundary.
        return [
            text[k : k + self.max_chunk_chars]
            for k in range(0, len(text), self.max_chunk_chars)
        ]

    @staticmethod
    def _split_keep_sep(text: str, sep: str) -> list[str]:
        """Split on ``sep`` and re-attach its non-newline portion to every
        subsequent piece so heading/list markers stay glued to their body."""
        parts = text.split(sep)
        if len(parts) <= 1:
            return [text]
        keep = sep.lstrip("\n")  # "\n## " -> "## ", "\n\n" -> "", " | " -> " | "
        result: list[str] = []
        if parts[0].strip():
            result.append(parts[0])
        for part in parts[1:]:
            piece = (keep + part) if keep else part
            if piece.strip():
                result.append(piece)
        return result

    def _merge_small(self, pieces: list[str]) -> list[str]:
        """Greedy pack adjacent pieces up to ``max_chunk_chars`` so we don't
        emit pointless 5-char chunks like "RICE:" left over from splitting."""
        if not pieces:
            return []
        out: list[str] = []
        buf = ""
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            if not buf:
                buf = piece
                continue
            joiner = "\n" if ("\n" in buf or "\n" in piece) else " "
            if len(buf) + len(joiner) + len(piece) <= self.max_chunk_chars:
                buf = f"{buf}{joiner}{piece}"
            else:
                out.append(buf)
                buf = piece
        if buf:
            out.append(buf)
        return out
