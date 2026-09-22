from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

_LINE_FULL = re.compile(
    r"Question\s*([0-9]+)\s*\|\s*((?:part_\d+\s+\d+\s*\|\s*)+)([A-Za-z]+)\s*\|\s*student:\s*(.*?)\s*\|\s*(\d+)\s*/\s*(\d+)\s*points",
    re.IGNORECASE,
)
_PART_TOKEN = re.compile(r"part_(\d+)\s+(\d+)", re.IGNORECASE)
_REASON_LINE = re.compile(r"^\s*Reason\s*[:：]\s*(.*)$", re.IGNORECASE)


def _accumulate(scores: dict[str, dict], qid: str, part: dict) -> None:
    existing = scores.get(qid)
    if existing is None:
        scores[qid] = part
        return
    existing["score"] += part["score"]
    existing["max"] += part["max"]
    if part.get("student"):
        existing["student"] = f'{existing["student"]} {part["student"]}'.strip()
    if not existing.get("type") and part.get("type"):
        existing["type"] = part["type"]


def parse_scores(text: str) -> dict[str, dict]:
    """Return parsed scores keyed by "<question_no>|<part_1>|<part_2>|...".

    Record shape:
    {type, student, score, max, question_no, part_path, part_depth, part_key}
    """
    scores: dict[str, dict] = {}
    seen_parts: set[tuple[str, tuple[int, ...]]] = set()
    pending_reason_qids: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = _LINE_FULL.match(line)
        if m:
            qid = m.group(1)
            parts_block = m.group(2)

            indexed_parts: list[tuple[int, int]] = []
            for part_match in _PART_TOKEN.finditer(parts_block):
                indexed_parts.append((int(part_match.group(1)), int(part_match.group(2))))
            if not indexed_parts:
                continue

            indexed_parts.sort(key=lambda p: p[0])
            part_path = [value for _, value in indexed_parts]
            part_tuple = tuple(indexed_parts)
            key = (qid, part_tuple)
            if key in seen_parts:
                continue
            seen_parts.add(key)

            composite_qid = f"{qid}|{'|'.join(f'{lvl}.{val}' for lvl, val in indexed_parts)}"
            _accumulate(scores, composite_qid, {
                "type": m.group(3).lower(),
                "student": m.group(4).strip(),
                "score": int(m.group(5)),
                "max": int(m.group(6)),
                "question_no": int(qid),
                "part_path": part_path,
                "part_depth": len(part_path),
                "part_key": composite_qid,
            })
            pending_reason_qids.append(composite_qid)
            continue

        reason_match = _REASON_LINE.match(line)
        if reason_match and pending_reason_qids:
            reason_text = reason_match.group(1).strip()
            for pqid in pending_reason_qids:
                if pqid in scores and reason_text:
                    scores[pqid]["reason"] = reason_text
            pending_reason_qids = []

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
    """Merge per-page score dicts into one; duplicate qids are accumulated."""
    merged: dict[str, dict] = {}
    for page_scores in pages:
        for qid, part in page_scores.items():
            _accumulate(merged, qid, dict(part))
    return merged
