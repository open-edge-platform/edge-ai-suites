# utils/topic_faiss_indexer.py

import json
import re
import faiss
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from utils.config_loader import config

# -----------------------------
# CONFIG
# -----------------------------

print(config.models.embedding.name)
EMBEDDING_MODEL = config.models.embedding.name

timestamp_pattern = re.compile(r"\[(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\]\s*(.*)")


class TopicFaissIndexer:
    def __init__(self, index_dir: Path):
        self.index_dir = index_dir
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.index_dir / "topics.faiss"
        self.meta_path = self.index_dir / "topics_meta.json"

        self.embedder = SentenceTransformer(EMBEDDING_MODEL)
        self.dim = self.embedder.get_sentence_embedding_dimension()

        self.index = faiss.IndexFlatIP(self.dim)
        self.metadata = []

    # -----------------------------
    # Transcript parsing
    # -----------------------------

    def load_transcript_lines(self, transcript_text: str):
        lines = []
        for raw_line in transcript_text.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            match = timestamp_pattern.match(raw_line)
            if match:
                lines.append({
                    "start": float(match.group(1)),
                    "end": float(match.group(2)),
                    "text": match.group(3)
                })
        return lines

    # -----------------------------
    # Topic text builder
    # -----------------------------

    def build_topic_text(self, topic, transcript_lines):
        start_time = topic["start_time"]
        end_time = topic["end_time"]

        texts = []
        for line in transcript_lines:
            # ✅ overlap-based inclusion (CRITICAL FIX)
            if not (line["end"] < start_time or line["start"] > end_time):
                texts.append(line["text"])

        return " ".join(texts)


    # -----------------------------
    # Main entry point
    # -----------------------------

    def index_topics(self, session_id: str, topics: list, transcript_text: str):
        transcript_lines = self.load_transcript_lines(transcript_text)

        vectors = []

        for topic in topics:
            raw_text = self.build_topic_text(topic, transcript_lines)
            if not raw_text.strip():
                continue

            # ⭐ Ranking fix (important)
            topic_text = f"Topic: {topic['topic']}. {raw_text}"

            embedding = self.embedder.encode(
                topic_text,
                normalize_embeddings=True
            )

            vectors.append(embedding)

            self.metadata.append({
                "session_id": session_id,
                "topic": topic["topic"],
                "start_time": topic["start_time"],
                "end_time": topic["end_time"],
                "text": raw_text
            })

        if not vectors:
            return 0

        vectors_np = np.vstack(vectors).astype("float32")
        self.index.add(vectors_np)

        # Persist
        faiss.write_index(self.index, str(self.index_path))
        self.meta_path.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")

        return len(vectors)
