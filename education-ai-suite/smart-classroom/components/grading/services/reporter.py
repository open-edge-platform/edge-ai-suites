from __future__ import annotations

from collections import defaultdict
from typing import Any


def _infer_catalog(vlm: dict) -> str:
    qtype = str(vlm.get("type") or "").strip().lower()
    return "subjective" if qtype == "subjective" else "objective"


def _sum_scores(children: list[dict[str, Any]]) -> tuple[int, int]:
    score = sum(int((c.get("meta") or {}).get("grading_score", 0)) for c in children)
    max_score = sum(int((c.get("meta") or {}).get("max_score", 0)) for c in children)
    return score, max_score


def _build_hierarchy(questions: dict[str, dict], grouped: dict[int, list[tuple[str, dict]]]) -> list[dict[str, Any]]:
    """Build nested questions hierarchy with per-level meta.

    Output shape (per root):
    {
      "question_no": 11,
      "meta": {"sub_question": true, "max_score": 20, "grading_score": 19},
      "questions": [...]
    }
    """

    def make_leaf(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "question_no": int(item.get("question_no", 0)),
            "sub_question_no": int(item.get("sub_question_no", 0)),
            "meta": {
                "sub_question": False,
                "max_score": int(item.get("max_score", 0)),
                "grading_score": int(item.get("vlm_score", 0)),
                "part_path": list(item.get("part_path") or []),
                "part_key": str(item.get("part_key") or ""),
                "catalog": item.get("catalog"),
                "type": item.get("type"),
            },
            "student_answer": item.get("student_answer", ""),
            "reason": item.get("reason", ""),
        }

    hierarchy: list[dict[str, Any]] = []

    for qn in sorted(grouped):
        items = grouped[qn]
        if len(items) == 1:
            only = items[0][1]
            path = list(only.get("part_path") or [])
            if path == [1]:
                hierarchy.append({
                    "question_no": qn,
                    "meta": {
                        "sub_question": False,
                        "max_score": int(only.get("max_score", 0)),
                        "grading_score": int(only.get("vlm_score", 0)),
                        "catalog": only.get("catalog"),
                        "type": only.get("type"),
                        "part_path": [],
                    },
                    "student_answer": only.get("student_answer", ""),
                    "reason": only.get("reason", ""),
                })
                continue

        root: dict[str, Any] = {
            "question_no": qn,
            "meta": {
                "sub_question": True,
                "max_score": 0,
                "grading_score": 0,
                "part_path": [],
            },
            "questions": [],
        }

        prefix_map: dict[tuple[int, ...], dict[str, Any]] = {(): root}

        for _, item in items:
            full_path = tuple(int(x) for x in (item.get("part_path") or []))
            if not full_path:
                full_path = (1,)

            for depth in range(1, len(full_path)):
                prefix = full_path[:depth]
                if prefix in prefix_map:
                    continue
                parent_prefix = full_path[:depth - 1]
                parent_node = prefix_map[parent_prefix]
                node: dict[str, Any] = {
                    "question_no": qn,
                    "sub_question_no": int(prefix[-1]),
                    "meta": {
                        "sub_question": True,
                        "max_score": 0,
                        "grading_score": 0,
                        "part_path": list(prefix),
                    },
                    "questions": [],
                }
                parent_node.setdefault("questions", []).append(node)
                prefix_map[prefix] = node

            parent = prefix_map[full_path[:-1]]
            parent.setdefault("questions", []).append(make_leaf(item))

        def finalize(node: dict[str, Any]) -> None:
            children = node.get("questions") or []
            for child in children:
                finalize(child)
            if children:
                s, m = _sum_scores(children)
                node["meta"]["grading_score"] = s
                node["meta"]["max_score"] = m

        finalize(root)
        hierarchy.append(root)

    return hierarchy


def build_result(scores: dict[str, dict]) -> dict[str, Any]:
    """Build the grading result from per-question VLM scores.

    scores: {qid: {type, student, score, max}} from result_parser.parse_scores.
    """
    questions: dict[str, dict] = {}
    question_groups: dict[str, dict] = {}
    obj_score = obj_max = subj_score = subj_max = 0

    def _sort_key(item_key: str) -> tuple[int, tuple[int, ...], str]:
        rec = scores[item_key]
        qn = int(rec.get("question_no", 0))
        part_path = tuple(int(x) for x in (rec.get("part_path") or []))
        return (qn, part_path, item_key)

    grouped: dict[int, list[tuple[str, dict]]] = defaultdict(list)

    for qid in sorted(scores, key=_sort_key):
        vlm = scores[qid]
        catalog = _infer_catalog(vlm)
        got = int(vlm.get("score", 0))
        mx = int(vlm.get("max", 0))
        qn = int(vlm.get("question_no", 0))
        part_path = [int(x) for x in (vlm.get("part_path") or [])]
        part_depth = int(vlm.get("part_depth", len(part_path)))
        part_key = str(vlm.get("part_key") or qid)

        questions[qid] = {
            "question_no": qn,
            "part_path": part_path,
            "part_depth": part_depth,
            "part_key": part_key,
            "catalog": catalog,
            "type": vlm.get("type", ""),
            "student_answer": vlm.get("student", ""),
            "reason": vlm.get("reason", ""),
            "vlm_score": got,
            "max_score": mx,
        }
        grouped[qn].append((qid, questions[qid]))

        if catalog == "subjective":
            subj_score += got
            subj_max += mx
        else:
            obj_score += got
            obj_max += mx

    for qn in sorted(grouped):
        items = grouped[qn]
        group_score = sum(int(item[1].get("vlm_score", 0)) for item in items)
        group_max = sum(int(item[1].get("max_score", 0)) for item in items)
        question_groups[str(qn)] = {
            "question_no": qn,
            "score": group_score,
            "max_score": group_max,
            "part_count": len(items),
            "items": [item[0] for item in items],
        }

    questions_hierarchy = _build_hierarchy(questions, grouped)

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
        "questions_hierarchy": questions_hierarchy,
        "graded_count": len(questions),
    }
