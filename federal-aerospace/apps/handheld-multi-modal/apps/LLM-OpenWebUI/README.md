<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->
# OpenVINO™ Model Server and Open WebUI-based Chat UI

OpenVINO™ model server-accelerated LLM inference on Intel iGPU with a web chat interface.

## Stack

| Service | Image | Role |
|---------|-------|------|
| `ovms` | `openvino/model_server:latest-gpu` | Serves OpenVINO-optimized LLMs via OpenAI-compatible REST API |
| `open-webui` | `ghcr.io/open-webui/open-webui:main` | Chat UI connected to OVMS |

Both services are defined in the root [`docker-compose.yml`](../../docker-compose.yml) and share the `fedaero` network.

## APIs

You can only access the Open WebUI chat UI through  the NGINX TLS reverse proxy. The container port is not exposed to the host.

| Endpoint                                                   | URL                           | Notes                                                          |
|------------------------------------------------------------|-------------------------------|----------------------------------------------------------------|
| Open WebUI chat UI                                         | https://localhost:8443        | Chat UI                                                        |
| OpenVINO model server's API, compatible with OpenAI format | http://localhost:9000/v3      | Direct host access; also used internally by Open WebUI chat UI |
| OpenVINO model server metrics                              | http://localhost:6443/metrics | Prometheus metrics                                             |

## Changing the model

Edit the `--source_model` argument on the `ovms` service in the root `docker-compose.yml`.
Models are downloaded from the HuggingFace hub on first start and persisted in the `ovms_models` Docker volume.

> **NOTE** Models loaded at runtime carry their own licenses and the operator is responsible for reviewing the licenses and making sure that they are matching operator's use-case(s).

Because downloading happens on first start, OpenVINO model server accepts connections before the model is actually ready to serve requests. After changing the model, or on a fresh start, check readiness before sending inference requests.

```bash
curl http://localhost:9000/v1/config
```

When you see `"state": "AVAILABLE"`, the model is ready. Until then the model is still
downloading or loading, and inference requests will fail.

### INT4 — Fastest with the Lowest Memory (Recommended for iGPU)

| Model | Size | Notes |
|-------|------|-------|
| `OpenVINO/Phi-3.5-mini-instruct-int4-ov` | ~2 GB | Default, very fast |
| `OpenVINO/llama-3.2-3b-instruct-int4-ov` | ~2 GB | Good general use |
| `OpenVINO/mistral-7b-instruct-v0.3-int4-ov` | ~4 GB | Better quality |
| `OpenVINO/DeepSeek-R1-Distill-Qwen-1.5B-int4-ov` | ~1 GB | Tiny, fastest |
| `OpenVINO/Qwen2.5-7B-Instruct-int4-ov` | ~4 GB | Strong instruction following |

### INT8 — Better Accuracy with Moderate Memory

| Model | Size | Notes |
|-------|------|-------|
| `OpenVINO/Phi-3.5-mini-instruct-int8-ov` | ~4 GB | Balanced quality and speed |
| `OpenVINO/llama-3.2-3b-instruct-int8-ov` | ~3 GB | Good accuracy |
| `OpenVINO/mistral-7b-instruct-v0.3-int8-ov` | ~7 GB | High quality, needs more VRAM |
| `OpenVINO/Qwen2.5-7B-Instruct-int8-ov` | ~8 GB | Excellent instruction following |

### FP16 — Full Precision and Best Quality (Requires ≥16-GB memory)

| Model | Size | Notes |
|-------|------|-------|
| `OpenVINO/Phi-3.5-mini-instruct-fp16-ov` | ~8 GB | Best Phi quality |
| `OpenVINO/llama-3.2-3b-instruct-fp16-ov` | ~6 GB | Best Llama 3.2-3B quality |
| `OpenVINO/DeepSeek-R1-Distill-Qwen-7B-fp16-ov` | ~15 GB | Strong reasoning, large |
