"""Cross-encoder reranker for the retrieval stage.

Wraps a cross-encoder and scores ``(query, passage)`` pairs jointly, which is
materially more accurate than the bi-encoder cosine score used during ANN
search. Used as a second-stage filter: the retrieval service over-fetches
``fetch_k`` documents by ANN, this component re-orders them, and the top-k
are kept.

Supports two backends:
  * ``openvino``: optimum-intel ``OVModelForSequenceClassification`` on CPU.
  * ``torch`` (default): sentence-transformers ``CrossEncoder``.
"""
from __future__ import annotations

import logging
import time

import numpy as np

from utils.config_loader import config
from utils.ensure_model import (
    ensure_reranker_openvino,
    get_reranker_openvino_path,
    resolve_reranker_model_source,
)


logger = logging.getLogger(__name__)


class _OpenVINOReranker:
    def __init__(self, model_dir: str, device: str, max_length: int, batch_size: int) -> None:
        from optimum.intel import OVModelForSequenceClassification
        from transformers import AutoTokenizer

        logger.info("[RERANK] Loading OpenVINO IR from %s (device=%s)", model_dir, device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = OVModelForSequenceClassification.from_pretrained(model_dir, device=device)
        self.model.compile()
        self.max_length = max_length
        self.batch_size = batch_size

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        scores: list[float] = []
        for start in range(0, len(pairs), self.batch_size):
            batch = pairs[start:start + self.batch_size]
            enc = self.tokenizer(
                [p[0] for p in batch],
                [p[1] for p in batch],
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            res = self.model(**enc)
            logits = res.logits.numpy()
            if logits.ndim == 2 and logits.shape[1] == 1:
                logits = logits[:, 0]
            elif logits.ndim == 2:
                logits = logits[:, -1]  # take the positive logit if multi-class
            scores.extend(float(s) for s in logits.astype(np.float32))
        return scores


class _CrossEncoderReranker:
    def __init__(self, source: str, device: str | None, max_length: int, batch_size: int) -> None:
        import torch
        from sentence_transformers import CrossEncoder

        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA requested for reranker but no NVIDIA driver/GPU was detected; falling back to CPU")
            device = "cpu"
        logger.info("[RERANK] Loading CrossEncoder %s (device=%s, max_length=%d)", source, device or "auto", max_length)
        self.model = CrossEncoder(source, device=device, max_length=max_length)
        self.batch_size = batch_size

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [float(s) for s in scores]


class RerankerComponent:
    def __init__(self) -> None:
        reranker_cfg = getattr(config.retrieval, "reranker", None)
        if reranker_cfg is None:
            raise RuntimeError("retrieval.reranker config block is missing")

        max_length = int(getattr(reranker_cfg, "max_length", 512))
        batch_size = int(getattr(reranker_cfg, "batch_size", 16))
        backend = (getattr(reranker_cfg, "backend", "") or "").lower()

        if backend == "openvino":
            ensure_reranker_openvino()
            ov_device = (getattr(reranker_cfg, "device", "CPU") or "CPU").upper()
            if ov_device in {"CUDA"}:
                ov_device = "GPU"
            self._impl: _OpenVINOReranker | _CrossEncoderReranker = _OpenVINOReranker(
                get_reranker_openvino_path(),
                device=ov_device,
                max_length=max_length,
                batch_size=batch_size,
            )
        else:
            source = resolve_reranker_model_source()
            device = getattr(reranker_cfg, "device", None)
            if isinstance(device, str):
                normalized_device = device.strip().lower()
                if normalized_device in {"gpu", "cuda"}:
                    device = "cuda"
                elif normalized_device in {"cpu", "auto", ""}:
                    device = normalized_device or None
            self._impl = _CrossEncoderReranker(source, device, max_length=max_length, batch_size=batch_size)

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        pairs = [(query, p) for p in passages]
        t0 = time.monotonic()
        scores = self._impl.score(pairs)
        dt_ms = (time.monotonic() - t0) * 1000
        logger.info("[RERANK] pairs=%d elapsed=%.1fms", len(pairs), dt_ms)
        return scores
