# VLM Fine-Tuning with Unsloth Library

VLM Fine-Tuning with the Unsloth Library is a standalone process for
fine-tuning a vision-language model (VLM) on your own multimodal
(image and text) dataset using the [Unsloth](https://github.com/unslothai/unsloth)
library and the Low-Rank Adaptation (LoRA) fine-tuning method, and
running inference with the resulting adapter.

This directory is **not integrated** with the rest of
`industrial-edge-insights-multimodal`; it does not wire into the
`docker-compose*.yml` stacks, `configs/`, or the vLLM serving setup in this
repository. It is a self-contained data preparation, fine-tuning, and inference
workflow that you run independently (e.g. on a development box or training server)
to produce a LoRA adapter. Once you have the adapter, you can serve it with the
existing configuration in [`docker-compose-vllm.yml`](../../docker-compose-vllm.yml),
or with any OpenAI-compatible VLM server that supports LoRA adapters.

## Directory Layout

```
vlm-fine-tuning/
├── README.md                  # this file
├── requirements.txt           # pinned Python dependencies
├── common.py                  # shared chat-format and device-detection helpers
├── prepare_weld_dataset.py    # weld-specific dataset preparation
├── train_qwen.py               # Generic LoRA fine-tuning using the Unsloth library and Transformer Reinforcement Learning (TRL) trainer
└── infer_qwen.py               # Generic standalone inference
```

> **Notes**:
> Generated artifacts are written to the directories specified by
> `--output-dir` and `--dataset-path` that you pass on the command line,
> for example, `processed_dataset/` and `qwen_3.5_2b_adapter/`.
> If you fork the `vlm-fine-tuning` directory into your own repository, add
> `processed_dataset/`, `*_adapter/`, `checkpoint-*/`, and downloaded
> datasets and images to `.gitignore`. Do not commit these generated artifacts.

## Guides

For prerequisites, setup, the expected dataset format, the fine-tuning and
inference steps and flags, and troubleshooting, see the published how-to
guides — this keeps the full instructions in one place instead of
duplicated here:

- [Fine-Tune a VLM with Unsloth Library](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.2.0/manufacturing-ai-suite/industrial-edge-insights-multimodal/docs/user-guide/how-to-guides/how-to-fine-tune-vlm.md) —
  the generic, domain-agnostic flow implemented by `train_qwen.py` and
  `infer_qwen.py`.
- [Fine-Tune a VLM with Unsloth Library — Weld Usecase](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.2.0/manufacturing-ai-suite/industrial-edge-insights-multimodal/docs/user-guide/how-to-guides/how-to-fine-tune-vlm-weld-usecase.md) —
  a concrete instance of that flow applied to a weld-defect visual
  inspection dataset, built on `prepare_weld_dataset.py`.

## License

See [VLM Fine-Tuning with Unsloth Library — License](./../../docs/user-guide/how-to-guides/how-to-fine-tune-vlm.md#license).
