#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Context compressor using LlamaIndex TreeSummarize for token-budget enforcement.

When the total context retrieved from the vector DB exceeds the VLM's context
window, TreeSummarize recursively groups and summarizes the chunks in batches
that each fit within the window — bottom-up — until a single answer is produced.

If all context already fits in one pass (determined by PromptHelper.repack),
the VLM is still called exactly once to answer the question from the packed batch.

Usage in qa_service:
    template = build_summary_template(system_prompt, history, max_history_msgs)
    synth    = build_tree_synthesizer(vlm_url, model_name, context_window,
                                      num_output, timeout, template)
    answer   = await synth.aget_response(query_str=question,
                                         text_chunks=context_parts)
"""

import logging
from typing import Any, Sequence

import httpx

from llama_index.core.base.llms.types import (
    ChatMessage,
    ChatResponse,
    ChatResponseAsyncGen,
    ChatResponseGen,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
    MessageRole,
)
from llama_index.core.bridge.pydantic import Field
from llama_index.core.indices.prompt_helper import PromptHelper
from llama_index.core.llms.callbacks import llm_chat_callback, llm_completion_callback
from llama_index.core.llms.custom import CustomLLM
from llama_index.core.prompts import PromptTemplate
from llama_index.core.response_synthesizers.tree_summarize import TreeSummarize

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# LlamaIndex LLM adapter wrapping our OpenAI-compatible VLM endpoint
# ──────────────────────────────────────────────────────────────────────────────

class VLMAdapter(CustomLLM):
    """
    Thin LlamaIndex CustomLLM wrapper around the VLM OpenAI-compatible endpoint.

    Used exclusively by TreeSummarize so that LlamaIndex can call the VLM
    during recursive context compression.  The async path (achat) is natively
    async via httpx.AsyncClient so it does not block the event loop.
    """

    vlm_url: str = Field(default="http://127.0.0.1:9900/v1/chat/completions")
    vlm_model: str = Field(default="Qwen/Qwen2.5-VL-3B-Instruct")
    vlm_timeout: float = Field(default=120.0)
    vlm_context_window: int = Field(default=4096)
    vlm_num_output: int = Field(default=512)

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=self.vlm_context_window,
            num_output=self.vlm_num_output,
            model_name=self.vlm_model,
            # Set True so LLM.apredict() calls achat() instead of acomplete().
            is_chat_model=True,
        )

    # ── Sync path (fallback, not performance-critical) ───────────────────────

    @llm_chat_callback()
    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        """Sync chat using httpx.Client (used by CustomLLM.stream_chat fallback)."""
        payload = self._build_payload(messages)
        with httpx.Client(timeout=self.vlm_timeout) as client:
            resp = client.post(self.vlm_url, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        return ChatResponse(
            message=ChatMessage(role=MessageRole.ASSISTANT, content=content)
        )

    def _complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """Sync completion — wraps the prompt as a single user message."""
        response = self.chat([ChatMessage(role=MessageRole.USER, content=prompt)])
        return CompletionResponse(text=response.message.content or "")

    def _stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        raise NotImplementedError(
            "Streaming is not supported by VLMAdapter (TreeSummarize does not stream)."
        )

    # ── Async path (primary, called by TreeSummarize.aget_response) ──────────

    @llm_chat_callback()
    async def achat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> ChatResponse:
        """Native async chat via httpx.AsyncClient — the hot path for TreeSummarize."""
        payload = self._build_payload(messages)
        async with httpx.AsyncClient(timeout=self.vlm_timeout) as client:
            resp = await client.post(self.vlm_url, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        logger.debug(
            "[VLMAdapter] TreeSummarize batch answered (%d chars)", len(content)
        )
        return ChatResponse(
            message=ChatMessage(role=MessageRole.ASSISTANT, content=content)
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_payload(self, messages: Sequence[ChatMessage]) -> dict:
        return {
            "model": self.vlm_model,
            "messages": [
                {"role": m.role.value, "content": str(m.content or "")}
                for m in messages
            ],
            "max_tokens": self.vlm_num_output,
            "stream": False,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Factory helpers
# ──────────────────────────────────────────────────────────────────────────────

def build_summary_template(
    system_prompt: str,
    history: list[dict],
    max_history_msgs: int,
) -> PromptTemplate:
    """
    Build a PromptTemplate for TreeSummarize that pre-bakes the system prompt
    and conversation history.

    ``{context_str}`` and ``{query_str}`` remain as placeholders that
    TreeSummarize fills in at each recursion level.
    """
    history_parts: list[str] = []
    for h in history[-(max_history_msgs * 2):]:
        role = h.get("role", "")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            history_parts.append(f"{role.capitalize()}: {content}")

    history_block = (
        "Previous conversation:\n" + "\n".join(history_parts) + "\n\n"
        if history_parts
        else ""
    )

    tmpl_str = (
        f"{system_prompt}\n\n"
        f"{history_block}"
        "Context information from educational materials:\n"
        "---------------------\n"
        "{context_str}\n"
        "---------------------\n"
        "Based on the context above (not prior knowledge), answer the question "
        "clearly and concisely. Cite the source file name when relevant.\n"
        "Question: {query_str}\n"
        "Answer: "
    )
    return PromptTemplate(tmpl_str)


def build_tree_synthesizer(
    vlm_url: str,
    model_name: str,
    context_window: int,
    num_output: int,
    timeout: float,
    summary_template: PromptTemplate,
) -> TreeSummarize:
    """
    Instantiate a TreeSummarize synthesizer backed by our VLM adapter.

    PromptHelper is configured with the VLM's ``context_window`` and
    ``num_output`` so that ``repack()`` correctly determines batch boundaries.
    TreeSummarize will:
      - repack all context_parts into minimum batches fitting the window
      - answer directly if 1 batch fits
      - recursively summarise across batches otherwise (multiple VLM calls)
    """
    adapter = VLMAdapter(
        vlm_url=vlm_url,
        vlm_model=model_name,
        vlm_context_window=context_window,
        vlm_num_output=num_output,
        vlm_timeout=timeout,
    )
    prompt_helper = PromptHelper(
        context_window=context_window,
        num_output=num_output,
    )
    return TreeSummarize(
        llm=adapter,
        prompt_helper=prompt_helper,
        summary_template=summary_template,
        use_async=True,
        verbose=False,
    )
