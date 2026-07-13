"""Pure prompt construction: stitches system prompt, conversation history,
retrieved context, and runtime context under a single char budget."""
from __future__ import annotations

from .types import RetrievalRecord


class PromptBuilder:
    def __init__(
        self,
        system_prompt: str,
        max_context_chars: int,
        history_turns: int,
        include_source_markers: bool,
        fallback_to_general_knowledge: bool,
    ) -> None:
        self.system_prompt = system_prompt
        self.max_context_chars = max_context_chars
        self.history_turns = max(0, history_turns)
        self.include_source_markers = include_source_markers
        self.fallback_to_general_knowledge = fallback_to_general_knowledge

    def build(
        self,
        question: str,
        sources: list[RetrievalRecord],
        context_text: str | None = None,
        system_prompt: str | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> str:
        prompt_system = system_prompt or self.system_prompt
        extra_context = (context_text or "").strip()
        history_block = self._build_history_block(history)
        # The retrieved context absorbs whatever budget is left after the
        # runtime context and conversation history are accounted for, so the
        # combined non-question payload never exceeds max_context_chars.
        remaining = max(0, self.max_context_chars - len(extra_context) - len(history_block))
        retrieved_context = self._build_context_block(sources, char_budget=remaining)

        # If history + extra alone already overflow, drop oldest history turns
        # until we are back within budget, then truncate extra_context tail.
        history_block, extra_context = self._enforce_total_budget(
            history_block, retrieved_context, extra_context,
        )

        fallback_hint = (
            "If the retrieved kiosk context is insufficient, you may use limited general domain knowledge, but state uncertainty clearly and do not invent business-specific facts."
            if self.fallback_to_general_knowledge
            else "If the context is insufficient, say you do not have enough knowledge-base context to answer confidently."
        )

        prompt = [prompt_system.strip()]
        if history_block:
            prompt.extend(["", f"Recent conversation (oldest first):\n{history_block}"])
        if retrieved_context:
            prompt.extend(["", f"Retrieved knowledge-base context:\n{retrieved_context}"])
        if extra_context:
            prompt.extend(["", f"Runtime context passed by caller:\n{extra_context}"])
        prompt.extend(["", fallback_hint, "", f"Customer question:\n{question.strip()}", "Answer:"])
        return "\n".join(prompt).strip()

    # ── internals ────────────────────────────────────────────────────

    def _build_context_block(
        self,
        sources: list[RetrievalRecord],
        char_budget: int | None = None,
    ) -> str:
        budget = self.max_context_chars if char_budget is None else max(0, char_budget)
        parts: list[str] = []
        total_chars = 0
        for index, record in enumerate(sources, start=1):
            label = f"[{index}] {record.source}" if self.include_source_markers else record.source
            block = f"### SOURCE {label}\n{record.content.strip()}"
            if total_chars + len(block) > budget:
                break
            parts.append(block)
            total_chars += len(block)
        return "\n\n".join(parts)

    def _build_history_block(self, history: list[tuple[str, str]] | None) -> str:
        if not history or self.history_turns <= 0:
            return ""
        # Keep at most history_turns full user+assistant exchanges (2 messages each).
        trimmed = history[-(self.history_turns * 2):]
        lines: list[str] = []
        for role, content in trimmed:
            text = (content or "").strip()
            if not text:
                continue
            label = (
                "User" if role == "user"
                else "Assistant" if role == "assistant"
                else role.capitalize()
            )
            lines.append(f"{label}: {text}")
        return "\n".join(lines)

    def _enforce_total_budget(
        self,
        history_block: str,
        retrieved_context: str,
        extra_context: str,
    ) -> tuple[str, str]:
        budget = self.max_context_chars
        # Drop oldest history lines until history + retrieved + extra fits.
        lines = history_block.split("\n") if history_block else []
        while lines and (
            len(retrieved_context) + len(extra_context) + sum(len(l) + 1 for l in lines) > budget
        ):
            lines.pop(0)
        history_block = "\n".join(lines)
        # Final guard: truncate extra_context tail if still over budget.
        overflow = len(history_block) + len(retrieved_context) + len(extra_context) - budget
        if overflow > 0 and extra_context:
            extra_context = extra_context[: max(0, len(extra_context) - overflow)]
        return history_block, extra_context
