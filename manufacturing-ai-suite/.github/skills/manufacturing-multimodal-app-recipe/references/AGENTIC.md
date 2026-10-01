# Agentic explainability layer (optional, `{{AGENTIC}}=yes`)

An LLM/VLM layer that turns a fused anomaly verdict into a human-readable
explanation ("why was this flagged, which modality drove it, what should the
operator do"). **Off by default** — adds real GPU/memory footprint and an
extra model download, so only build it when Question 9 explicitly opts in.

**Do not re-implement the agent framework by hand** — this layer is an
overlay Compose file (reference: `docker-compose-agentic.yml` +
`docker-compose-vllm.yml`) composing three existing microservices, not new
code to write from scratch.

## Components

| Service | Image | Role |
|---|---|---|
| `apm-agent` | `intel/agent-quality-handler` | LangGraph meta-agent + worker agents; subscribes to a **batch-complete** MQTT event (not raw fusion messages) and calls the LLM to produce an explanation |
| `apm-llm` | `openvino/model_server` (OVMS) | Serves the LLM/VLM via an OpenAI-compatible `/v3` API, from a pre-converted OpenVINO IR/mediapipe graph |
| `model-download` | `intel/model-download` | Fetches the LLM weights (Hugging Face) and converts to OpenVINO IR ahead of `apm-llm` startup |
| (optional) `metrics-manager` / `prometheus` | | Only if the vertical needs LLM-usage/latency metrics — skip for a minimal Agentic add-on |

## Wiring into Fusion Analytics

`apm-agent`'s `STORAGE_SERVICE_URL` points at Fusion Analytics'
health/query API (`http://ia-fusion-analytics:8080` — the FastAPI surface
described in `FUSION.md`). Fusion Analytics (or a thin batching shim next to
it) must publish a **`apm/batch-complete`** MQTT event once it has
accumulated a batch of fused verdicts — the agent is detection-agnostic and
never subscribes to `{{FUSION_TOPIC}}` directly, only to this batch-complete
signal, so define the batch trigger (size- or time-based) explicitly in the
plan before wiring this up.

## Required env

```
LLM_MODEL_NAME=
LLM_DEVICE=GPU              # or CPU
LLM_WEIGHT_FORMAT=int4      # or fp16/int8 — must match model-download's conversion output
MODEL_PATH=/model/llm_model_agentic/openvino_models/${LLM_DEVICE_LOWER}/${LLM_WEIGHT_FORMAT_LOWER}/${LLM_MODEL_NAME}
MQTT_BATCH_TOPIC=apm/batch-complete
HUGGINGFACEHUB_API_TOKEN=   # required for gated HF models
```

`LLM_MODE=fallback` runs the agent without a live LLM (pure rule-based
templated explanation) — offer this as a lightweight alternative to standing
up OVMS/vLLM when the user just wants structured "why" text without a model.

## GPU/device requirements

Same `group_add` render-GID list as `PIPELINE.md`
(`109`/`110`/`992`/`993` + `${VIDEO_GROUP_ID}`/`${RENDER_GROUP_ID}`) plus
`/dev/dri` and `/dev/accel` device mounts on the `apm-llm` service — LLM
inference is far more memory-hungry than the vision/sensor models, so verify
available GPU/iGPU memory before enabling this layer (the reference
`Makefile`'s `check_hardware`/`check_models` targets gate this explicitly;
reuse that pattern rather than skipping validation).

## Completion criteria (Agentic layer, in addition to the base 1–11)

12. `model-download` completes and `apm-llm` health check passes
    (`GET /v3/config` returns 200) before `apm-agent` is marked healthy.
13. Publishing a synthetic `apm/batch-complete` MQTT event produces one
    explanation output in `apm-agent`'s `OUTPUT_DIR`, quoted verbatim in the
    final summary.
14. `LLM_MODE=fallback` still produces a structured explanation with no LLM
    running, if the user opted into the fallback path instead of a live
    model.
