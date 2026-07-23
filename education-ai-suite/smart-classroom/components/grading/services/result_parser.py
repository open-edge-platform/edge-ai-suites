"""Parse VLM free-text grading output into structured per-question results.

Expected primary format (one question per two lines):
    Question 1 | choice | student: A | 4/4 points
    Reason: ...
Falls back to the simpler "Question 1: 4/10 points" if the model omits the
type / student fields.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

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


_HEADER_KEYS = ("paper_title", "subject", "student_name", "class_name", "exam_number")

_HEADER_ALIASES_DEFAULT = {
    "paper_title": ("paper_title", "title", "paper", "exam_title"),
    "subject": ("subject",),
    "student_name": ("student_name", "name"),
    "class_name": ("class_name", "class"),
    "exam_number": ("exam_number", "exam_id", "exam_no", "admission_number", "student_id"),
}


def _load_header_aliases() -> dict[str, tuple[str, ...]]:
    try:
        cfg_path = Path(__file__).resolve().parents[1] / "config.yaml"
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        aliases = (raw.get("section_split") or {}).get("header_aliases") or {}
        if isinstance(aliases, dict):
            return {k: tuple(v) for k, v in aliases.items() if isinstance(v, list)}
    except Exception:
        pass
    return _HEADER_ALIASES_DEFAULT


_WRAPPER_KEYS = ("header", "data", "result", "info")


def _flatten_dict(obj: dict) -> dict:
    """Flatten one level of nesting (e.g. a wrapping "header"/"data" object).

    Nested dict values are merged into the top level; shallow keys win on clash.
    A wrapper key whose value is a bare string (e.g. {"header": "<paper title>"})
    is treated as the paper title.
    """
    flat: dict[str, Any] = {}
    for k, v in obj.items():
        if isinstance(v, dict):
            for nk, nv in v.items():
                flat.setdefault(nk, nv)
        elif isinstance(v, str) and str(k).lower() in _WRAPPER_KEYS:
            flat.setdefault("paper_title", v)
        else:
            flat.setdefault(k, v)
    return flat


def parse_header_info(text: str) -> dict[str, Any]:
    """Extract the header JSON object from a VLM reply.

    Tolerates code fences, surrounding prose, a wrapping object (e.g. "header"),
    and key-name aliases. Returns the five canonical keys (missing/blank -> None);
    all-None if nothing parseable is found.
    """
    empty = {k: None for k in _HEADER_KEYS}
    if not text:
        return empty

    obj = None
    try:
        obj = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
            except Exception:
                obj = None
    if not isinstance(obj, dict):
        return empty

    flat = _flatten_dict(obj)
    lower = {str(k).lower(): v for k, v in flat.items()}

    out = dict(empty)
    for canonical, aliases in _load_header_aliases().items():
        for alias in aliases:
            v = lower.get(alias.lower())
            if isinstance(v, str):
                v = v.strip()
            if v:
                out[canonical] = v
                break
    return out


def merge_page_scores(pages: list[dict[str, dict]]) -> dict[str, dict]:
    """Merge per-page score dicts into one; later pages win on duplicate qids."""
    merged: dict[str, dict] = {}
    for page_scores in pages:
        merged.update(page_scores)
    return merged
