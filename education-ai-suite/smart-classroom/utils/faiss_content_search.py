import json
import faiss
from sentence_transformers import SentenceTransformer
from pathlib import Path

MODEL_NAME = "BAAI/bge-large-en-v1.5"


class FaissContentSearcher:
    def __init__(self, faiss_dir: Path):
        self.index_path = faiss_dir / "topics.faiss"
        self.meta_path = faiss_dir / "topics_meta.json"

        if not self.index_path.exists():
            raise FileNotFoundError(f"FAISS index not found: {self.index_path}")
        if not self.meta_path.exists():
            raise FileNotFoundError(f"FAISS metadata not found: {self.meta_path}")

        self.embedder = SentenceTransformer(MODEL_NAME)
        self.index = faiss.read_index(str(self.index_path))

        with open(self.meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

    def search(self, query: str, top_k: int = 5):
        query_vec = self.embedder.encode(
            query,
            normalize_embeddings=True
        ).reshape(1, -1)

        scores, ids = self.index.search(query_vec, top_k)

        results = []
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:
                continue

            results.append({
                "score": float(score),
                **self.metadata[idx]
            })

        return results
