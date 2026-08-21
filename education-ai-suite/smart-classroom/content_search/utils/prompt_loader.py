#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
from functools import lru_cache
from typing import Optional

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


@lru_cache(maxsize=None)
def _load_chunk_prompt(lang: str) -> str:
    path = os.path.join(_PROMPTS_DIR, "video_summary", lang, "chunk.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().rstrip("\n")


def get_default_video_summary_prompt(language: Optional[str] = None) -> str:
    """Load the per-chunk video summary prompt, falling back to English."""
    lang = (language or os.getenv("APP_LANGUAGE", "en")).lower()
    try:
        return _load_chunk_prompt(lang)
    except FileNotFoundError:
        return _load_chunk_prompt("en")
