"""RAG evaluation: MRR (retrieval) + BERTScore (generation quality).

Usage
-----
  # Run fresh evaluation against a live service (slow — calls LLM per question):
  python scripts/evaluate_rag.py [--file PATH] [--url URL] [--limit N] [--checkpoint PATH]

  # Compute metrics only from a previously saved results JSONL (fast):
  python scripts/evaluate_rag.py --results-only PATH

Metrics
-------
MRR (Mean Reciprocal Rank)
  For each question the service is called via /api/v1/query with include_sources=True.
  Retrieved source chunks are ranked 1..top_k. A chunk is "relevant" when the
  reference answer text has a keyword overlap ≥ min_overlap_ratio with the chunk.
  Reciprocal Rank = 1 / rank_of_first_relevant_chunk  (0 if none found in top-k).
  MRR = mean(RR) over all questions.
  Hit@1, Hit@3 also reported.

BERTScore
  Uses the bert-score library (default model: microsoft/deberta-xlarge-mnli or
  roberta-large depending on availability) to compute F1 between the generated
  answer and the reference answer from store_qna.jsonl.
  Reports mean Precision, Recall, F1 across all evaluated questions.

Output
------
  Prints a summary table and saves a detailed JSONL results file.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_QNA = Path(__file__).resolve().parents[3] / "knowledge-base" / "store_qna.jsonl"
DEFAULT_QUERY_URL = "http://127.0.0.1:8020/api/v1/query"
DEFAULT_CHAT_URL = "http://127.0.0.1:8020/v1/chat/completions"
HEALTH_URL = "http://127.0.0.1:8020/health"

NO_PROXY = {"http": "", "https": ""}

CHROMA_PATH = BASE_DIR / "storage" / "vector_db"
CHROMA_COLLECTION = "smart-kiosk-assistant-bge-large"
EMBED_MODEL_NAME = "BAAI/bge-large-en-v1.5"
RERANKER_MODEL_NAME = "BAAI/bge-reranker-base"
# Pull this many ANN candidates before reranking. Mirrors retrieval.fetch_k
# in config.yaml so the eval matches what the service does at runtime.
LOCAL_RETRIEVER_ANN_K = 5

SERVICE_START_CMD = (
    "source /home/intel/udit-ws/kiosk/new_audio_analyzer/.venv-1/bin/activate && "
    "cd /home/intel/udit-ws/kiosk/new_audio_analyzer/proof-of-concepts/rag-service && "
    "python main.py >> /tmp/rag-service.log 2>&1"
)

# Lazy-initialised local retriever (embedding model + chromadb collection)
_local_retriever: dict | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Service restart helper
# ─────────────────────────────────────────────────────────────────────────────

def restart_service() -> bool:
    """Kill any running service process and start a fresh one. Returns True when healthy."""
    subprocess.run(["pkill", "-f", "python main.py"], capture_output=True)
    time.sleep(3)
    subprocess.Popen(
        ["bash", "-c", SERVICE_START_CMD],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):        # up to ~80s
        try:
            r = requests.get(HEALTH_URL, timeout=3, proxies=NO_PROXY)
            if r.status_code == 200:
                print("  [restart] Service is healthy.")
                return True
        except Exception:
            pass
        time.sleep(2)
    print("  [restart] ERROR: service did not become healthy within 80s.")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Local chromadb retrieval (no LLM — for MRR computation)
# ─────────────────────────────────────────────────────────────────────────────

def _init_local_retriever() -> bool:
    """Load embedding model + chromadb collection (and optional reranker) once.
    Returns True on success."""
    global _local_retriever
    if _local_retriever is not None:
        return True
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
        print(f"[LocalRetriever] Loading {EMBED_MODEL_NAME} + chromadb…")
        embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        coll = client.get_collection(CHROMA_COLLECTION)
        reranker = None
        try:
            from sentence_transformers import CrossEncoder
            print(f"[LocalRetriever] Loading reranker {RERANKER_MODEL_NAME}…")
            reranker = CrossEncoder(RERANKER_MODEL_NAME, device="cpu", max_length=512)
        except Exception as exc:  # noqa: BLE001
            print(f"[LocalRetriever] Reranker unavailable ({exc}); falling back to ANN-only ranking.")
        _local_retriever = {"embed": embed_model, "coll": coll, "reranker": reranker}
        suffix = " + reranker" if reranker is not None else ""
        print(f"[LocalRetriever] Ready. Collection has {coll.count()} docs.{suffix}")
        return True
    except Exception as exc:
        print(f"[LocalRetriever] Init failed: {exc}")
        return False


def get_rr_local(question: str, reference: str, top_k: int = 6) -> float:
    """Reciprocal rank via direct chromadb query + optional cross-encoder
    rerank — no service LLM needed. Mirrors the rag-service retrieval flow:
    ANN over-fetch (LOCAL_RETRIEVER_ANN_K) → rerank → keep top_k."""
    if not _local_retriever:
        return 0.0
    try:
        embed_model = _local_retriever["embed"]
        coll = _local_retriever["coll"]
        reranker = _local_retriever.get("reranker")
        qemb = embed_model.encode(question, normalize_embeddings=True)
        ann_k = max(top_k, LOCAL_RETRIEVER_ANN_K)
        res = coll.query(query_embeddings=[qemb.tolist()], n_results=ann_k, include=["documents"])
        docs = res["documents"][0]
        if reranker is not None and len(docs) > 1:
            scores = reranker.predict(
                [(question, d) for d in docs],
                batch_size=16, show_progress_bar=False, convert_to_numpy=True,
            )
            order = sorted(range(len(docs)), key=lambda i: float(scores[i]), reverse=True)
            docs = [docs[i] for i in order[:top_k]]
        else:
            docs = docs[:top_k]
        sources = [{"content": d} for d in docs]
        return reciprocal_rank(sources, reference)
    except Exception as exc:
        print(f"    [local_rr] WARN: {exc}")
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────

def ask_chat(url: str, question: str, timeout: float) -> str:
    payload = {
        "model": "smart-kiosk-rag",
        "messages": [{"role": "user", "content": question}],
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=timeout, proxies=NO_PROXY)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def ask_query_with_sources(
    url: str, question: str, timeout: float
) -> tuple[str, list[dict]]:
    """Call /api/v1/query (SSE), return (generated_answer, ranked_sources).

    sources is a list of dicts with at least "source" and optionally "content"
    keys, in the order returned by the service (highest-rank first).
    """
    payload = {
        "transcription": question,
        "include_sources": True,
        "top_k": 6,
    }
    resp = requests.post(
        url, json=payload, timeout=timeout, stream=True, proxies=NO_PROXY
    )
    resp.raise_for_status()

    tokens: list[str] = []
    sources: list[dict] = []

    for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line or not raw_line.startswith("data:"):
            continue
        payload_str = raw_line[5:].strip()
        if payload_str == "[DONE]":
            break
        try:
            event = json.loads(payload_str)
        except json.JSONDecodeError:
            continue

        if "token" in event:
            tokens.append(event["token"])
        elif event.get("event") == "sources":
            sources = event.get("sources", [])

    answer = "".join(tokens).strip()
    return answer, sources


# ─────────────────────────────────────────────────────────────────────────────
# Relevance judging for MRR
# ─────────────────────────────────────────────────────────────────────────────

def _token_set(text: str) -> set[str]:
    """Lowercase alphabetic tokens, min length 3."""
    return {t.lower() for t in re.findall(r"[a-zA-Z0-9₹%\-\.]+", text) if len(t) >= 3}


def chunk_is_relevant(chunk_content: str, reference_answer: str, min_overlap: float = 0.25) -> bool:
    """True if enough reference-answer tokens appear in the chunk."""
    ref_tokens = _token_set(reference_answer)
    if not ref_tokens:
        return False
    chunk_tokens = _token_set(chunk_content)
    overlap = len(ref_tokens & chunk_tokens) / len(ref_tokens)
    return overlap >= min_overlap


def reciprocal_rank(sources: list[dict], reference: str) -> float:
    """Return 1/rank of first relevant source, or 0 if none relevant."""
    for rank, src in enumerate(sources, start=1):
        content = src.get("content", src.get("source", ""))
        if chunk_is_relevant(content, reference):
            return 1.0 / rank
    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# BERTScore computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_bert_scores(
    candidates: list[str], references: list[str], batch_size: int = 32
) -> dict[str, float]:
    """Compute semantic similarity using locally cached BAAI/bge-large-en-v1.5.

    Primary: sentence_transformers cosine similarity (works fully offline).
    Fallback: bert_score library with explicit num_layers (bypasses model registry).
    """
    valid = [(c, r) for c, r in zip(candidates, references) if r.strip() and c.strip()]
    if not valid:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "n": 0}
    cands, refs = zip(*valid)

    # ── Primary: sentence_transformers cosine similarity ──────────────────
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
        print(f"\n[SemanticSim] Encoding {len(cands)} pairs with {EMBED_MODEL_NAME}…")
        model = SentenceTransformer(EMBED_MODEL_NAME)
        cand_embs = model.encode(list(cands), batch_size=batch_size, normalize_embeddings=True, show_progress_bar=True)
        ref_embs  = model.encode(list(refs),  batch_size=batch_size, normalize_embeddings=True, show_progress_bar=True)
        sims = (cand_embs * ref_embs).sum(axis=1).tolist()  # cosine sim (already L2-normalised)
        mean_sim = float(sum(sims) / len(sims))
        print(f"[SemanticSim] Done. Mean cosine similarity={mean_sim:.4f}")
        return {
            "model": EMBED_MODEL_NAME,
            "metric": "cosine_similarity",
            "precision": mean_sim,
            "recall": mean_sim,
            "f1": mean_sim,
            "n": len(cands),
        }
    except Exception as exc:
        print(f"[SemanticSim] Failed: {exc}. Trying bert_score fallback…")

    # ── Fallback: bert_score with explicit num_layers (bypasses registry) ──
    try:
        from bert_score import score as bert_score_fn  # type: ignore
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        # (model_type, lang, num_layers) — num_layers bypasses model2layers registry
        _CANDIDATE_MODELS = [
            ("BAAI/bge-large-en-v1.5", "en", 17),
            ("BAAI/bge-base-en-v1.5", "en", 9),
            ("BAAI/bge-large-en", "en", 17),
        ]
        for model_type, lang, num_layers in _CANDIDATE_MODELS:
            print(f"[BERTScore] Trying {model_type} (num_layers={num_layers})…")
            try:
                P, R, F1 = bert_score_fn(
                    list(cands), list(refs),
                    lang=lang, model_type=model_type, num_layers=num_layers,
                    batch_size=batch_size, verbose=False,
                )
                return {
                    "model": model_type,
                    "metric": "bert_score",
                    "precision": float(P.mean()),
                    "recall": float(R.mean()),
                    "f1": float(F1.mean()),
                    "n": len(cands),
                }
            except Exception as exc:
                print(f"[BERTScore] {model_type} failed: {exc}")
    except ImportError:
        print("[BERTScore] bert_score not installed.")

    return {"error": "All similarity computation methods failed"}


# ─────────────────────────────────────────────────────────────────────────────
# Main evaluation loop
# ─────────────────────────────────────────────────────────────────────────────

def run_evaluation(args: argparse.Namespace) -> int:
    qna_path = Path(args.file)
    if not qna_path.exists():
        print(f"ERROR: QnA file not found: {qna_path}", file=sys.stderr)
        return 2

    items = []
    with qna_path.open(encoding="utf-8") as fh:
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

    # Load checkpoint if resuming
    checkpoint_path = Path(args.checkpoint) if args.checkpoint else qna_path.with_suffix(".eval_checkpoint.jsonl")
    done_ids: set = set()
    checkpoint_records: list[dict] = []
    if checkpoint_path.exists():
        with checkpoint_path.open(encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line.strip())
                done_ids.add(rec["id"])
                checkpoint_records.append(rec)
        print(f"Resuming from checkpoint: {len(done_ids)} already done.")

    pending = [it for it in items if it["id"] not in done_ids]
    print(f"Evaluating {len(pending)} / {len(items)} questions against {args.chat_url}")

    # Initialise local retriever (chromadb + embedding model) once before the loop
    if not _init_local_retriever():
        print("WARNING: Local retriever unavailable — MRR will be 0 for all questions.")

    all_records = list(checkpoint_records)
    cp_fh = checkpoint_path.open("a", encoding="utf-8")

    for i, item in enumerate(pending, 1):
        qid = item["id"]
        question = item["question"]
        reference = item.get("answer", "")
        nature = item.get("nature", "")

        elapsed_chat = 0.0
        elapsed_query = 0.0
        generated = ""
        sources: list[dict] = []
        rr = 0.0
        error = ""

        # ── generation via chat endpoint (single LLM call) ─────────────────
        # NOTE: We do NOT call the /api/v1/query endpoint here — it triggers a
        # second full LLM generation which doubles GPU load and causes SIGSEGV
        # crashes on the iGPU. MRR is computed via direct chromadb lookup below.
        for _attempt in range(3):
            t0 = time.monotonic()
            try:
                generated = ask_chat(args.chat_url, question, args.timeout)
                elapsed_chat = time.monotonic() - t0
                error = ""
                break
            except requests.exceptions.ConnectionError as exc:
                elapsed_chat = time.monotonic() - t0
                print(f"  [{i}/{len(pending)}] Q{qid} ConnectionError (attempt {_attempt + 1}/3)")
                if _attempt < 2 and args.auto_restart:
                    print("  [restart] Service appears down — restarting…")
                    if restart_service():
                        continue
                error = str(exc)
                print(f"  [{i}/{len(pending)}] Q{qid} ERROR (chat): {exc}")
                break
            except Exception as exc:  # noqa: BLE001
                elapsed_chat = time.monotonic() - t0
                error = str(exc)
                print(f"  [{i}/{len(pending)}] Q{qid} ERROR (chat): {exc}")
                break

        # ── retrieval for MRR via local chromadb (no LLM) ─────────────────
        elapsed_query = 0.0
        if not error and reference:
            t1 = time.monotonic()
            rr = get_rr_local(question, reference, top_k=6)
            elapsed_query = time.monotonic() - t1

        record = {
            "id": qid,
            "question": question,
            "reference": reference,
            "nature": nature,
            "generated": generated,
            "rr": round(rr, 4),
            "elapsed_chat": round(elapsed_chat, 2),
            "elapsed_query": round(elapsed_query, 2),
            "error": error,
        }
        all_records.append(record)
        cp_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        cp_fh.flush()

        status = f"RR={rr:.2f}" if reference else "no-ref"
        print(
            f"  [{i}/{len(pending)}] Q{qid} [{nature}] {elapsed_chat:.1f}s "
            f"| {status} | {question[:70]}"
        )

    cp_fh.close()

    # ── MRR metrics ─────────────────────────────────────────────────────────
    rr_values = [r["rr"] for r in all_records if r.get("reference") and not r.get("error")]
    hit1 = sum(1 for rr in rr_values if rr >= 1.0) / len(rr_values) if rr_values else 0
    hit3 = sum(1 for rr in rr_values if rr >= 1 / 3) / len(rr_values) if rr_values else 0
    mrr = sum(rr_values) / len(rr_values) if rr_values else 0

    # ── BERTScore ──────────────────────────────────────────────────────────
    bert_records = [r for r in all_records if r.get("reference") and r.get("generated") and not r.get("error")]
    candidates = [r["generated"] for r in bert_records]
    references = [r["reference"] for r in bert_records]
    bert = compute_bert_scores(candidates, references, batch_size=args.bert_batch)

    # ── Print summary ────────────────────────────────────────────────────────
    total = len(all_records)
    errors = sum(1 for r in all_records if r.get("error"))
    avg_t = sum(r["elapsed_chat"] for r in all_records) / total if total else 0

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)
    print(f"  Questions evaluated  : {total}")
    print(f"  Errors               : {errors}")
    print(f"  Avg generation time  : {avg_t:.1f}s")
    print()
    print("RETRIEVAL (MRR)")
    print(f"  MRR                  : {mrr:.4f}")
    print(f"  Hit@1                : {hit1:.4f}  ({int(hit1*len(rr_values))}/{len(rr_values)})")
    print(f"  Hit@3                : {hit3:.4f}  ({int(hit3*len(rr_values))}/{len(rr_values)})")
    print()
    print("GENERATION QUALITY (BERTScore vs reference answers)")
    if "error" in bert:
        print(f"  BERTScore error: {bert['error']}")
    else:
        print(f"  Precision            : {bert['precision']:.4f}")
        print(f"  Recall               : {bert['recall']:.4f}")
        print(f"  F1                   : {bert['f1']:.4f}  (n={bert['n']})")

    # ── Per-nature breakdown ─────────────────────────────────────────────────
    natures = sorted({r.get("nature", "unknown") for r in all_records if r.get("nature")})
    if natures:
        print()
        print("PER-NATURE BREAKDOWN (MRR)")
        for nat in natures:
            nat_records = [r for r in all_records if r.get("nature") == nat and r.get("reference") and not r.get("error")]
            if not nat_records:
                continue
            nat_rr = [r["rr"] for r in nat_records]
            nat_mrr = sum(nat_rr) / len(nat_rr)
            print(f"  {nat:<20} n={len(nat_rr):<5} MRR={nat_mrr:.4f}")

    # ── Save final results JSONL ─────────────────────────────────────────────
    output_path = qna_path.with_suffix(".eval_results.jsonl")
    with output_path.open("w", encoding="utf-8") as fh:
        for r in all_records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nDetailed results → {output_path}")

    return 0


def run_metrics_only(results_path: str) -> int:
    """Recompute BERTScore + MRR from a saved results JSONL, no LLM calls."""
    path = Path(results_path)
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 2

    records = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            records.append(json.loads(line.strip()))

    rr_values = [r["rr"] for r in records if r.get("reference") and not r.get("error")]
    mrr = sum(rr_values) / len(rr_values) if rr_values else 0
    hit1 = sum(1 for rr in rr_values if rr >= 1.0) / len(rr_values) if rr_values else 0
    hit3 = sum(1 for rr in rr_values if rr >= 1/3) / len(rr_values) if rr_values else 0

    bert_records = [r for r in records if r.get("reference") and r.get("generated") and not r.get("error")]
    bert = compute_bert_scores(
        [r["generated"] for r in bert_records],
        [r["reference"] for r in bert_records],
    )

    print(f"\nResults file: {path}  ({len(records)} records)")
    print(f"MRR={mrr:.4f}  Hit@1={hit1:.4f}  Hit@3={hit3:.4f}")
    if "error" not in bert:
        print(f"BERTScore F1={bert['f1']:.4f}  P={bert['precision']:.4f}  R={bert['recall']:.4f}  n={bert['n']}")
    else:
        print(f"BERTScore error: {bert['error']}")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", default=str(DEFAULT_QNA), help="Path to QnA JSONL")
    parser.add_argument("--chat-url", default=DEFAULT_CHAT_URL, help="Chat completions endpoint")
    parser.add_argument("--query-url", default=DEFAULT_QUERY_URL, help="Query endpoint (for MRR sources)")
    parser.add_argument("--limit", type=int, default=0, help="Max questions (0=all)")
    parser.add_argument("--start", type=int, default=0, help="Skip first N questions")
    parser.add_argument("--timeout", type=float, default=240.0, help="HTTP timeout per request (s)")
    parser.add_argument("--checkpoint", default="", help="Checkpoint JSONL path (auto-named if omitted)")
    parser.add_argument("--bert-batch", type=int, default=16, help="BERTScore batch size")
    parser.add_argument("--auto-restart", action="store_true", default=True,
                        help="Auto-restart service on ConnectionError (default: on)")
    parser.add_argument("--no-auto-restart", dest="auto_restart", action="store_false",
                        help="Disable auto-restart")
    parser.add_argument("--results-only", default="", metavar="PATH",
                        help="Recompute metrics from saved results JSONL (no LLM calls)")
    args = parser.parse_args()

    if args.results_only:
        return run_metrics_only(args.results_only)
    return run_evaluation(args)


if __name__ == "__main__":
    sys.exit(main())
