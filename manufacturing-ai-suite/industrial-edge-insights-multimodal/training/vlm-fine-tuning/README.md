# VLM Fine-Tuning with Unsloth

Standalone process for fine-tuning a vision-language
model (VLM) on your own multimodal (image + text) dataset using
[Unsloth](https://github.com/unslothai/unsloth) + LoRA, and running
inference with the resulting adapter.

This directory is **not integrated** with the rest of
`industrial-edge-insights-multimodal` — it does not wire into the
`docker-compose*.yml` stacks, `configs/`, or the vLLM serving setup in this
repo. It is a self-contained data-prep + fine-tuning + inference workflow you
run independently (e.g. on a dev box or training server) to produce a LoRA
adapter. Once you have an adapter, you can serve it with the existing
[`docker-compose-vllm.yml`](../../docker-compose-vllm.yml) in this repo, or with
any OpenAI-compatible VLM server that supports LoRA adapters.

## Directory Layout

```
vlm-fine-tuning/
├── README.md                  # this file
├── requirements.txt           # pinned Python dependencies
├── common.py                  # shared chat-format / device-detection helpers
├── prepare_weld_dataset.py    # weld-specific dataset prep
├── train_qwen.py               # Generic LoRA fine-tuning (Unsloth + TRL)
└── infer_qwen.py               # Generic standalone inference
```

Generated artifacts (not checked in — see `.gitignore` note below) land in
whatever `--output-dir` / `--dataset-path` you pass on the command line,
e.g. `processed_dataset/` and `qwen_3.5_2b_adapter/`.

> If you fork this into your own repo, add `processed_dataset/`,
> `*_adapter/`, `checkpoint-*/`, and any downloaded datasets/images to
> `.gitignore` — none of these generated artifacts should be committed.

## Guides

For prerequisites, setup, the expected dataset format, the fine-tuning and
inference steps and flags, and troubleshooting, see the published how-to
guides — this keeps the full instructions in one place instead of
duplicated here:

- [Fine-Tune a VLM with Unsloth](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.2.0/manufacturing-ai-suite/industrial-edge-insights-multimodal/docs/user-guide/how-to-guides/how-to-fine-tune-vlm.md) —
  the generic, domain-agnostic flow implemented by `train_qwen.py` and
  `infer_qwen.py`.
- [Fine-Tune a VLM with Unsloth — Weld Usecase](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.2.0/manufacturing-ai-suite/industrial-edge-insights-multimodal/docs/user-guide/how-to-guides/how-to-fine-tune-vlm-weld-usecase.md) —
  a concrete instance of that flow applied to a weld-defect visual
  inspection dataset, built on `prepare_weld_dataset.py`.

## License

Third-party components used by the scripts in this directory (see
`requirements.txt`), each under their own upstream license:

- [Unsloth](https://github.com/unslothai/unsloth) — Apache-2.0
- [Hugging Face `transformers`](https://github.com/huggingface/transformers) — Apache-2.0
- [Hugging Face `datasets`](https://github.com/huggingface/datasets) — Apache-2.0
- [TRL](https://github.com/huggingface/trl) — Apache-2.0
- [PEFT](https://github.com/huggingface/peft) — Apache-2.0
- [PyTorch](https://github.com/pytorch/pytorch) — BSD-3-Clause

For the license of any dataset used with this toolkit, see the dataset's
own license terms — e.g. for the weld worked example, see the
[Fine-Tune a VLM with Unsloth — Weld Usecase](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.2.0/manufacturing-ai-suite/industrial-edge-insights-multimodal/docs/user-guide/how-to-guides/how-to-fine-tune-vlm-weld-usecase.md#license--dataset-attribution)
section of the guide.
