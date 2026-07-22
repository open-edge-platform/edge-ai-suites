"""Slice a full rubric prompt down to the block for one section.

The rubric file is split on separator lines (config: separator). The first
block (scenario/intro) and the last block (output-format) are always kept; the
one middle block whose leading ordinal matches the section title's leading
ordinal is inserted between them. If nothing matches, the full prompt is used.

All patterns live in config — no section-type text is hardcoded here.
"""
from __future__ import annotations

import re
from typing import Any


def _split_blocks(text: str, separator: str) -> list[str]:
    """Split text into blocks on separator lines. Returns block strings
    (separator lines removed, surrounding blank lines trimmed)."""
    sep_re = re.compile(separator)
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if sep_re.match(line):
            if current:
                blocks.append("\n".join(current).strip("\n"))
                current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip("\n"))
    # drop empty blocks that result from consecutive separators
    return [b for b in blocks if b.strip()]


def _leading_ordinal(text: str, ordinal_pattern: re.Pattern) -> str | None:
    """Extract the leading ordinal (group 1) from a heading-like string."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = ordinal_pattern.search(line)
        return m.group(1) if m else None
    return None


def _is_header_block(block: str, marker_pattern: re.Pattern) -> bool:
    """True if a block's first non-blank line matches the header marker pattern."""
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        return bool(marker_pattern.match(line))
    return False


def extract_header_block(full_prompt: str, cfg: dict[str, Any]) -> str | None:
    """Return the header-extraction instruction block from the rubric, or None.

    The rubric is split on the same separator used for section slicing; the block
    whose first line matches `header_extract.marker_pattern` is returned with its
    marker line stripped. Returns None when no such block exists (caller then
    skips header extraction entirely).
    """
    header_cfg = cfg.get("header_extract", {})
    if not isinstance(header_cfg, dict) or not header_cfg.get("enabled", False):
        return None

    separator = header_cfg.get("separator") \
        or cfg.get("prompt_slicing", {}).get("separator", r"^\s*={5,}\s*$")
    marker = re.compile(header_cfg.get("marker_pattern", r"^\s*(?:\[HEADER\]|【卷头信息】)"))

    for block in _split_blocks(full_prompt, separator):
        if _is_header_block(block, marker):
            lines = block.splitlines()
            # drop the marker line (first non-blank line)
            for i, line in enumerate(lines):
                if line.strip():
                    return "\n".join(lines[i + 1:]).strip() or block.strip()
            return block.strip()
    return None


def slice_prompt_for_section(
    full_prompt: str,
    section_title: str,
    cfg: dict[str, Any],
) -> str:
    """Return the prompt slice for a section, or the full prompt as fallback."""
    slicing = cfg.get("prompt_slicing", {})
    if not isinstance(slicing, dict) or not slicing.get("enabled", False):
        return full_prompt

    separator = slicing.get("separator", r"^\s*={5,}\s*$")
    ordinal_pattern = re.compile(slicing.get("ordinal_pattern", r"^\s*([一二三四五六七八九十]+)"))
    keep_first = bool(slicing.get("keep_first_block", True))
    keep_last = bool(slicing.get("keep_last_block", True))

    # A header-extraction block (if any) is metadata, not a gradable section —
    # exclude it so it is never mistaken for a question block.
    header_cfg = cfg.get("header_extract", {})
    header_marker = None
    if isinstance(header_cfg, dict) and header_cfg.get("enabled", False):
        header_marker = re.compile(
            header_cfg.get("marker_pattern", r"^\s*(?:\[HEADER\]|【卷头信息】)")
        )

    blocks = _split_blocks(full_prompt, separator)
    if header_marker is not None:
        blocks = [b for b in blocks if not _is_header_block(b, header_marker)]
    if len(blocks) < 3:
        return full_prompt  # nothing meaningful to slice

    target = _leading_ordinal(section_title, ordinal_pattern)
    if not target:
        return full_prompt

    first, last = blocks[0], blocks[-1]
    middle = blocks[1:-1]

    matched = None
    for b in middle:
        if _leading_ordinal(b, ordinal_pattern) == target:
            matched = b
            break
    if matched is None:
        return full_prompt

    parts: list[str] = []
    if keep_first:
        parts.append(first)
    parts.append(matched)
    if keep_last:
        parts.append(last)
    return "\n\n".join(parts)
