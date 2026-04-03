# PostProcessor / Reranker

`PostProcessor` in `providers/file_ingest_and_retrieve/reranker.py` sits between ChromaDB retrieval and the API response. It deduplicates video frames, reranks documents with a cross-encoder, merges results from multiple content types, and normalises the output format.

---

## Configurable Options

| Parameter | Default | Effect |
|-----------|---------|--------|
| `reranker_model` | _(required)_ | HuggingFace model ID or local OV IR directory name under `models/openvino/`. If the OV IR does not exist it is exported and saved automatically. |
| `device` | `"CPU"` | OpenVINO inference device (e.g. `"GPU"`, `"NPU"`). |
| `dedup_time_threshold` | `5.0` s | Two video frames from the same file within this temporal window are treated as duplicates; only the one with lower distance is kept. |
| `overfetch_multiplier` | `3` | Available for callers to overfetch candidates before post-processing (not used internally by `PostProcessor` itself). |
| `RRF_K` (module constant) | `60` | Controls how steeply RRF scores drop off with rank. Higher → more diversity; lower → top-rank items dominate more. |

---

## Entry Points

### `process_text_query_results(query, visual_results, doc_results, top_k)`

Pipeline: **dedup → rerank → allocate slots → format**

```
visual_results (ChromaDB) ──→ flatten → _dedup_video_frames ──┐
                                                               ├─→ _allocate_slots → _to_chroma_format
doc_results    (ChromaDB) ──→ flatten → _rerank_documents ────┘
```

### `process_image_query_results(visual_results, top_k)`

Pipeline: **dedup → trim → assign RRF by rank → format**

No cross-encoder is invoked. `scores` are assigned purely by distance rank so the output format is consistent with the text path.

---

## Step Details

### 1. `_dedup_video_frames`

- Splits input into **video** (`meta.type == "video"`) and **non-video** (static images, pass-through).
- For each video file, sorts frames by `video_pin_second`, then does a linear scan:
  - If the current frame's timestamp is within `dedup_time_threshold` of the cluster leader, they are in the same cluster → keep whichever has the lower `distance`.
  - Otherwise, emit the cluster leader and start a new cluster.
- Final output is sorted by `distance` ascending (lower = more relevant). This ordering is relied on by `_allocate_slots` for RRF ranking.

### 2. `_rerank_documents`

- Documents with `meta.chunk_text` are scored by the cross-encoder as `[query, chunk_text]` pairs in a single batched inference call (max length 512 tokens).
- The raw logit is stored as `reranker_score` on each result.
- Scored documents are sorted by `reranker_score` descending. Documents without `chunk_text` are appended at the end in their original order without a score.

### 3. `_allocate_slots`

Merges `visual` and `document` groups into a single ranked list of `top_k` items.

**RRF scoring** — each group is ranked independently (visual: by distance, document: by reranker_score). RRF score is assigned per item:

$$\text{rrf\_score} = \frac{1}{k + \text{rank}}, \quad k = \text{RRF\_K} = 60$$

**Two-pass selection:**

1. **Guarantee pass** — each group gets at least `min_per_group = max(1, top_k // (num_groups × 2))` slots, preventing a dominant group from starving others entirely.
2. **Fill pass** — remaining slots are filled globally by descending `rrf_score`.

After both passes, `selected` is re-sorted by `rrf_score` descending to produce a globally consistent ranking (the guarantee pass can insert items out of global order).

### 4. `_to_chroma_format`

Converts the flat result list back to ChromaDB nested format. Output fields:

| Field | Content | Direction |
|-------|---------|-----------|
| `ids` | result id list | — |
| `metadatas` | original metadata dicts | — |
| `distances` | raw ChromaDB cosine distance | lower = better |
| `scores` | RRF score, list is already sorted descending | higher = better |
| `reranker_scores` | cross-encoder logit per result (`None` for visual items); **only present when at least one document result exists** | higher = better |

---

## Score Comparability

- `scores` (RRF) are **comparable within a single call** — visual and document results can be ranked against each other.
- `scores` are **not comparable across separate calls** — RRF is a relative rank-based value, not an absolute similarity measure.
- `distances` are absolute cosine distances and can be used for quality filtering (e.g. drop results with `distance > threshold`) independently of call context.
