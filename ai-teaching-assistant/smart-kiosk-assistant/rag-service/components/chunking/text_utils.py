from __future__ import annotations

import re

import numpy as np


def normalize_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    normalized = text.replace("\n", " ")
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", normalized)
    return [part.strip() for part in parts if part.strip()]


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    left_norm = np.linalg.norm(left)
    right_norm = np.linalg.norm(right)
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return float(np.dot(left, right) / (left_norm * right_norm))


def cleanup_chunks(chunks: list[str]) -> list[str]:
    """Collapse only spaces/tabs and excess blank lines; keep newlines so that
    tables, lists, and code blocks survive embedding."""
    cleaned: list[str] = []
    for chunk in chunks:
        if not chunk or not chunk.strip():
            continue
        c = re.sub(r"[ \t]+", " ", chunk)
        c = re.sub(r"\n{3,}", "\n\n", c)
        c = c.strip()
        if c:
            cleaned.append(c)
    return cleaned


def apply_overlap(chunks: list[str], overlap_chars: int) -> list[str]:
    """Append a sentence-boundary-aware prefix from each chunk to the next so
    retrieval gets a few sentences of context across the boundary."""
    if overlap_chars <= 0 or len(chunks) < 2:
        return chunks

    with_overlap: list[str] = [chunks[0]]
    for index in range(1, len(chunks)):
        prev = chunks[index - 1]
        current = chunks[index]
        window_size = max(overlap_chars, overlap_chars * 2)
        window = prev[-window_size:]
        boundaries = [m.end() for m in re.finditer(r"(?:[.!?]\s+|\n)", window)]
        prefix = ""
        for b in boundaries:
            candidate = window[b:].strip()
            if 0 < len(candidate) <= overlap_chars:
                prefix = candidate
                break
        if not prefix and boundaries:
            prefix = window[boundaries[-1]:].strip()
        if not prefix:
            tail = prev[-overlap_chars:]
            space = tail.find(" ")
            prefix = tail[space + 1:].strip() if space != -1 else tail.strip()
        combined = f"{prefix}\n{current}" if prefix else current
        with_overlap.append(combined.strip())
    return with_overlap
