"""Aggregate parsed VLM scores into a grading result.

The grading prompt is the sole basis for scoring, so results come only from
what the VLM reported per question. Objective vs subjective totals are split by
the VLM-reported question type (calculation -> subjective, else objective).
The `summary` shape stays compatible with the legacy pipeline.
"""
from __future__ import annotations

from typing import Any


def _infer_catalog(vlm: dict) -> str:
    return "subjective" if vlm.get("type") == "calculation" else "objective"


def build_result(scores: dict[str, dict]) -> dict[str, Any]:
    """Build the grading result from per-question VLM scores.

    scores: {qid: {type, student, score, max}} from result_parser.parse_scores.
    """
    questions: dict[str, dict] = {}
    obj_score = obj_max = subj_score = subj_max = 0

    for qid in sorted(scores, key=lambda x: (len(x), x)):
        vlm = scores[qid]
        catalog = _infer_catalog(vlm)
        got = int(vlm.get("score", 0))
        mx = int(vlm.get("max", 0))

        questions[qid] = {
            "catalog": catalog,
            "type": vlm.get("type", ""),
            "student_answer": vlm.get("student", ""),
            "vlm_score": got,
            "max_score": mx,
        }

        if catalog == "subjective":
            subj_score += got
            subj_max += mx
        else:
            obj_score += got
            obj_max += mx

    summary = {
        "objective_score": obj_score,
        "objective_max": obj_max,
        "subjective_score": subj_score,
        "subjective_max": subj_max,
        "total_score": obj_score + subj_score,
        "total_max": obj_max + subj_max,
    }

    return {
        "summary": summary,
        "questions": questions,
        "graded_count": len(questions),
    }
