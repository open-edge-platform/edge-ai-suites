# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Synthetic classroom-transcript builder for the long-context capacity validator.

Builds a chat prompt whose token count lands as close to a target size as the
tokenizer's merge rules allow, so trial_runner.py can push the real OpenVINO
pipeline up to a given context length and measure whether *this hardware* can
prefill and decode it without running out of memory.

Everything here is model-agnostic: it only needs a HuggingFace-style tokenizer
(``encode`` / ``decode`` / ``apply_chat_template``), so it can be unit-tested
with a stub tokenizer and no model download. This mirrors the approach in
refer/long_context/long_context_probe.py -- the content is irrelevant to the
validation, only the token *volume* matters, but realistic, varied dialog keeps
the tokenizer's merge behaviour representative of a real transcript instead of a
single repeated token.
"""

from __future__ import annotations

from typing import Protocol


class Tokenizer(Protocol):
    def encode(self, text: str, add_special_tokens: bool = True) -> list:
        ...

    def decode(self, ids, skip_special_tokens: bool = True) -> str:
        ...

    def apply_chat_template(self, messages, tokenize: bool = False, **kwargs) -> str:
        ...


SYSTEM_PROMPT = (
    "You are a teaching assistant validating a classroom transcript. Follow the "
    "task after the transcript and answer with useful natural language."
)

_USER_PREFIX = "CLASSROOM TRANSCRIPT\n---\n"
_USER_SUFFIX = (
    "\n---\nTASK\nSummarize the lesson's main topic and one key relationship "
    "explained by the teacher in two concise sentences."
)

# A small pool of generic classroom-dialog lines. Content is irrelevant to the
# validation -- only the token *volume* matters -- but realistic, varied text
# keeps the tokenizer's merge behaviour representative of a real transcript
# rather than a single repeated token.
_CORPUS_LINES = [
    "TEACHER: Let's begin today's lesson by reviewing what we covered last week about energy transfer.",
    "STUDENT_01: Could you explain again why kinetic energy depends on the square of the velocity?",
    "TEACHER: Good question. When we double the speed, the energy increases by a factor of four.",
    "STUDENT_02: So a car moving twice as fast needs four times the braking distance?",
    "TEACHER: Precisely, and that is why speed limits matter so much for road safety.",
    "STUDENT_03: What happens to that energy when the car finally stops?",
    "TEACHER: Most of it is converted into heat through friction in the brakes and the tyres.",
    "STUDENT_01: Does that mean energy is never actually lost, only transformed?",
    "TEACHER: Correct, that is the principle of conservation of energy in a closed system.",
    "STUDENT_04: Can you give an everyday example where potential energy becomes kinetic energy?",
    "TEACHER: Think of a roller coaster climbing to the top of a hill and then racing down.",
    "STUDENT_02: At the very top it has the most potential energy and almost no motion.",
    "TEACHER: Exactly, and at the bottom that potential energy has become kinetic energy.",
    "STUDENT_03: How do engineers account for friction and air resistance in real designs?",
    "TEACHER: They add safety margins and measure the losses experimentally in testing.",
    "STUDENT_04: Is there a formula that ties all of these ideas together for the exam?",
    "TEACHER: Yes, we will derive the work-energy theorem step by step on the board now.",
    "STUDENT_01: Should we memorise the derivation or just the final expression?",
    "TEACHER: Understand the derivation; the final expression will follow naturally from it.",
    "STUDENT_02: Thank you, that makes the relationship between force and distance much clearer.",
]


def _corpus_text() -> str:
    return "\n".join(_CORPUS_LINES) + "\n"


def build_text_of_token_length(tokenizer: Tokenizer, target_tokens: int) -> tuple:
    """Return synthetic transcript text whose token count is as close to
    ``target_tokens`` as the tokenizer's merge rules allow.

    Returns ``(text, actual_token_count)``. ``actual_token_count`` is measured by
    re-encoding the decoded text (round-tripped), so it reflects exactly what the
    downstream pipeline will see, not the pre-truncation id list.
    """
    if target_tokens <= 0:
        return "", 0

    corpus = _corpus_text()
    corpus_ids = tokenizer.encode(corpus, add_special_tokens=False)
    if not corpus_ids:
        raise ValueError("Tokenizer produced no tokens for the built-in corpus.")

    # Repeat the corpus until we have at least the requested number of tokens,
    # then slice the id list to the exact target and decode back to text.
    reps = (target_tokens // len(corpus_ids)) + 1
    text = corpus * reps
    ids = tokenizer.encode(text, add_special_tokens=False)[:target_tokens]
    text = tokenizer.decode(ids, skip_special_tokens=True)
    actual = len(tokenizer.encode(text, add_special_tokens=False))
    return text, actual


def measure_template_overhead(
    tokenizer: Tokenizer,
    messages: list,
    empty_user_content: str = "",
    **template_kwargs,
) -> int:
    """Token cost of the chat template + system prompt with an *empty* user turn.

    Used to back out how much room is left for transcript content so the final
    rendered prompt lands on a target size. The last user turn's content is
    blanked for the measurement so the transcript itself doesn't inflate it.
    """
    probe = [dict(m) for m in messages]
    user_idx = next(
        (i for i in range(len(probe) - 1, -1, -1) if probe[i].get("role") == "user"),
        None,
    )
    if user_idx is not None:
        probe[user_idx]["content"] = empty_user_content
    rendered = tokenizer.apply_chat_template(probe, tokenize=False, **template_kwargs)
    return len(tokenizer.encode(rendered))


def build_context_prompt(tokenizer: Tokenizer, target_tokens: int) -> tuple:
    """Build a rendered chat prompt whose token length is ~``target_tokens``.

    Sizes the transcript content so that, once the system prompt and chat-template
    scaffolding are added back, the whole rendered prompt lands on the target.
    Returns ``(prompt_text, prompt_tokens)`` where ``prompt_tokens`` is the real
    prefill size the pipeline will see (special tokens included).
    """
    template_kwargs = dict(add_generation_prompt=True, enable_thinking=False)

    empty_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": ""},
    ]
    fixed_user_content = _USER_PREFIX + _USER_SUFFIX
    overhead = measure_template_overhead(
        tokenizer,
        empty_messages,
        empty_user_content=fixed_user_content,
        **template_kwargs,
    )
    content_target = max(0, target_tokens - overhead)

    content, _actual_content = build_text_of_token_length(tokenizer, content_target)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _USER_PREFIX + content + _USER_SUFFIX},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, **template_kwargs)
    prompt_tokens = len(tokenizer.encode(prompt))
    return prompt, prompt_tokens
