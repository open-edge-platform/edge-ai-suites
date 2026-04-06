# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from collections import defaultdict
from pathlib import Path

import math

import torch
from optimum.intel import OVModelForSequenceClassification
from transformers import AutoTokenizer

logger = logging.getLogger(__name__)

RRF_K = 60  # RRF constant — higher means scores drop off more slowly with rank, increasing diversity


def _flatten_chroma_results(chroma_results: dict) -> list[dict]:
    """Convert ChromaDB nested result format into a flat list of dicts."""
    ids = chroma_results.get("ids", [[]])[0]
    metas = chroma_results.get("metadatas", [[]])[0]
    dists = chroma_results.get("distances", [[]])[0]
    return [
        {"id": ids[i], "distance": dists[i], "meta": metas[i]}
        for i in range(len(ids))
    ]


class PostProcessor:
    """Post-processes retrieval results: video dedup, document reranking, slot allocation."""

    def __init__(self, reranker_model: str, device: str = "CPU",
                 dedup_time_threshold: float = 5.0, overfetch_multiplier: int = 3):
        self.dedup_time_threshold = dedup_time_threshold
        self.overfetch_multiplier = overfetch_multiplier

        local_path = Path(os.getcwd()).parent / "models" / "openvino" / reranker_model
        if local_path.exists():
            logger.info(f"Loading reranker OV IR from {local_path}")
            self.tokenizer = AutoTokenizer.from_pretrained(str(local_path))
            self.reranker_model = OVModelForSequenceClassification.from_pretrained(str(local_path), device=device)
        else:
            logger.info(f"Converting reranker model {reranker_model} to OV IR and saving to {local_path}")
            self.tokenizer = AutoTokenizer.from_pretrained(reranker_model)
            self.reranker_model = OVModelForSequenceClassification.from_pretrained(reranker_model, export=True, device=device)
            local_path.mkdir(parents=True, exist_ok=True)
            self.tokenizer.save_pretrained(str(local_path))
            self.reranker_model.save_pretrained(str(local_path))
        logger.info(f"Reranker model '{reranker_model}' loaded successfully on device '{device}'.")


    def process_text_query_results(
        self, query: str, visual_results: dict, doc_results: dict, top_k: int,
    ) -> dict:
        """Full post-processing for text queries: dedup → rerank → allocate slots."""
        visual_flat = _flatten_chroma_results(visual_results)
        doc_flat = _flatten_chroma_results(doc_results)
        logger.debug("[PostProcessor] Text query: %r | visual candidates: %d | doc candidates: %d | top_k: %d",
                     query, len(visual_flat), len(doc_flat), top_k)

        visual_deduped = self._dedup_video_frames(visual_flat)
        logger.debug("[PostProcessor] After dedup: %d visual results (removed %d)",
                     len(visual_deduped), len(visual_flat) - len(visual_deduped))

        doc_reranked = self._rerank_documents(query, doc_flat)

        groups = {}
        if visual_deduped:
            groups["visual"] = visual_deduped
        if doc_reranked:
            groups["document"] = doc_reranked

        merged = self._allocate_slots(groups, top_k)
        self._compute_percentage_scores(merged)
        logger.debug("[PostProcessor] Final merged results: %d", len(merged))
        return self._to_chroma_format(merged)

    def process_image_query_results(
        self, visual_results: dict, top_k: int,
    ) -> dict:
        """Post-processing for image queries: dedup only."""
        visual_flat = _flatten_chroma_results(visual_results)
        logger.debug("[PostProcessor] Image query | visual candidates: %d | top_k: %d",
                     len(visual_flat), top_k)
        deduped = self._dedup_video_frames(visual_flat)
        logger.debug("[PostProcessor] After dedup: %d visual results (removed %d)",
                     len(deduped), len(visual_flat) - len(deduped))
        trimmed = deduped[:top_k]
        # Assign RRF scores by rank so distances field is consistent with text query path (higher = better)
        for rank, item in enumerate(trimmed):
            item["rrf_score"] = 1.0 / (RRF_K + rank)
        self._compute_percentage_scores(trimmed)
        return self._to_chroma_format(trimmed)


    def _dedup_video_frames(self, results: list[dict]) -> list[dict]:
        """Remove near-duplicate video frames from the same video.

        Frames from the same video whose ``video_pin_second`` values are
        within ``self.dedup_time_threshold`` of each other are collapsed
        into a single result (the one with the lowest distance).

        Non-video results (type == "image") pass through unchanged.
        """
        videos: dict[str, list[dict]] = defaultdict(list)
        non_video: list[dict] = []

        for r in results:
            meta = r.get("meta", {})
            if meta.get("type") == "video":
                videos[meta.get("file_path", "")].append(r)
            else:
                non_video.append(r)

        deduped: list[dict] = list(non_video)
        for file_path, frames in videos.items():
            frames.sort(key=lambda r: r["meta"].get("video_pin_second", 0))
            cluster_best = frames[0]
            cluster_start = cluster_best["meta"].get("video_pin_second", 0)
            removed_count = 0
            for frame in frames[1:]:
                t_cur = frame["meta"].get("video_pin_second", 0)
                if t_cur - cluster_start < self.dedup_time_threshold:
                    # Same temporal cluster — keep the better score
                    removed_count += 1
                    if frame["distance"] < cluster_best["distance"]:
                        logger.debug("[dedup] %s: t=%.1fs replaces t=%.1fs (dist %.4f < %.4f, cluster start=%.1fs)",
                                     file_path, t_cur,
                                     cluster_best["meta"].get("video_pin_second", 0),
                                     frame["distance"], cluster_best["distance"], cluster_start)
                        cluster_best = frame
                    else:
                        logger.debug("[dedup] %s: t=%.1fs dropped (within %.1fs of cluster start=%.1fs)",
                                     file_path, t_cur, self.dedup_time_threshold, cluster_start)
                else:
                    deduped.append(cluster_best)
                    cluster_best = frame
                    cluster_start = t_cur
            deduped.append(cluster_best)
            if removed_count:
                logger.debug("[dedup] %s: %d/%d frames kept after dedup (threshold=%.1fs)",
                             file_path, len(frames) - removed_count, len(frames), self.dedup_time_threshold)

        logger.debug("[dedup] Total: %d non-video + %d video deduped = %d results",
                     len(non_video), len(deduped) - len(non_video), len(deduped))
        # Sort by distance ascending (lower = more relevant) so output order is deterministic
        deduped.sort(key=lambda r: r["distance"])
        return deduped


    def _rerank_documents(self, query: str, doc_results: list[dict]) -> list[dict]:
        """Re-score documents with BAAI/bge-reranker-large cross-encoder.

        Documents missing ``chunk_text`` in metadata are kept at their
        original rank position but do not receive a reranker score.
        """
        if not doc_results:
            return doc_results

        # Separate items with and without chunk_text
        with_text: list[tuple[int, dict]] = []
        without_text: list[tuple[int, dict]] = []
        for idx, r in enumerate(doc_results):
            chunk_text = r.get("meta", {}).get("chunk_text")
            if chunk_text:
                with_text.append((idx, r))
            else:
                without_text.append((idx, r))

        if with_text:
            pairs = [[query, r["meta"]["chunk_text"]] for _, r in with_text]
            logger.debug("[rerank] Scoring %d doc pairs with cross-encoder", len(pairs))
            inputs = self.tokenizer(
                pairs, padding=True, truncation=True, max_length=512, return_tensors="pt",
            )
            with torch.no_grad():
                logits = self.reranker_model(**inputs).logits.squeeze(-1)
            scores = logits.float().cpu().tolist()
            if isinstance(scores, float):
                scores = [scores]

            for score, (_, r) in zip(scores, with_text):
                r["reranker_score"] = score

            # Sort by reranker score descending
            with_text.sort(key=lambda x: x[1]["reranker_score"], reverse=True)

            for rank, (_, r) in enumerate(with_text):
                snippet = r["meta"]["chunk_text"][:80].replace("\n", " ")
                logger.debug("[rerank] #%d  reranker_score=%.4f  id=%s  text=%r...",
                             rank, r["reranker_score"], r["id"], snippet)

        if without_text:
            logger.debug("[rerank] %d doc(s) without chunk_text — kept at original position", len(without_text))

        # Merge: reranked items first, then items without text in original order
        reranked = [r for _, r in with_text] + [r for _, r in without_text]
        return reranked


    def _allocate_slots(self, groups: dict[str, list[dict]], top_k: int) -> list[dict]:
        """Allocate *top_k* result slots across content groups using RRF.

        Each group gets a dynamic minimum guarantee::

            min_per_group = max(1, top_k // (num_active_groups * 2))

        Remaining slots are filled by global RRF score.
        """
        if not groups:
            return []

        num_active = len(groups)
        min_per_group = max(1, top_k // (num_active * 2))
        logger.debug("[slots] groups=%s | top_k=%d | min_per_group=%d",
                     list(groups.keys()), top_k, min_per_group)

        # Assign RRF scores
        # visual group: already sorted by distance asc from _dedup_video_frames
        # document group: already sorted by reranker_score desc from _rerank_documents
        scored: list[tuple[float, str, int, dict]] = []  # (rrf, group, rank, result)
        for group_name, items in groups.items():
            for rank, item in enumerate(items):
                rrf = 1.0 / (RRF_K + rank)
                item["rrf_score"] = rrf
                scored.append((rrf, group_name, rank, item))

        selected: list[dict] = []
        selected_ids: set[str] = set()

        # First pass: guarantee minimum per group
        for group_name, items in groups.items():
            count = 0
            for item in items:
                if count >= min_per_group:
                    break
                if len(selected) >= top_k:
                    break
                item_id = item["id"]
                if item_id not in selected_ids:
                    selected.append(item)
                    selected_ids.add(item_id)
                    count += 1

        logger.debug("[slots] After guaranteed pass: %d selected (ids: %s)",
                     len(selected), [r["id"] for r in selected])

        # Second pass: fill remaining by global RRF
        scored.sort(key=lambda x: x[0], reverse=True)
        for rrf, group_name, rank, item in scored:
            if len(selected) >= top_k:
                break
            if item["id"] not in selected_ids:
                selected.append(item)
                selected_ids.add(item["id"])

        # Final sort: guarantee pass may have inserted items out of global RRF order
        selected.sort(key=lambda r: r["rrf_score"], reverse=True)

        # Log final allocation breakdown
        type_counts: dict[str, int] = {}
        for r in selected:
            t = r.get("meta", {}).get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        logger.debug("[slots] Final allocation: %s  (total=%d)", type_counts, len(selected))
        for i, r in enumerate(selected):
            logger.debug("[slots]   #%d  id=%-12s  type=%-8s  rrf=%.6f  dist=%.4f",
                         i, r["id"], r.get("meta", {}).get("type", "?"),
                         r.get("rrf_score", 0), r.get("distance", 0))

        return selected


    @staticmethod
    def _compute_percentage_scores(results: list[dict]) -> None:
        """Compute a 0-100% relevance score for each result in-place.

        - Documents with a reranker_score: sigmoid(reranker_score) * 100
        - Visual results (no reranker_score): (1 - distance) * 100, clamped to [0, 100]
          (ChromaDB cosine distance is in [0, 2]; 0 = identical)
        """
        for r in results:
            if r.get("reranker_score") is not None:
                r["score"] = round(1.0 / (1.0 + math.exp(-r["reranker_score"])) * 100, 2)
            else:
                r["score"] = round(max(0.0, min(100.0, (1.0 - r["distance"]) * 100)), 2)

    @staticmethod
    def _to_chroma_format(results: list[dict]) -> dict:
        """Convert flat result list back to ChromaDB nested format for backward compat."""
        output = {
            "ids": [[r["id"] for r in results]],
            "metadatas": [[r["meta"] for r in results]],
            "distances": [[r["distance"] for r in results]],
            "scores": [[r.get("score", 0.0) for r in results]],
        }
        # Attach reranker_scores as a parallel list when any result has one
        reranker_scores = [r.get("reranker_score") for r in results]
        if any(s is not None for s in reranker_scores):
            output["reranker_scores"] = [reranker_scores]
        return output
