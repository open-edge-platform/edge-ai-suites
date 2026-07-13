from __future__ import annotations

import logging
import time

import numpy as np

from utils.config_loader import config
from utils.ensure_model import (
    ensure_embedding_openvino,
    get_embedding_openvino_path,
    resolve_embedding_model_source,
)


logger = logging.getLogger(__name__)


def _l2_normalize(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return x / norms


class _OpenVINOEmbedder:
    """OpenVINO IR embedder using CLS pooling + L2 normalize (matches bge-m3
    / bge-large-en-v1.5 sentence-transformers config)."""

    def __init__(self, model_dir: str, device: str, max_seq_length: int, batch_size: int) -> None:
        from optimum.intel import OVModelForFeatureExtraction
        from transformers import AutoTokenizer

        logger.info("[EMBED] Loading OpenVINO IR from %s (device=%s)", model_dir, device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = OVModelForFeatureExtraction.from_pretrained(model_dir, device=device)
        self.model.compile()
        self.max_seq_length = max_seq_length
        self.batch_size = batch_size

    def encode(self, texts: list[str], *, normalize: bool) -> np.ndarray:
        outs: list[np.ndarray] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            enc = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.max_seq_length,
                return_tensors="pt",
            )
            res = self.model(**enc)
            last = res.last_hidden_state.numpy()  # (B, T, H)
            cls = last[:, 0, :]  # CLS pooling
            outs.append(cls)
        emb = np.concatenate(outs, axis=0).astype(np.float32)
        if normalize:
            emb = _l2_normalize(emb)
        return emb


class _SentenceTransformerEmbedder:
    """Fallback torch-CPU embedder via sentence-transformers."""

    def __init__(self, source: str, device: str | None, max_seq_length: int) -> None:
        import torch
        from sentence_transformers import SentenceTransformer

        logger.info("[EMBED] Loading sentence-transformers model %s (device=%s)", source, device or "auto")
        self.model = SentenceTransformer(source)
        if device:
            if device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA requested for embeddings but no NVIDIA driver/GPU was detected; falling back to CPU")
                device = "cpu"
            self.model = self.model.to(device)
        self.max_seq_length = int(getattr(self.model, "max_seq_length", max_seq_length) or max_seq_length)
        self.tokenizer = getattr(self.model, "tokenizer", None)

    def encode(self, texts: list[str], *, normalize: bool) -> np.ndarray:
        return self.model.encode(
            texts,
            normalize_embeddings=normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )


class EmbeddingComponent:
    def __init__(self) -> None:
        embedding_cfg = config.models.embedding
        normalize = bool(getattr(embedding_cfg, "normalize_embeddings", True))
        backend = (getattr(embedding_cfg, "backend", "") or "").lower()
        max_seq_length = int(getattr(embedding_cfg, "max_seq_length", 512) or 512)
        batch_size = int(getattr(embedding_cfg, "batch_size", 16) or 16)

        if backend == "openvino":
            ensure_embedding_openvino()
            ov_device = (getattr(embedding_cfg, "device", "CPU") or "CPU").upper()
            if ov_device == "CUDA":
                ov_device = "GPU"
            self._impl: _OpenVINOEmbedder | _SentenceTransformerEmbedder = _OpenVINOEmbedder(
                get_embedding_openvino_path(),
                device=ov_device,
                max_seq_length=max_seq_length,
                batch_size=batch_size,
            )
            self._tokenizer = self._impl.tokenizer
        else:
            source = resolve_embedding_model_source()
            device = getattr(embedding_cfg, "device", None)
            if isinstance(device, str):
                normalized_device = device.strip().lower()
                if normalized_device in {"gpu", "cuda"}:
                    device = "cuda"
                elif normalized_device in {"cpu", "auto", ""}:
                    device = normalized_device or None
            self._impl = _SentenceTransformerEmbedder(source, device, max_seq_length=max_seq_length)
            self._tokenizer = self._impl.tokenizer

        self.normalize = normalize
        self._max_seq_length = self._impl.max_seq_length

    def _warn_if_truncated(self, texts: list[str]) -> None:
        if self._tokenizer is None:
            return
        for i, text in enumerate(texts):
            try:
                n_tokens = len(self._tokenizer.encode(text, add_special_tokens=True))
            except Exception:  # noqa: BLE001
                continue
            if n_tokens > self._max_seq_length:
                logger.warning(
                    "[EMBED] chunk %d exceeds model max_seq_length (%d > %d tokens); "
                    "trailing content will be silently truncated by the encoder. "
                    "Consider lowering chunking.max_chunk_chars.",
                    i, n_tokens, self._max_seq_length,
                )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._warn_if_truncated(texts)
        t0 = time.monotonic()
        emb = self._impl.encode(texts, normalize=self.normalize)
        dt_ms = (time.monotonic() - t0) * 1000
        logger.info("[EMBED] documents n=%d dim=%d elapsed=%.1fms", len(texts), emb.shape[1], dt_ms)
        return emb.tolist()

    def embed_query(self, text: str) -> list[float]:
        t0 = time.monotonic()
        emb = self._impl.encode([text], normalize=self.normalize)
        dt_ms = (time.monotonic() - t0) * 1000
        logger.info("[EMBED] query len_chars=%d elapsed=%.1fms", len(text), dt_ms)
        return emb[0].tolist()
