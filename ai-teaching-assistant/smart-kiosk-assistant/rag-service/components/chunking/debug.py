from __future__ import annotations

import datetime
import json
import logging
import os
import uuid


logger = logging.getLogger(__name__)


def save_debug_chunks(chunks: list[str], save_dir: str, service_root: str) -> None:
    """Persist final chunks (about to be embedded) as JSONL for manual review."""
    if not os.path.isabs(save_dir):
        save_dir = os.path.join(service_root, save_dir.lstrip("./"))
    os.makedirs(save_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = os.path.join(save_dir, f"chunks_{ts}_{uuid.uuid4().hex[:8]}.jsonl")
    try:
        with open(fname, "w", encoding="utf-8") as fh:
            for index, chunk in enumerate(chunks):
                fh.write(
                    json.dumps(
                        {"chunk_index": index, "chars": len(chunk), "text": chunk},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        logger.info("[CHUNKER] Saved %d chunks for review → %s", len(chunks), fname)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[CHUNKER] Failed to save debug chunks: %s", exc)
