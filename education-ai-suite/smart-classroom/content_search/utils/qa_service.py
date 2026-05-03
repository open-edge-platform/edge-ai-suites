#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Q&A Service — Retrieval-Augmented Generation over uploaded content.

Flow:
  1. Run semantic search against the vector DB to retrieve relevant chunks.
  2. Build a RAG prompt from the retrieved context.
  3. Call the VLM /v1/chat/completions endpoint (text-only) to generate an answer.
  4. Return the answer text and the source references.
"""

import os
import logging
import traceback

import httpx

from utils.search_service import search_service

logger = logging.getLogger(__name__)

# System prompt injected at the start of every conversation.
_SYSTEM_PROMPT = (
    "You are a helpful AI assistant for an educational smart classroom. "
    "Your job is to answer questions based on the content of uploaded educational materials "
    "(videos, documents, slides, and images). "
    "When answering, be clear, concise, and accurate. "
    "Cite the source file name when relevant. "
    "If the provided context does not contain enough information to answer the question, "
    "say so clearly instead of guessing."
)

# Maximum number of history turns (user + assistant pairs) to include.
# Overridden by QA_MAX_HISTORY_TURNS env var (set from config.yaml qa.max_history_turns).
_MAX_HISTORY_TURNS = int(os.getenv("QA_MAX_HISTORY_TURNS", "3"))

# Default retrieval and generation limits read from config.yaml via env vars.
# These are the server-side defaults; the caller (endpoint) may override per-request
# as long as the per-request value does not exceed these maximums.
_DEFAULT_MAX_CONTEXT = int(os.getenv("QA_MAX_CONTEXT", "10"))
_DEFAULT_MAX_TOKENS = int(os.getenv("QA_MAX_TOKENS", "1024"))


def _format_seconds(seconds: float) -> str:
    """Convert a float second value to a human-readable MM:SS string."""
    total = int(seconds)
    m, s = divmod(total, 60)
    return f"{m}:{s:02d}"


class QAService:
    def __init__(self):
        host = os.getenv("VLM_HOST", "127.0.0.1")
        port = os.getenv("VLM_PORT", "9900")
        self.vlm_url = f"http://{host}:{port}/v1/chat/completions"
        self.model_name = os.getenv("VLM_MODEL_NAME", "Qwen/Qwen2.5-VL-3B-Instruct")
        self.timeout = 120.0

    async def ask(
        self,
        question: str,
        history: list[dict] | None = None,
        filters: dict | None = None,
        max_context: int | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """
        Returns:
            {
              "answer":  str | None,
              "sources": list of source metadata dicts,
              "error":   str (only present on failure),
            }
        """
        history = history or []

        # Use config-driven defaults when the caller did not specify a value.
        # Cap at the config maximum so a caller cannot exceed the configured limit.
        effective_max_context = min(max_context or _DEFAULT_MAX_CONTEXT, _DEFAULT_MAX_CONTEXT)
        effective_max_tokens = min(max_tokens or _DEFAULT_MAX_TOKENS, _DEFAULT_MAX_TOKENS)

        # ── Step 1: Retrieve relevant context from the vector DB ──────────
        search_payload: dict = {
            "query": question,
            "max_num_results": effective_max_context,
        }
        if filters:
            search_payload["filter"] = filters

        search_data = await search_service.semantic_search(search_payload)
        # logger.info(f"Retrieval response status: {search_data}")
        results: list[dict] = search_data.get("results", [])

        # ── Step 2: Build context string and collect source references ────
        context_parts: list[str] = []
        sources: list[dict] = []

        for r in results:
            meta = r.get("meta") or {}
            # Text content: document chunks store it in chunk_text;
            # video frame results have summary_text attached by the PostProcessor.
            # For visual results (video frames, images) without any text, build a
            # descriptive fallback so the VLM still receives context about every
            # match — consistent with what the Search functionality returns.
            chunk_text = (
                meta.get("chunk_text")
                or meta.get("summary_text")
                or ""
            )

            file_name = meta.get("file_name") or meta.get("file_path", "unknown").rsplit("/", 1)[-1]
            source_label = f"[Source: {file_name}]"
            if meta.get("video_pin_second") is not None:
                source_label += f" [at {_format_seconds(meta['video_pin_second'])}]"

            if not chunk_text:
                # Visual result (video frame or image) with no extracted text yet.
                content_type = meta.get("type") or "content"
                if meta.get("video_pin_second") is not None:
                    chunk_text = (
                        f"[Relevant {content_type} frame from '{file_name}' "
                        f"at {_format_seconds(meta['video_pin_second'])}]"
                    )
                else:
                    chunk_text = f"[Relevant {content_type} from '{file_name}']"

            context_parts.append(f"{source_label}\n{chunk_text}")
            sources.append({
                "file_name": meta.get("file_name"),
                "file_path": meta.get("file_path"),
                "type": meta.get("type"),
                "video_pin_second": meta.get("video_pin_second"),
                "video_start_second": meta.get("video_start_second"),
                "video_end_second": meta.get("video_end_second"),
                "score": r.get("score"),
            })

        context = "\n\n".join(context_parts)

        # ── Step 3: Build the messages list for the VLM ───────────────────
        messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]

        # Include the last N turns of conversation history.
        max_msgs = _MAX_HISTORY_TURNS * 2
        for h in history[-max_msgs:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": str(h["content"])})

        # Construct the current user turn with injected context.
        if context:
            user_content = (
                "Use the following context retrieved from the uploaded educational materials "
                "to answer the question. Do not answer from general knowledge alone.\n\n"
                f"--- Context ---\n{context}\n--- End of Context ---\n\n"
                f"Question: {question}"
            )
        else:
            user_content = (
                f"Question: {question}\n\n"
                "(No relevant content was found in the uploaded materials for this question. "
                "Please let the user know and suggest they upload relevant files.)"
            )

        messages.append({"role": "user", "content": user_content})

        # ── Step 4: Call the VLM ──────────────────────────────────────────
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.vlm_url,
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        "max_completion_tokens": effective_max_tokens,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                answer: str = data["choices"][0]["message"]["content"]
                logger.info(f"[QAService] answer generated ({len(answer)} chars), {len(sources)} sources")
                return {"answer": answer, "sources": sources}

        except httpx.ConnectError:
            msg = "VLM service is not reachable. Please ensure the VLM server is running."
            logger.error(f"[QAService] {msg}")
            return {"answer": None, "sources": sources, "error": msg}
        except Exception as exc:
            logger.error(f"[QAService] VLM call failed: {exc}")
            traceback.print_exc()
            return {"answer": None, "sources": sources, "error": str(exc)}


qa_service = QAService()
