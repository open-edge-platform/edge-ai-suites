# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import os


APP_DISPLAY_NAME = os.getenv("APP_DISPLAY_NAME", "Live Video Captioning RAG")
APP_PORT = int(os.getenv("APP_PORT", "4172"))
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "4173"))
DEBUG = bool(int(os.getenv("DEBUG", "0")))


def _read_rag_chatbot_mode() -> str:
    """Return canonical RAG chatbot mode: 'embedded' or 'detached'."""
    raw = os.getenv("RAG_CHATBOT_MODE", "detached")
    mode = raw.strip().lower()
    return mode if mode in {"embedded", "detached"} else "detached"

BASE_DIR = Path(__file__).parent.parent
UI_DIR = BASE_DIR / "ui"

LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "")
PROMPT_TEMPLATE_PATH = os.getenv("PROMPT_TEMPLATE_PATH", "")
LLM_DEVICE = os.getenv("LLM_DEVICE", "cpu")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
TOP_K = int (os.getenv("TOP_K", "1"))
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD")) if os.getenv("SCORE_THRESHOLD", "").strip() else 0.3
CACHE_DIR = os.getenv("CACHE_DIR", "/tmp/model_cache")
MAX_PROMPT_LEN = int(os.getenv("MAX_PROMPT_LEN", "1024"))

# VDMS
VDMS_HOST = os.getenv("VDMS_HOST", "")
VDMS_PORT = int(os.getenv("VDMS_PORT", "5555"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "")
EMBEDDING_HOST = os.getenv("EMBEDDING_HOST", "")
EMBEDDING_HOST_PORT = int(os.getenv("EMBEDDING_HOST_PORT", "8000"))
EMBEDDING_LENGTH = int(os.getenv("EMBEDDING_LENGTH", "0"))

# UI embedding policy for the RAG frontend.
RAG_CHATBOT_MODE = _read_rag_chatbot_mode()