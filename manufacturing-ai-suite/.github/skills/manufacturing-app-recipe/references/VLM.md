# VLM narrative-explanation layer (`vllm`/`agentic` modes — always on top of `multimodal`)

A bare LLM/VLM layer that turns a fused anomaly verdict into a human-readable
explanation ("why was this flagged, which modality drove it, what should the
operator do"). This is the foundation both `vllm` mode (as-is) and `agentic`
mode (wrapped by [`AGENTIC.md`](AGENTIC.md)'s orchestration overlay) build
on. Adds real GPU/memory footprint and an extra model download versus plain
`multimodal` mode.

**Do not re-implement model serving by hand** — `apm-llm` is OVMS
(OpenVINO Model Server), an existing component; only the thin explainer
call/service around it is authored here.

Bring the stack up with `make up_vllm` — not the plain `make up` target,
which omits the `docker-compose-vllm.yml` overlay this layer's services are
defined in (see [`INSTALL.md`](INSTALL.md)'s *Makefile targets* section).

## Components (bare `vllm` mode — no agent orchestration)

| Service | Image | Role |
|---|---|---|
| `apm-llm` | `openvino/model_server` (OVMS) | Serves the LLM/VLM via an OpenAI-compatible `/v3` API, from a pre-converted OpenVINO IR/mediapipe graph |
| `model-download` | `intel/model-download` | Fetches the LLM weights (Hugging Face) and converts to OpenVINO IR ahead of `apm-llm` startup |
| `vllm-explainer` (authored here, no prebuilt image) | thin Python service | subscribes to the fused-alert batch event and calls `apm-llm`'s `/v3` API directly — a single request/response per batch, no multi-step agent planning |

## Wiring into Fusion Analytics

`vllm-explainer`'s `STORAGE_SERVICE_URL` points at Fusion Analytics'
health/query API (`http://ia-fusion-analytics:8080` — the FastAPI surface
described in [`FUSION.md`](FUSION.md)). Fusion Analytics itself owns
batching fused verdicts and publishes a **batch-complete** MQTT event
(`MQTT_BATCH_TOPIC`, e.g. `vllm/batch-complete`) once the configured trigger
fires — see FUSION.md's *Batching for the explanation layer* section for
the exact mechanism and required env (`BATCH_TRIGGER_MODE`/`BATCH_SIZE`/
`BATCH_INTERVAL_S`); there is no separate batching service to build.

`vllm-explainer`'s own logic is intentionally simple: on a batch-complete
event, fetch the batch from `STORAGE_SERVICE_URL`, build one prompt
(fused verdict + both modalities' evidence), call `apm-llm`'s `/v3/chat/completions`
(or `/v3/completions`) once, and write the response text to
`OUTPUT_DIR`/InfluxDB/a dedicated MQTT topic. No LangGraph, no multi-agent
planning, no tool-calling loop — that sophistication is what `agentic` mode
adds via [`AGENTIC.md`](AGENTIC.md).

## Required env

```
LLM_MODEL_NAME={{LLM_MODEL_NAME}}
LLM_DEVICE={{LLM_DEVICE}}           # GPU (default) or CPU
LLM_WEIGHT_FORMAT={{LLM_WEIGHT_FORMAT}}   # int4 (default) or fp16/int8 — must match model-download's conversion output
MODEL_PATH=/model/llm_model/openvino_models/${LLM_DEVICE_LOWER}/${LLM_WEIGHT_FORMAT_LOWER}/${LLM_MODEL_NAME}
MQTT_BATCH_TOPIC=vllm/batch-complete
HUGGINGFACEHUB_API_TOKEN=   # required for gated HF models
```

`LLM_MODE=fallback` runs `vllm-explainer` without a live LLM (pure rule-based
templated explanation) — offer this as a lightweight alternative to standing
up OVMS when the user just wants structured "why" text without a model.

## GPU/device requirements

Same `group_add` render-GID list as [`PIPELINE.md`](PIPELINE.md)
(`109`/`110`/`992`/`993` + `${VIDEO_GROUP_ID}`/`${RENDER_GROUP_ID}`) plus
`/dev/dri` and `/dev/accel` device mounts on the `apm-llm` service — LLM
inference is far more memory-hungry than the vision/sensor models, so verify
available GPU/iGPU memory before enabling this layer. Reuse the reference
`Makefile`'s `check_hardware`/`check_models` targets to gate this explicitly
rather than skipping validation.

## Completion criteria (`vllm` mode, in addition to the base `multimodal` criteria 1–9)

10. `model-download` completes and `apm-llm`'s health check passes
    (`GET /v3/config` returns 200) before `vllm-explainer` is marked healthy.
11. Publishing a synthetic batch-complete MQTT event produces one
    explanation output in `vllm-explainer`'s `OUTPUT_DIR`, quoted verbatim in
    the final summary.
12. `LLM_MODE=fallback` (if selected) still produces a structured
    explanation with no LLM running.
