#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
import logging
import traceback
import httpx

from utils.search_service import search_service
from utils.context_compressor import ( build_summary_template,build_tree_synthesizer)

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
_MAX_HISTORY_TURNS = int(os.getenv("QA_MAX_HISTORY_TURNS", "3"))

# Default retrieval and generation limits read from config.yaml via env vars.
_DEFAULT_MAX_CONTEXT = int(os.getenv("QA_MAX_CONTEXT", "5"))
_DEFAULT_MAX_TOKENS = int(os.getenv("QA_MAX_TOKENS", "1024"))
# VLM context-window size in tokens (used for TreeSummarize token budgeting).
_VLM_CONTEXT_WINDOW = int(os.getenv("VLM_CONTEXT_WINDOW", "8192"))


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
        effective_max_tokens = min(max_tokens or _DEFAULT_MAX_TOKENS, _DEFAULT_MAX_TOKENS)

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
                chunk_text = meta.get("summary_text") 

            else:
                # Unknown type — best-effort: prefer any text available.
                chunk_text = meta.get("chunk_text") or meta.get("summary_text") or ""

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

        # ── Step 3: Token-budget enforcement & answer generation ──────────
        #
        # A) Context retrieved → TreeSummarize handles token budgeting and answering.
        #    PromptHelper.repack() groups chunks into batches fitting _VLM_CONTEXT_WINDOW.
        #    One batch → single VLM call.  Multiple batches → recursive summarisation.
        #
        # B) No context → skip to the direct VLM call below with a fallback message.

        if context_parts:
            return await self._answer_with_tree_summarize(
                context_parts=context_parts,
                question=question,
                history=history,
                max_tokens=effective_max_tokens,
                sources=sources,
            )

        context = ""  # Path B — no context found

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

    # ── TreeSummarize helper ──────────────────────────────────────────────────

    async def _answer_with_tree_summarize(
        self,
        context_parts: list[str],
        question: str,
        history: list[dict],
        max_tokens: int,
        sources: list[dict],
    ) -> dict:
        """
        Use LlamaIndex TreeSummarize to answer ``question`` from ``context_parts``
        while respecting the VLM context-window token budget.

        TreeSummarize internally calls PromptHelper.repack() to group the context
        chunks into batches that each fit within ``_VLM_CONTEXT_WINDOW``.  If all
        chunks fit in one batch, the VLM is called once.  If they overflow,
        each batch is summarised first (parallel async calls), then the summaries
        are recursively processed until a single answer is produced.
        """
        try:
            summary_template = build_summary_template(
                system_prompt=_SYSTEM_PROMPT,
                history=history,
                max_history_msgs=_MAX_HISTORY_TURNS,
            )
            synthesizer = build_tree_synthesizer(
                vlm_url=self.vlm_url,
                model_name=self.model_name,
                context_window=_VLM_CONTEXT_WINDOW,
                num_output=max_tokens,
                timeout=self.timeout,
                summary_template=summary_template,
            )
            logger.info(
                "[QAService] TreeSummarize: %d context chunk(s), "
                "context_window=%d, max_tokens=%d",
                len(context_parts),
                _VLM_CONTEXT_WINDOW,
                max_tokens,
            )
            answer = await synthesizer.aget_response(
                query_str=question,
                text_chunks=context_parts,
            )
            answer_str = str(answer)
            logger.info(
                "[QAService] TreeSummarize answer generated (%d chars), %d sources",
                len(answer_str),
                len(sources),
            )
            return {"answer": answer_str, "sources": sources}

        except httpx.ConnectError:
            msg = "VLM service is not reachable. Please ensure the VLM server is running."
            logger.error("[QAService] %s", msg)
            return {"answer": None, "sources": sources, "error": msg}
        except Exception as exc:
            logger.error("[QAService] TreeSummarize failed: %s", exc)
            traceback.print_exc()
            return {"answer": None, "sources": sources, "error": str(exc)}


qa_service = QAService()
