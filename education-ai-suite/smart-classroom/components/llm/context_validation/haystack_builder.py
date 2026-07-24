# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Synthetic classroom-transcript ("haystack") construction for the long-context validator.

Builds a token-exact-sized synthetic transcript with a single unique fact (the
"needle") planted at a configurable relative depth, plus a question that can only
be answered by recalling that fact. Used by trial_runner.py to probe whether a
model still uses content from far back in its context window, not just whether
it loads/generates without error.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Protocol


class Tokenizer(Protocol):
    def encode(self, text: str) -> list:
        ...

    def decode(self, ids, skip_special_tokens: bool = True) -> str:
        ...


SYSTEM_PROMPT = (
    "You are a careful reading-comprehension assistant. Read the full classroom "
    "transcript below, then answer the question at the end using only information "
    "stated in the transcript."
)

# No "reply with only the code" instruction needed: trial_runner.py constrains
# the answer to exactly N digits via structured output (grammar-constrained
# decoding), so format compliance doesn't depend on the model following the
# instruction -- it's structurally the only thing it can produce.
QUESTION = "What is the classroom access code mentioned earlier by the teacher?"

# Content-free filler topics: cycling through several subjects keeps the synthetic
# transcript lexically varied at 100K+ tokens instead of degenerating into a
# repeated phrase the model could shortcut on.
_TOPICS = [
    ("photosynthesis", "how plants convert sunlight into chemical energy"),
    ("the water cycle", "how water moves between the atmosphere, land, and oceans"),
    ("the French Revolution", "the social and political causes behind the uprising"),
    ("quadratic equations", "how to factor and solve for the roots"),
    ("Newton's laws of motion", "how force, mass, and acceleration relate to each other"),
    ("the periodic table", "how elements are organized by atomic number and properties"),
    ("cell division", "how a single cell splits into two identical daughter cells"),
    ("supply and demand", "how price is determined in a competitive market"),
    ("the Renaissance", "the revival of art, science, and philosophy in Europe"),
    ("probability", "how to calculate the likelihood of independent events"),
    ("hydrogen bonding", "why it gives water its unique properties"),
    ("the Industrial Revolution", "how mechanization changed manufacturing and society"),
    ("plate tectonics", "how moving plates shape mountains and earthquakes"),
    ("the Cold War", "how rival ideologies shaped decades of global politics"),
    ("binary search trees", "how keeping nodes ordered makes lookups fast"),
]

_TEACHER_TEMPLATES = [
    "Let's continue our discussion on {topic}. Remember that {detail}.",
    "Today's lesson covers {topic}. In particular, {detail}.",
    "Turning back to {topic}, it's worth repeating that {detail}.",
    "As we go deeper into {topic}, keep in mind {detail}.",
    "One more point about {topic}: {detail}.",
]

_STUDENT_TEMPLATES = [
    "Could you explain again why {detail}?",
    "I'm a little confused about {topic}. Can you give another example?",
    "So does that mean {detail} always holds true?",
    "What happens with {topic} in a different scenario?",
    "Is {detail} the same in every case we've covered?",
]

# Digits only, not mixed alphanumeric: real-hardware testing showed models
# recalling a mixed-alnum code (e.g. "X7S89U") would locate the right spot but
# reproduce it imprecisely (e.g. quoting "46AX" for planted code "46AXE7") --
# tokenizers generally chunk digit runs more predictably than mixed alnum
# strings, so a numeric code is less likely to produce a false "wrong" verdict
# that's actually a tokenization artifact rather than a genuine recall miss.
# This mirrors standard practice in needle-in-haystack benchmarks.
_CODE_ALPHABET = "0123456789"


def _next_line(rng: random.Random, index: int) -> str:
    topic, detail = _TOPICS[index % len(_TOPICS)]
    if index % 2 == 0:
        speaker = "TEACHER"
        text = rng.choice(_TEACHER_TEMPLATES).format(topic=topic, detail=detail)
    else:
        speaker = f"STUDENT_{(index // 2) % 12 + 1:02d}"
        text = rng.choice(_STUDENT_TEMPLATES).format(topic=topic, detail=detail)
    return f"{speaker}: {text}"


def _join(lines: list) -> str:
    return "\n".join(lines)


def _generate_code(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice(_CODE_ALPHABET) for _ in range(length))


def _needle_line(code: str) -> str:
    return (
        "TEACHER: Quick announcement before we continue: today's classroom access "
        f"code is {code}. Please write it down."
    )


def _build_filler(
    tokenizer: Tokenizer,
    rng: random.Random,
    budget_tokens: int,
    start_index: int = 0,
    sample_lines: int = 50,
    margin: float = 1.15,
) -> tuple:
    """Return filler text sized to ~budget_tokens, exact via token-id truncation.

    Avoids re-tokenizing on every line: estimate tokens-per-line from one sample,
    generate enough lines to comfortably exceed the budget, then truncate the
    encoded ids to the exact count. Bounded to a handful of tokenizer calls
    regardless of how large budget_tokens is.
    """
    if budget_tokens <= 0:
        return "", start_index

    lines = [_next_line(rng, start_index + i) for i in range(sample_lines)]
    sample_tokens = max(len(tokenizer.encode(_join(lines))), 1)
    tokens_per_line = sample_tokens / len(lines)

    needed_lines = max(len(lines), math.ceil(budget_tokens / tokens_per_line * margin))
    lines.extend(
        _next_line(rng, start_index + len(lines) + i)
        for i in range(needed_lines - len(lines))
    )
    ids = tokenizer.encode(_join(lines))

    # A tokenizer far more efficient than the sample suggested could still
    # undershoot the margin; extend once more rather than looping indefinitely.
    if len(ids) < budget_tokens:
        extra = [
            _next_line(rng, start_index + len(lines) + i) for i in range(sample_lines)
        ]
        lines.extend(extra)
        ids = tokenizer.encode(_join(lines))

    ids = ids[:budget_tokens]
    text = tokenizer.decode(ids, skip_special_tokens=True)
    # A raw token-count cutoff can land mid-line, leaving a dangling fragment
    # (e.g. "STUDENT_1" with no colon or content) right before the needle or
    # the [QUESTION] marker -- trim back to the last complete line so nothing
    # ambiguous sits at the seam.
    if "\n" in text and not text.endswith("\n"):
        text = text.rsplit("\n", 1)[0]
    return text, start_index + len(lines)


@dataclass
class Probe:
    messages: list = field(default_factory=list)  # [{"role": ..., "content": ...}, ...]
    expected_code: str = ""
    tokens_actual: int = 0


def build_probe(
    tokenizer: Tokenizer,
    target_tokens: int,
    depth: float,
    seed: int,
    reserved_tokens: int = 128,
) -> Probe:
    """Build one needle-in-haystack probe sized to ~target_tokens.

    `depth` in [0, 1] controls how far into the transcript the needle is planted
    (0.0 = right at the start, 1.0 = right at the end). `reserved_tokens` leaves
    headroom for the needle sentence, the question, and chat-template overhead
    the caller adds afterward (system role, generation prompt, etc.).
    """
    if not 0.0 <= depth <= 1.0:
        raise ValueError(f"depth must be within [0, 1], got {depth}")

    rng = random.Random(seed)
    code = _generate_code(rng)
    needle = _needle_line(code)
    needle_tokens = len(tokenizer.encode(needle))
    question_tokens = len(tokenizer.encode(QUESTION))

    filler_budget = max(target_tokens - needle_tokens - question_tokens - reserved_tokens, 0)
    before_budget = round(filler_budget * depth)
    after_budget = filler_budget - before_budget

    before_text, next_index = _build_filler(tokenizer, rng, before_budget, start_index=0)
    after_text, _ = _build_filler(tokenizer, rng, after_budget, start_index=next_index)

    body_parts = [part for part in (before_text, needle, after_text) if part]
    transcript = "[SYNTHETIC CLASSROOM TRANSCRIPT]\n" + _join(body_parts)
    user_content = f"{transcript}\n\n[QUESTION]\n{QUESTION}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    tokens_actual = len(tokenizer.encode(user_content))
    return Probe(messages=messages, expected_code=code, tokens_actual=tokens_actual)
