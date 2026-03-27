# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import os


APP_DISPLAY_NAME = os.getenv("APP_DISPLAY_NAME", "Live Video Captioning RAG")
APP_PORT = int(os.getenv("APP_PORT", "4172"))
DEBUG = bool(int(os.getenv("DEBUG", "0")))

BASE_DIR = Path(__file__).parent.parent
UI_DIR = BASE_DIR / "ui"

LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "")
PROMPT_TEMPLATE_PATH = os.getenv("PROMPT_TEMPLATE_PATH", "")
LLM_DEVICE = os.getenv("LLM_DEVICE", "cpu")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
TOP_K = int (os.getenv("TOP_K", "1"))
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD")) if os.getenv("SCORE_THRESHOLD", "").strip() else 0.3
CACHE_DIR = os.getenv("CACHE_DIR", "/tmp/model_cache")

# VDMS
VDMS_HOST = os.getenv("VDMS_HOST", "")
VDMS_PORT = int(os.getenv("VDMS_PORT", "5555"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "")
EMBEDDING_HOST = os.getenv("EMBEDDING_HOST", "")
EMBEDDING_HOST_PORT = int(os.getenv("EMBEDDING_HOST_PORT", "8000"))
EMBEDDING_LENGTH = int(os.getenv("EMBEDDING_LENGTH", "0"))