#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Shared helpers for converting the weld VLM parquet dataset (produced by
prepare_weld_dataset.py) into Unsloth/Qwen chat-template message formats,
used by both train_qwen.py and infer_qwen.py.
"""

from __future__ import annotations

import json
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import torch


def detect_device() -> str:
    """Pick the best available accelerator: Intel XPU > CUDA > CPU."""
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        return "xpu"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def parse_conversation_json(raw_conversation: Any) -> List[Dict[str, Any]]:
    """Parse the dataset's `conversation_json` column into a messages list."""
    if isinstance(raw_conversation, str):
        return json.loads(raw_conversation)
    if isinstance(raw_conversation, list):
        return raw_conversation
    raise TypeError(
        f"Unsupported conversation_json type: {type(raw_conversation).__name__}"
    )


def extract_text_from_content(content_items: Any) -> str:
    """Pull the first text segment out of a chat-template content list."""
    if isinstance(content_items, str):
        return content_items
    for item in content_items or []:
        if isinstance(item, dict) and item.get("type") == "text":
            return item.get("text", "")
    return ""


def convert_to_conversation(sample: Dict[str, Any]) -> Dict[str, Any]:
    """Convert one dataset row into an Unsloth SFTTrainer training conversation."""
    parsed_conversation = parse_conversation_json(sample["conversation_json"])
    messages = []

    for message in parsed_conversation:
        role = message.get("role")
        if role == "user":
            user_content = []
            for item in message.get("content", []):
                if item.get("type") == "image":
                    user_content.append({"type": "image", "image": sample["image"]})
                elif item.get("type") == "text":
                    user_content.append({"type": "text", "text": item.get("text", "")})
            messages.append({"role": "user", "content": user_content})
        elif role in {"system", "assistant"}:
            messages.append({"role": role, "content": message.get("content", "")})

    return {"messages": messages}


def get_sample_prompt(sample: Dict[str, Any]) -> str:
    """Return the raw user prompt text stored in a dataset row's conversation."""
    parsed_conversation = parse_conversation_json(sample["conversation_json"])
    for message in parsed_conversation:
        if message.get("role") == "user":
            return extract_text_from_content(message.get("content", []))
    raise ValueError("No user prompt found in conversation_json")


def build_inference_messages(
    sample: Dict[str, Any], instruction_override: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Build a chat-template message list for running inference on one sample."""
    parsed_conversation = parse_conversation_json(sample["conversation_json"])
    system_text = None
    user_text = None

    for message in parsed_conversation:
        role = message.get("role")
        if role == "system" and system_text is None:
            system_text = message.get("content", "")
        elif role == "user" and user_text is None:
            user_text = extract_text_from_content(message.get("content", []))

    if user_text is None:
        raise ValueError("No user message found in conversation_json")

    user_text = instruction_override or user_text

    messages = []
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": user_text},
            ],
        }
    )
    return messages


def validate_sample_index(dataset, sample_index: int) -> None:
    if not 0 <= sample_index < len(dataset):
        raise IndexError(
            f"sample-index {sample_index} is out of range for dataset size {len(dataset)}"
        )
