from __future__ import annotations

import re
from typing import Any


def _select_scalar_by_language(value: Any, language: str) -> str | None:
    if isinstance(value, dict):
        return value.get(language)
    if isinstance(value, str):
        return value
    return None


def _markers(cfg: dict[str, Any], language: str) -> dict[str, re.Pattern]:
    raw = ((cfg.get("rubric_markers") or {}).get(language)) or {}
    return {name: re.compile(pat) for name, pat in raw.items() if isinstance(pat, str)}


def _parse_marked_blocks(full_prompt: str, markers: dict[str, re.Pattern]) -> list[dict]:
    def kind_of(line: str) -> str | None:
        for name, pat in markers.items():
            if pat.match(line):
                return name
        return None

    blocks: list[dict] = []
    current: dict | None = None
    for line in full_prompt.splitlines():
        k = kind_of(line)
        if k is not None:
            if current is not None:
                current["text"] = "\n".join(current["lines"]).strip("\n")
                blocks.append(current)
            title = markers[k].sub("", line, count=1).strip()
            current = {"kind": k, "title": title, "lines": []}
        elif current is not None:
            current["lines"].append(line)
    if current is not None:
        current["text"] = "\n".join(current["lines"]).strip("\n")
        blocks.append(current)
    return blocks


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


def extract_header_block(full_prompt: str, cfg: dict[str, Any], language: str = "en") -> str | None:
    """Return the exam-info (header) instruction block from the rubric, or None."""
    header_cfg = cfg.get("header_extract", {})
    if not isinstance(header_cfg, dict) or not header_cfg.get("enabled", False):
        return None

    markers = _markers(cfg, language)
    if "exam_info" in markers:
        for block in _parse_marked_blocks(full_prompt, markers):
            if block["kind"] == "exam_info":
                return block["text"] or None
        return None

    separator = header_cfg.get("separator") \
        or cfg.get("prompt_slicing", {}).get("separator", r"^\s*={5,}\s*$")
    marker = re.compile(header_cfg.get("marker_pattern", r"^\s*(?:\[HEADER\]|【卷头信息】)"))
    for block in _split_blocks(full_prompt, separator):
        if _is_header_block(block, marker):
            lines = block.splitlines()
            for i, line in enumerate(lines):
                if line.strip():
                    return "\n".join(lines[i + 1:]).strip() or block.strip()
            return block.strip()
    return None


def _slice_by_markers(
    full_prompt: str,
    section_title: str,
    markers: dict[str, re.Pattern],
    ordinal_pattern: re.Pattern,
) -> str:
    blocks = _parse_marked_blocks(full_prompt, markers)
    context = next((b["text"] for b in blocks if b["kind"] == "context"), None)
    output = next((b["text"] for b in blocks if b["kind"] == "output"), None)

    target = _leading_ordinal(section_title, ordinal_pattern)
    matched = None
    if target:
        for b in blocks:
            if b["kind"] == "section" and _leading_ordinal(b["title"], ordinal_pattern) == target:
                matched = f'{b["title"]}\n{b["text"]}'.strip()
                break

    if matched is None:
        return full_prompt

    parts = [p for p in (context, matched, output) if p]
    return "\n\n".join(parts)


def slice_prompt_for_section(
    full_prompt: str,
    section_title: str,
    cfg: dict[str, Any],
    language: str = "en",
) -> str:
    """Return the prompt slice for a section, or the full prompt as fallback."""
    slicing = cfg.get("prompt_slicing", {})
    if not isinstance(slicing, dict) or not slicing.get("enabled", False):
        return full_prompt

    ordinal_pattern = re.compile(
        _select_scalar_by_language(slicing.get("ordinal_pattern"), language)
        or r"^\s*([一二三四五六七八九十]+)"
    )

    markers = _markers(cfg, language)
    if "section" in markers:
        return _slice_by_markers(full_prompt, section_title, markers, ordinal_pattern)

    separator = slicing.get("separator", r"^\s*={5,}\s*$")
    keep_first = bool(slicing.get("keep_first_block", True))
    keep_last = bool(slicing.get("keep_last_block", True))

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
