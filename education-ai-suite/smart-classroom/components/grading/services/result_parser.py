"""Parse VLM free-text grading output into structured per-question results.

Expected primary format (one question per two lines):
    Question 1 | choice | student: A | 4/4 points
    Reason: ...
Falls back to the simpler "Question 1: 4/10 points" if the model omits the
type / student fields.
"""
from __future__ import annotations

import re

# "Question 1 | choice | student: A | 4/4 points"
_LINE_FULL = re.compile(
    r"Question\s*([0-9]+)\s*\|\s*([A-Za-z]+)\s*\|\s*student:\s*(.*?)\s*\|\s*(\d+)\s*/\s*(\d+)",
    re.IGNORECASE,
)
# Fallback: "Question 1: 4/10 points"
_LINE_SIMPLE = re.compile(
    r"Question\s*([0-9]+)\s*[:：]\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE
)


def parse_scores(text: str) -> dict[str, dict]:
    """Return {qid: {type, student, score, max}} parsed from model output."""
    scores: dict[str, dict] = {}
    for m in _LINE_FULL.finditer(text):
        scores[m.group(1)] = {
            "type": m.group(2).lower(),
            "student": m.group(3).strip(),
            "score": int(m.group(4)),
            "max": int(m.group(5)),
        }
    for m in _LINE_SIMPLE.finditer(text):
        qid = m.group(1)
        if qid not in scores:
            scores[qid] = {
                "type": "",
                "student": "",
                "score": int(m.group(2)),
                "max": int(m.group(3)),
            }
    return scores


def merge_page_scores(pages: list[dict[str, dict]]) -> dict[str, dict]:
    """Merge per-page score dicts into one; later pages win on duplicate qids."""
    merged: dict[str, dict] = {}
    for page_scores in pages:
        merged.update(page_scores)
    return merged
