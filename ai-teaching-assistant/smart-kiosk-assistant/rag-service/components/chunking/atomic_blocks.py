from __future__ import annotations

import re

from .text_utils import split_sentences


_LIST_LINE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")


class AtomicBlockDetector:
    """Identifies inclusive line-index ranges that must never be split
    internally: fenced code blocks, pipe tables, and bullet/numbered list runs
    of >=2 lines. Also provides utilities to snap split markers out of such
    ranges and to split text into atomic-aware units."""

    def block_ranges(self, lines: list[str]) -> list[tuple[int, int]]:
        ranges: list[tuple[int, int]] = []
        n = len(lines)
        i = 0
        in_fence = False
        fence_start = -1
        while i < n:
            stripped = lines[i].lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                if not in_fence:
                    in_fence = True
                    fence_start = i
                else:
                    ranges.append((fence_start, i))
                    in_fence = False
                i += 1
                continue
            if in_fence:
                i += 1
                continue
            if "|" in lines[i] and i + 1 < n and "|" in lines[i + 1]:
                start = i
                while i < n and "|" in lines[i] and lines[i].strip():
                    i += 1
                if i - 1 > start:
                    ranges.append((start, i - 1))
                continue
            if _LIST_LINE.match(lines[i]):
                start = i
                while i < n and (
                    _LIST_LINE.match(lines[i])
                    or (lines[i].startswith("  ") and lines[i].strip())
                ):
                    i += 1
                if i - 1 - start >= 1:
                    ranges.append((start, i - 1))
                continue
            i += 1
        if in_fence and fence_start >= 0:
            ranges.append((fence_start, n - 1))
        return ranges

    def snap_markers(self, markers: list[int], lines: list[str]) -> list[int]:
        """Move any split point that lands inside an atomic block to the
        block's start, so we never cut a table/list/code fence in half."""
        ranges = self.block_ranges(lines)
        if not ranges:
            return markers
        snapped: set[int] = set()
        for m in markers:
            for start, end in ranges:
                if start < m <= end:
                    m = start
                    break
            snapped.add(m)
        return sorted(snapped)

    def split_into_units(self, text: str) -> list[str]:
        """Atomic-aware unit splitter: treats fenced code blocks, tables, and
        list runs as single indivisible units; splits everything else into
        sentences."""
        lines = text.split("\n")
        ranges = self.block_ranges(lines)
        if not ranges:
            return split_sentences(text)

        in_block = [False] * len(lines)
        for start, end in ranges:
            for j in range(start, min(end + 1, len(lines))):
                in_block[j] = True

        units: list[str] = []
        i = 0
        while i < len(lines):
            if in_block[i]:
                start = i
                while i < len(lines) and in_block[i]:
                    i += 1
                block_text = "\n".join(lines[start:i]).strip()
                if block_text:
                    units.append(block_text)
            else:
                start = i
                while i < len(lines) and not in_block[i]:
                    i += 1
                para = "\n".join(lines[start:i]).strip()
                if para:
                    units.extend(split_sentences(para))
        return [u for u in units if u]
