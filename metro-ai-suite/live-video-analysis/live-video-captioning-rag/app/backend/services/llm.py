# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from ..config import (
    LLM_MODEL_ID,
    LLM_DEVICE,
    MAX_TOKENS,
    CACHE_DIR,
    MAX_PROMPT_LEN,
)
from ..utils.logger import logger
from ..integrations.ov_genai.ov_langchain_helper import OpenVINOLLM
import os


def initialize_llm():
    '''
    Initialize and return an OpenVINO LLM instance.
    Returns:
        An instance of OpenVINOLLM configured with the specified model and device.
    '''
    logger.info(f"Initializing OpenVINO LLM with model ID: {LLM_MODEL_ID} on device: {LLM_DEVICE}")
    model_dir = os.path.join(CACHE_DIR, LLM_DEVICE.lower(), LLM_MODEL_ID)
    pipeline_config = {"MAX_PROMPT_LEN": MAX_PROMPT_LEN} if LLM_DEVICE.upper() == "NPU" else {}
    llm = OpenVINOLLM.from_model_path(
        model_path = model_dir,
        device = LLM_DEVICE,
        **pipeline_config
    )
    llm.config.max_new_tokens = MAX_TOKENS

    return llm
