#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Run inference with a Qwen vision-language model (base model or a fine-tuned
LoRA adapter produced by train_qwen.py) using Unsloth.

Two input modes are supported:
    1. Dataset mode (default): pull N samples from a parquet split produced by
       prepare_weld_dataset.py and reuse their image + prompt (or an override
       instruction).
    2. Single-image mode: pass --image and --instruction to run inference on
       an arbitrary weld image outside the prepared dataset.

Usage:
    # Run the first 5 test-split samples through a saved adapter
    python infer_qwen.py \\
        --model-path qwen_3.5_2b_adapter \\
        --dataset-path processed_dataset/parquet \\
        --split test \\
        --num-samples 5

    # Run a single external image through the base model
    python infer_qwen.py \\
        --model-path unsloth/Qwen3.5-2B \\
        --image /path/to/weld.jpg \\
        --instruction "Analyze this weld image for quality and identify any anomalies."
"""

from __future__ import annotations

import argparse

from datasets import load_dataset
from PIL import Image
from transformers import TextStreamer

from unsloth import FastVisionModel

from common import build_inference_messages
from common import detect_device
from common import get_sample_prompt

DEFAULT_MODEL_PATH = "unsloth/Qwen3.5-2B"
DEFAULT_DATASET_PATH = "processed_dataset/parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Unsloth-based inference with a base or fine-tuned "
        "Qwen VLM on weld images."
    )
    parser.add_argument(
        "--model-path",
        default=DEFAULT_MODEL_PATH,
        help="Base model repo id, or a local directory containing a saved "
        "LoRA adapter (as produced by train_qwen.py).",
    )
    parser.add_argument("--dataset-path", default=DEFAULT_DATASET_PATH)
    parser.add_argument(
        "--split", default="test", choices=["train", "validation", "test"]
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=5,
        help="Number of dataset samples to run inference on (dataset mode only).",
    )
    parser.add_argument(
        "--sample-index",
        type=int,
        default=None,
        help="Run a single specific sample index instead of the first --num-samples.",
    )
    parser.add_argument(
        "--image",
        default=None,
        help="Path to a standalone image file. When set, runs single-image "
        "mode instead of pulling samples from --dataset-path.",
    )
    parser.add_argument(
        "--instruction",
        default=None,
        help="Override the user prompt. Required in single-image mode.",
    )
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=1.5)
    parser.add_argument("--min-p", type=float, default=0.1)
    parser.add_argument(
        "--load-in-4bit",
        action="store_true",
        default=True,
        help="Load the model with 4-bit quantization (default: on).",
    )
    return parser.parse_args()


def load_model(model_path: str, load_in_4bit: bool):
    model, tokenizer = FastVisionModel.from_pretrained(
        model_path,
        load_in_4bit=load_in_4bit,
    )
    FastVisionModel.for_inference(model)
    return model, tokenizer


def run_inference(
    model,
    tokenizer,
    image,
    messages,
    device: str,
    max_new_tokens: int,
    temperature: float,
    min_p: float,
):
    input_text = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
    inputs = tokenizer(
        image,
        input_text,
        add_special_tokens=False,
        return_tensors="pt",
    ).to(device)

    streamer = TextStreamer(tokenizer, skip_prompt=True)
    return model.generate(
        **inputs,
        streamer=streamer,
        max_new_tokens=max_new_tokens,
        use_cache=True,
        temperature=temperature,
        min_p=min_p,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.eos_token_id,
    )


def run_single_image(args, model, tokenizer, device):
    if not args.instruction:
        raise ValueError("--instruction is required when using --image.")

    image = Image.open(args.image).convert("RGB")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": args.instruction},
            ],
        }
    ]
    run_inference(
        model,
        tokenizer,
        image,
        messages,
        device,
        args.max_new_tokens,
        args.temperature,
        args.min_p,
    )


def run_dataset_samples(args, model, tokenizer, device):
    dataset = load_dataset(args.dataset_path, split=args.split)

    if args.sample_index is not None:
        indices = [args.sample_index]
    else:
        indices = list(range(min(args.num_samples, len(dataset))))

    for idx in indices:
        sample = dataset[idx]
        instruction = args.instruction or get_sample_prompt(sample)
        messages = build_inference_messages(sample, instruction_override=instruction)

        print(f"\n=== Sample {idx} ({args.split}) ===")
        print(f"Instruction: {instruction}")
        run_inference(
            model,
            tokenizer,
            sample["image"],
            messages,
            device,
            args.max_new_tokens,
            args.temperature,
            args.min_p,
        )
        print("\n" + "=" * 60)


def main() -> None:
    args = parse_args()
    device = detect_device()
    print(f"Using device: {device}")
    print(f"Loading model/adapter from: {args.model_path}")
    model, tokenizer = load_model(args.model_path, args.load_in_4bit)

    if args.image:
        run_single_image(args, model, tokenizer, device)
    else:
        run_dataset_samples(args, model, tokenizer, device)


if __name__ == "__main__":
    main()
