#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

"""
Fine-tune a Qwen vision-language model on the weld VLM dataset using
Unsloth + LoRA + TRL's SFTTrainer.

Input:
    A parquet dataset directory produced by prepare_weld_dataset.py, containing
    train/validation/test splits with an `image` column and a `conversation_json`
    column (system/user/assistant chat messages).

Output:
    A LoRA adapter (and tokenizer) saved to --output-dir, loadable later by
    infer_qwen.py or served via vLLM with `--enable-lora`.

Usage:
    python train_qwen.py \\
        --model-name unsloth/Qwen3.5-2B \\
        --dataset-path processed_dataset/parquet \\
        --output-dir qwen_3.5_2b_adapter \\
        --learning-rate 2e-4 \\
        --num-train-epochs 2
"""

from __future__ import annotations

import argparse

from datasets import load_dataset
# Redundant by mandatorily import unsloth before importing trl
# EOS token default changes if trl imported before unsloth
# causing an exception in SFTTrainer
import unsloth

from trl import SFTConfig
from trl import SFTTrainer

from unsloth import FastVisionModel
from unsloth.trainer import UnslothVisionDataCollator

from common import convert_to_conversation
from common import detect_device
from common import validate_sample_index

DEFAULT_MODEL_NAME = "unsloth/Qwen3.5-2B"
DEFAULT_DATASET_PATH = "processed_dataset/parquet"
DEFAULT_OUTPUT_DIR = "qwen_3.5_2b_adapter"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune a Qwen vision-language model on the weld VLM dataset."
    )
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--dataset-path", default=DEFAULT_DATASET_PATH)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sample-index", type=int, default=0)
    parser.add_argument("--num-train-epochs", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument(
        "--per-device-train-batch-size", type=int, default=4
    )
    parser.add_argument("--per-device-eval-batch-size", type=int, default=4)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument(
        "--load-in-4bit",
        action="store_true",
        default=True,
        help="Load the base model with 4-bit quantization (default: on).",
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Load and print the first converted training sample, then exit "
        "without building the model or training.",
    )
    parser.add_argument(
        "--skip-save",
        action="store_true",
        help="Do not save the trained adapter/tokenizer to --output-dir.",
    )
    return parser.parse_args()


def build_model(model_name: str, load_in_4bit: bool, lora_r: int, lora_alpha: int):
    model, tokenizer = FastVisionModel.from_pretrained(
        model_name,
        load_in_4bit=load_in_4bit,
        use_gradient_checkpointing="unsloth",
    )

    model = FastVisionModel.get_peft_model(
        model,
        finetune_vision_layers=True,
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=0,
        bias="none",
        random_state=3407,
        use_rslora=False,
        loftq_config=None,
    )
    return model, tokenizer


def main() -> None:
    args = parse_args()
    device = detect_device()
    optim_name = "adamw_8bit" if device == "cuda" else "adamw_torch"

    train_dataset = load_dataset(args.dataset_path, split="train")
    eval_dataset = load_dataset(args.dataset_path, split="validation")
    validate_sample_index(train_dataset, args.sample_index)

    converted_train_dataset = [
        convert_to_conversation(sample) for sample in train_dataset
    ]
    converted_eval_dataset = [
        convert_to_conversation(sample) for sample in eval_dataset
    ]

    print(f"Loaded {len(train_dataset)} training samples from {args.dataset_path}")
    print(f"Loaded {len(eval_dataset)} evaluation samples from {args.dataset_path}")
    print(f"Using device: {device}")
    print(converted_train_dataset[args.sample_index])

    if args.preview_only:
        return

    print(f"Building model from base: {args.model_name} ...")
    model, tokenizer = build_model(
        args.model_name, args.load_in_4bit, args.lora_r, args.lora_alpha
    )

    FastVisionModel.for_training(model)
    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        data_collator=UnslothVisionDataCollator(model, tokenizer, resize="max"),
        train_dataset=converted_train_dataset,
        eval_dataset=converted_eval_dataset,
        args=SFTConfig(
            skip_memory_metrics=False,
            per_device_train_batch_size=args.per_device_train_batch_size,
            per_device_eval_batch_size=args.per_device_eval_batch_size,
            gradient_accumulation_steps=args.gradient_accumulation_steps,
            warmup_steps=5,
            num_train_epochs=args.num_train_epochs,
            learning_rate=args.learning_rate,
            logging_strategy="steps",
            logging_steps=5,
            optim=optim_name,
            eval_strategy="steps",
            eval_steps=50,
            save_strategy="steps",
            save_steps=50,
            weight_decay=0.001,
            lr_scheduler_type="linear",
            seed=3407,
            output_dir=args.output_dir,
            report_to="none",
            remove_unused_columns=False,
            dataset_text_field="",
            dataset_kwargs={"skip_prepare_dataset": True},
            max_length=args.max_seq_length,
        ),
    )

    trainer_stats = trainer.train()
    print(trainer_stats)

    if not args.skip_save:
        model.save_pretrained(args.output_dir)
        tokenizer.save_pretrained(args.output_dir)
        print(f"Adapter and tokenizer saved to: {args.output_dir}")
        print(
            "Run infer_qwen.py --model-path "
            f"{args.output_dir} to try it out."
        )


if __name__ == "__main__":
    main()
