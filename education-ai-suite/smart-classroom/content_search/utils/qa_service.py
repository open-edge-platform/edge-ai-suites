#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

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
    "When answering, be thorough and accurate — provide as much detail as the question requires. "
    "Use bullet points, numbered lists, or structured sections when they improve clarity. "
    "Cite the source file name when relevant. "
    "If the provided context does not contain enough information to answer the question, "
    "say so clearly instead of guessing."
)

# Maximum number of history turns (user + assistant pairs) to include.
_MAX_HISTORY_TURNS = int(os.getenv("QA_MAX_HISTORY_TURNS", "3"))

# Default retrieval and generation limits read from config.yaml via env vars.
_DEFAULT_MAX_CONTEXT = int(os.getenv("QA_MAX_CONTEXT", "5"))
_DEFAULT_MAX_TOKENS = int(os.getenv("QA_MAX_TOKENS", "1024"))
# Token budget for context: total VLM context window minus reserved output and overhead.
# Chars-per-token approximation (4 chars ≈ 1 token) avoids a heavy tokenizer dependency.
# Reserved = max_output (1024) + system/history/question overhead (~512) = 1536 tokens.
_VLM_CONTEXT_WINDOW = int(os.getenv("VLM_CONTEXT_WINDOW", "32768"))
_CONTEXT_RESERVED_TOKENS = int(os.getenv("QA_RESERVED_TOKENS", "1536"))
_CHARS_PER_TOKEN = 4

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
        effective_max_context = min(max_context or _DEFAULT_MAX_CONTEXT, _DEFAULT_MAX_CONTEXT)
        effective_max_tokens = max_tokens or _DEFAULT_MAX_TOKENS

        # ── Step 1: Retrieve relevant context from the vector DB ──────────
        search_payload: dict = {
            "query": question,
            "max_num_results": effective_max_context,
        }
        if filters:
            search_payload["filter"] = filters

        search_data = await search_service.semantic_search(search_payload)
        results: list[dict] = search_data.get("results", [])

        # ── Step 2: Build context string and collect source references ────
        candidate_parts: list[tuple[str, dict]] = []
        context_parts: list[str] = []
        sources: list[dict] = []

        for r in results:
            meta = r.get("meta") or {}
            content_type = meta.get("type") or ""
            file_name = meta.get("file_name") or meta.get("file_path", "unknown").rsplit("/", 1)[-1]
            source_label = f"[Source: {file_name}]"

            if meta.get("video_pin_second") is not None:
                source_label += f" [at {_format_seconds(meta['video_pin_second'])}]"

            if content_type == "document":
                # always have chunk_text — use it directly as context.
                chunk_text = meta.get("chunk_text", "")

            elif content_type in ("video", "image"):
                # Use VLM-generated summary when available (summarization enabled),
                # otherwise fall back to whatever chunk_text was stored at ingest time.
                chunk_text = meta.get("summary_text") or meta.get("chunk_text", "")

            else:
                # Unknown type — best-effort: prefer any text available.
                chunk_text = meta.get("chunk_text") or meta.get("summary_text") or ""

            candidate_parts.append((f"{source_label}\n{chunk_text}", {
                "file_name": meta.get("file_name"),
                "file_path": meta.get("file_path"),
                "type": meta.get("type"),
                "video_pin_second": meta.get("video_pin_second"),
                "video_start_second": meta.get("video_start_second"),
                "video_end_second": meta.get("video_end_second"),
                "score": r.get("score"),
            }))

        # ── Dynamic budget: include whole chunks until token budget is exhausted ──
        # Chunks are already ordered best-score-first from the retriever.
        # Drop lower-scored chunks rather than truncating higher-scored ones.
        context_budget_chars = (_VLM_CONTEXT_WINDOW - _CONTEXT_RESERVED_TOKENS) * _CHARS_PER_TOKEN
        used_chars = 0
        for chunk_str, source_meta in candidate_parts:
            chunk_chars = len(chunk_str)
            if used_chars + chunk_chars > context_budget_chars:
                logger.info(
                    "[QAService] Budget exhausted at %d/%d chars — dropping remaining chunks.",
                    used_chars, context_budget_chars,
                )
                break
            context_parts.append(chunk_str)
            sources.append(source_meta)
            used_chars += chunk_chars

        context = "\n\n".join(context_parts)

        # ── Step 4: Build the messages list for the VLM ───────────────────
        messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]

        # Include the last N turns of conversation history.
        max_msgs = _MAX_HISTORY_TURNS * 2
        for h in history[-max_msgs:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": str(h["content"])})

        # Construct the current user turn with injected context.
        if context:
            text_content = (
                "Use the following context retrieved from the uploaded educational materials "
                "to answer the question. Do not answer from general knowledge alone.\n\n"
                f"--- Context ---\n{context}\n--- End of Context ---\n\n"
                f"Question: {question}"
            )
        else:
            text_content = (
                f"Question: {question}\n\n"
                "(No relevant content was found in the uploaded materials for this question. "
                "Please let the user know and suggest they upload relevant files.)"
            )

        messages.append({"role": "user", "content": text_content})

        # ── Step 5: Call the VLM (no-context fallback path) ──────────────
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
