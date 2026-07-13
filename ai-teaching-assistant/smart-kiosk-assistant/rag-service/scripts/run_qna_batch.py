"""Run a JSONL of {question, answer?, expected_keywords?} against the RAG service.

Usage:
    python scripts/run_qna_batch.py [--limit N] [--start N] [--file PATH] [--url URL]

QnA JSONL format — two modes supported:
  1. Keyword mode (original): {"question": "...", "expected_keywords": ["..."]}
     PASS if any keyword appears in the answer (case-insensitive substring).
  2. Reference mode (new):   {"question": "...", "answer": "<reference answer>"}
     PASS if answer is non-empty (quality checked separately by evaluate_rag.py).
     If both fields present, keyword mode takes precedence.

A record with neither field is always marked PASS (answer captured only).
Network/HTTP errors are reported as ERROR and counted separately.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests


DEFAULT_URL = "http://127.0.0.1:8020/v1/chat/completions"
DEFAULT_QNA = Path(__file__).resolve().parents[3] / "knowledge-base" / "store_qna.jsonl"


def ask(url: str, question: str, timeout: float) -> str:
    payload = {
        "model": "smart-kiosk-rag",
        "messages": [{"role": "user", "content": question}],
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def evaluate(answer: str, item: dict) -> tuple[bool, list[str], str]:
    """Return (pass, matched_keywords, mode)."""
    keywords = item.get("expected_keywords", [])
    if keywords:
        answer_lc = answer.lower()
        matched = [kw for kw in keywords if kw.lower() in answer_lc]
        return bool(matched), matched, "keyword"
    # Reference mode — PASS if the answer is non-empty
    if item.get("answer"):
        return bool(answer.strip()), [], "reference"
    return True, [], "no_eval"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=str(DEFAULT_QNA), help="Path to QnA JSONL")
    parser.add_argument("--url", default=DEFAULT_URL, help="Chat completions endpoint")
    parser.add_argument("--limit", type=int, default=0, help="Max questions to run (0 = all)")
    parser.add_argument("--start", type=int, default=0, help="Skip the first N questions")
    parser.add_argument("--timeout", type=float, default=180.0, help="HTTP timeout per request (s)")
    args = parser.parse_args()

    qna_path = Path(args.file)
    if not qna_path.exists():
        print(f"ERROR: QnA file not found: {qna_path}", file=sys.stderr)
        return 2

    items = []
    with qna_path.open("r", encoding="utf-8") as fh:
        for idx, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "id" not in rec:
                rec["id"] = idx
            items.append(rec)

    if args.start:
        items = items[args.start:]
    if args.limit:
        items = items[: args.limit]

    print(f"Running {len(items)} question(s) against {args.url}")
    print("=" * 80)

    pass_n = fail_n = err_n = 0
    durations: list[float] = []
    fails: list[dict] = []
    results_out: list[dict] = []

    for item in items:
        qid = item.get("id", "?")
        question = item["question"]
        reference = item.get("answer", "")
        keywords = item.get("expected_keywords", [])
        nature = item.get("nature", "")

        label = f"[Q{qid}]" + (f" [{nature}]" if nature else "")
        print(f"\n{label} {question}")
        if keywords:
            print(f"   expected keywords: {keywords}")
        elif reference:
            print(f"   reference: {reference[:120]}{'...' if len(reference)>120 else ''}")

        t0 = time.monotonic()
        try:
            answer = ask(args.url, question, args.timeout)
        except Exception as exc:  # noqa: BLE001
            err_n += 1
            elapsed = time.monotonic() - t0
            durations.append(elapsed)
            print(f"   ERROR after {elapsed:.1f}s: {exc}")
            fails.append({"id": qid, "question": question, "error": str(exc)})
            results_out.append({"id": qid, "question": question, "answer": "", "reference": reference, "error": str(exc), "elapsed": round(elapsed, 2)})
            continue
        elapsed = time.monotonic() - t0
        durations.append(elapsed)

        ok, matched, mode = evaluate(answer, item)
        verdict = "PASS" if ok else "FAIL"
        if ok:
            pass_n += 1
        else:
            fail_n += 1
            fails.append({"id": qid, "question": question, "answer": answer, "keywords": keywords, "reference": reference})

        print(f"   answer ({elapsed:.1f}s): {answer}")
        print(f"   {verdict} [{mode}]" + (f" | matched={matched}" if matched else ""))
        results_out.append({"id": qid, "question": question, "answer": answer, "reference": reference, "verdict": verdict, "mode": mode, "elapsed": round(elapsed, 2)})

    total = pass_n + fail_n + err_n
    avg = sum(durations) / len(durations) if durations else 0.0
    print("\n" + "=" * 80)
    print(f"SUMMARY: {pass_n}/{total} PASS | {fail_n} FAIL | {err_n} ERROR | avg={avg:.1f}s")

    # Save results JSONL for downstream evaluation
    out_file = Path(args.file).with_suffix(".results.jsonl")
    with out_file.open("w", encoding="utf-8") as fh:
        for r in results_out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Results saved → {out_file}")

    if fails:
        print("\nFailures:")
        for f in fails:
            if "error" in f:
                print(f"  Q{f['id']}: ERROR — {f['error']}")
            else:
                print(f"  Q{f['id']}: {f['question']}")
                if f.get("keywords"):
                    print(f"      expected any of: {f['keywords']}")
                    print(f"      got: {f['answer'][:200]}")
                else:
                    print(f"      got: (empty answer)")

    return 0 if fail_n == 0 and err_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
