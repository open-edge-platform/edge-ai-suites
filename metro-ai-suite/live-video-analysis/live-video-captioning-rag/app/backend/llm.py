# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from .config import (
    LLM_MODEL_ID,
    LLM_DEVICE,
    MAX_TOKENS,
    CACHE_DIR,
)
from langchain_huggingface import HuggingFacePipeline
import os


def initialize_llm():
    llm = HuggingFacePipeline.from_model_id(
        model_id=os.path.join(CACHE_DIR, LLM_MODEL_ID),
        task="text-generation",
        backend="openvino",
        model_kwargs={
            "device": LLM_DEVICE,
            "ov_config": {
                "PERFORMANCE_HINT": "LATENCY",
                "NUM_STREAMS": "1",
                "CACHE_DIR": os.path.join(CACHE_DIR, LLM_MODEL_ID, "model_cache"),
            },
            "trust_remote_code": True,
        },
        pipeline_kwargs={"max_new_tokens": MAX_TOKENS},
    )

    if llm.pipeline.tokenizer.eos_token_id:
        llm.pipeline.tokenizer.pad_token_id = llm.pipeline.tokenizer.eos_token_id

    return llm