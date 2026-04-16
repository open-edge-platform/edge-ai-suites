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

from providers.file_ingest_and_retrieve.utils import extract_bucket_name, file_key_to_path

logger = logging.getLogger(__name__)

RRF_K = 60  # RRF constant — higher means scores drop off more slowly with rank, increasing diversity

# Sigmoid parameters for visual score rescaling: sigmoid(k * (sim - center)) * 100.
# Text→image and image→image have very different similarity distributions, so each
# query type needs its own center.
VISUAL_SIGMOID_K = 15.0               # steepness (shared)
VISUAL_SIGMOID_CENTER_TEXT = 0.15     # text→image: CLIP sim clusters ~0.05–0.35
VISUAL_SIGMOID_CENTER_IMAGE = 0.70   # image→image: CLIP sim clusters ~0.5–0.95


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
                 dedup_time_threshold: float = 5.0, overfetch_multiplier: int = 3,
                 video_summary_id_map: dict = None, chroma_client=None,
                 document_collection_name: str = ""):
        self.dedup_time_threshold = dedup_time_threshold
        self.overfetch_multiplier = overfetch_multiplier
        self.video_summary_id_map = video_summary_id_map or {}
        self.chroma_client = chroma_client
        self.document_collection_name = document_collection_name

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
        """Full post-processing for text queries: dedup → attach summaries → rerank → scores → drop attached summaries → allocate slots → summary to video → format."""
        visual_flat = _flatten_chroma_results(visual_results)
        doc_flat = _flatten_chroma_results(doc_results)
        logger.debug("[PostProcessor] Text query: %r | visual candidates: %d | doc candidates: %d | top_k: %d",
                     query, len(visual_flat), len(doc_flat), top_k)

        visual_deduped = self._dedup_video_frames(visual_flat)
        logger.debug("[PostProcessor] After dedup: %d visual results (removed %d)",
                     len(visual_deduped), len(visual_flat) - len(visual_deduped))

        self._attach_best_summary_texts(visual_deduped)

        doc_reranked = self._rerank_documents(query, doc_flat)

        self._compute_percentage_scores(visual_deduped)
        self._compute_percentage_scores(doc_reranked)

        doc_filtered = self._remove_attached_summaries(doc_reranked, visual_deduped)

        groups = {}
        if visual_deduped:
            groups["visual"] = visual_deduped
        if doc_filtered:
            groups["document"] = doc_filtered

        merged = self._allocate_slots(groups, top_k)
        self._convert_summaries_to_video(merged)
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
        self._attach_best_summary_texts(deduped)
        trimmed = deduped[:top_k]
        # Assign RRF scores by rank so distances field is consistent with text query path (higher = better)
        for rank, item in enumerate(trimmed):
            item["rrf_score"] = 1.0 / (RRF_K + rank)
        self._compute_percentage_scores(trimmed, visual_sigmoid_center=VISUAL_SIGMOID_CENTER_IMAGE)
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


    def _attach_best_summary_texts(self, results: list[dict]) -> None:
        """Attach the best matched summary text to each video result in-place.

        For each video result, finds the summary whose time range midpoint
        is closest to the video_pin_second and attaches its chunk_text.
        Non-video results are skipped.
        """
        if not self.video_summary_id_map or not self.chroma_client:
            return

        # Group video results by file_path to avoid redundant DB lookups
        video_results_by_file: dict[str, list[dict]] = defaultdict(list)
        for r in results:
            meta = r.get("meta", {})
            if meta.get("type") == "video":
                file_path = meta.get("file_path", "")
                video_results_by_file[file_path].append(r)

        for file_path, video_results in video_results_by_file.items():
            summary_ids = self.video_summary_id_map.get(file_path, [])
            if not summary_ids:
                logger.debug("[summary] No summaries found for %s", file_path)
                continue

            summaries = self.chroma_client.get(
                ids=summary_ids,
                output_fields=["id", "meta"],
                collection_name=self.document_collection_name,
            )
            if not summaries:
                continue

            for r in video_results:
                video_pin_second = r["meta"].get("video_pin_second", 0)
                best = self._find_best_summary(video_pin_second, summaries)
                if best:
                    chunk_text = best.get("meta", {}).get("chunk_text", "")
                    if chunk_text:
                        r["meta"]["summary_text"] = chunk_text
                        logger.debug("[summary] Attached summary to video t=%.1fs in %s",
                                     video_pin_second, file_path)

    @staticmethod
    def _find_best_summary(video_pin_second: float, summaries: list[dict]) -> dict | None:
        """Find the summary whose time range midpoint is closest to video_pin_second."""
        best = None
        best_dist = float("inf")
        for s in summaries:
            meta = s.get("meta", {})
            start_time = meta.get("start_time")
            end_time = meta.get("end_time")
            if start_time is None or end_time is None:
                continue
            mid_time = start_time + (end_time - start_time) / 2
            dist = abs(video_pin_second - mid_time)
            if dist < best_dist:
                best_dist = dist
                best = s
        return best

    @staticmethod
    def _remove_attached_summaries(doc_results: list[dict], visual_results: list[dict]) -> list[dict]:
        """Remove summaries whose chunk_text is already attached to a visual frame."""
        attached_texts = {
            r["meta"].get("summary_text", "")
            for r in visual_results
            if r.get("meta", {}).get("summary_text")
        }
        filtered = []
        removed_count = 0
        for r in doc_results:
            if "summary_key" in r.get("meta", {}) and r["meta"].get("chunk_text", "") in attached_texts:
                removed_count += 1
            else:
                filtered.append(r)
        if removed_count:
            logger.debug("[PostProcessor] Removed %d attached summaries from doc group", removed_count)
        return filtered

    @staticmethod
    def _convert_summaries_to_video(results: list[dict]) -> None:
        """Convert remaining summary documents in the final result list to video results in-place.

        Attached summaries are already removed before allocation, so every
        summary here should be converted.  Any that cannot be converted
        (missing file_key/bucket) are dropped.
        """
        converted_count = 0
        remove_indices: list[int] = []
        for i, r in enumerate(results):
            meta = r.get("meta", {})
            if "summary_key" not in meta:
                continue
            chunk_text = meta.get("chunk_text", "")
            file_key = meta.get("file_key", "")
            bucket = extract_bucket_name(meta.get("file_path", ""))
            if not bucket or not file_key:
                remove_indices.append(i)
                continue
            video_fp = file_key_to_path(file_key, bucket)
            start_time = meta.get("start_time", 0)
            end_time = meta.get("end_time", 0)
            mid_time = start_time + (end_time - start_time) / 2
            r["meta"] = {
                "file_path": video_fp,
                "type": "video",
                "original_type": "constructed_from_summary",
                "video_pin_second": round(mid_time, 2),
                "video_start_second": round(start_time, 2),
                "video_end_second": round(end_time, 2),
                "summary_text": chunk_text,
                "reranker_score": r.get("reranker_score"),
            }
            converted_count += 1
        for i in reversed(remove_indices):
            results.pop(i)
        if converted_count or remove_indices:
            logger.debug("[PostProcessor] Summaries: %d converted to video, %d dropped (missing file_key)",
                         converted_count, len(remove_indices))

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
        group_sizes = {name: len(items) for name, items in groups.items()}
        logger.debug("[slots] %d group(s): %s | top_k=%d | min_per_group=%d",
                     num_active, group_sizes, top_k, min_per_group)

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
    def _compute_percentage_scores(results: list[dict], visual_sigmoid_center: float = VISUAL_SIGMOID_CENTER_TEXT) -> None:
        """Compute a 0-100% absolute relevance score for each result in-place.

        - Documents (reranker_score present): sigmoid(reranker_score) * 100
        - Visual (no reranker_score): sigmoid(k * (cosine_sim - center)) * 100
          where cosine_sim = 1 - distance (ChromaDB cosine distance in [0, 2])
        """
        for r in results:
            if r.get("reranker_score") is not None:
                r["score"] = round(1.0 / (1.0 + math.exp(-r["reranker_score"])) * 100, 2)
            else:
                similarity = 1.0 - r["distance"]
                r["score"] = round(1.0 / (1.0 + math.exp(-VISUAL_SIGMOID_K * (similarity - visual_sigmoid_center))) * 100, 2)

    @staticmethod
    def _to_chroma_format(results: list[dict]) -> dict:
        """Convert flat result list back to ChromaDB nested format for backward compat.

        Preserves RRF order from _allocate_slots — scores are absolute relevance
        per type and not comparable across types, so sorting by score would be wrong.
        """
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
