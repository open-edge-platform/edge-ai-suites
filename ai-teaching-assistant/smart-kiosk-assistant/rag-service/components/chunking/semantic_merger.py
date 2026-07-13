from __future__ import annotations

import numpy as np

from .text_utils import cosine_similarity


class SemanticMerger:
    """Post-pass that absorbs any below-min chunk into its most similar
    neighbor when cosine similarity passes the threshold. Runs once at the
    end of the pipeline across section boundaries."""

    def __init__(
        self,
        embedding_component,
        min_chunk_chars: int,
        max_chunk_chars: int,
        semantic_similarity_threshold: float,
    ) -> None:
        self.embedding_component = embedding_component
        self.min_chunk_chars = min_chunk_chars
        self.max_chunk_chars = max_chunk_chars
        self.semantic_similarity_threshold = semantic_similarity_threshold

    def merge_small_chunks(
        self, items: list[tuple[str, dict]],
    ) -> list[tuple[str, dict]]:
        if not items:
            return items
        items = [(t, m) for t, m in items if t and t.strip()]
        if len(items) < 2:
            return items

        out = list(items)
        changed = True
        while changed:
            changed = False
            for i, (text, md) in enumerate(out):
                if len(text) >= self.min_chunk_chars:
                    continue
                candidates: list[int] = []
                if i > 0:
                    candidates.append(i - 1)
                if i < len(out) - 1:
                    candidates.append(i + 1)
                if not candidates:
                    break
                small_vec = np.array(
                    self.embedding_component.embed_query(text), dtype=np.float32,
                )
                best_idx: int | None = None
                best_sim = -1.0
                for j in candidates:
                    neighbor_vec = np.array(
                        self.embedding_component.embed_query(out[j][0]),
                        dtype=np.float32,
                    )
                    sim = cosine_similarity(small_vec, neighbor_vec)
                    if out[j][1].get("section") == md.get("section"):
                        sim += 0.05
                    if sim > best_sim:
                        best_sim = sim
                        best_idx = j
                if best_idx is None:
                    continue
                if best_sim >= self.semantic_similarity_threshold:
                    if best_idx < i:
                        merged_text = f"{out[best_idx][0]}\n{text}".strip()
                    else:
                        merged_text = f"{text}\n{out[best_idx][0]}".strip()
                    out[best_idx] = (merged_text, out[best_idx][1])
                    out.pop(i)
                    changed = True
                    break
        return out
