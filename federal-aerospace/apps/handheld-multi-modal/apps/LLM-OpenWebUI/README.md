# OpenVINO Model Server + Open WebUI

OpenVINO-accelerated LLM inference on Intel iGPU with a web chat interface.

## Stack

| Service | Image | Role |
|---------|-------|------|
| `ovms` | `openvino/model_server:latest-gpu` | Serves OpenVINO-optimized LLMs via OpenAI-compatible REST API |
| `open-webui` | `ghcr.io/open-webui/open-webui:main` | Chat UI connected to OVMS |

Both services are defined in the root [`docker-compose.yml`](../../docker-compose.yml) and share the `fedaero` network.

> Speech-to-text is handled by the standalone Whisper STT service — see [`../speech-to-text/`](../speech-to-text/).

## APIs

Open WebUI is only accessible via the nginx TLS reverse proxy. The container port is not exposed to the host.

| Endpoint | URL | Notes |
|----------|-----|-------|
| Open WebUI | https://localhost:8443 | Chat UI — browser mic enabled (via nginx) |
| OVMS OpenAI-compatible API | http://localhost:9000/v3 | Direct host access; also used internally by Open WebUI |
| OVMS metrics | http://localhost:9000/metrics | Prometheus metrics |

Check OVMS model readiness:

```bash
curl http://localhost:9000/v1/config
```

When you see `"state": "AVAILABLE"` the model is ready.

## Changing the model

Edit the `--source_model` argument on the `ovms` service in the root `docker-compose.yml`.
Models are downloaded from HuggingFace on first start and persisted in the `ovms_models` Docker volume.

### int4 — fastest, lowest memory (recommended for iGPU)

| Model | Size | Notes |
|-------|------|-------|
| `OpenVINO/Phi-3.5-mini-instruct-int4-ov` | ~2 GB | Default, very fast |
| `OpenVINO/llama-3.2-3b-instruct-int4-ov` | ~2 GB | Good general use |
| `OpenVINO/mistral-7b-instruct-v0.3-int4-ov` | ~4 GB | Better quality |
| `OpenVINO/DeepSeek-R1-Distill-Qwen-1.5B-int4-ov` | ~1 GB | Tiny, fastest |
| `OpenVINO/Qwen2.5-7B-Instruct-int4-ov` | ~4 GB | Strong instruction following |

### int8 — better accuracy, moderate memory

| Model | Size | Notes |
|-------|------|-------|
| `OpenVINO/Phi-3.5-mini-instruct-int8-ov` | ~4 GB | Balanced quality/speed |
| `OpenVINO/llama-3.2-3b-instruct-int8-ov` | ~3 GB | Good accuracy |
| `OpenVINO/mistral-7b-instruct-v0.3-int8-ov` | ~7 GB | High quality, needs more VRAM |
| `OpenVINO/Qwen2.5-7B-Instruct-int8-ov` | ~8 GB | Excellent instruction following |

### fp16 — full precision, best quality (requires ≥16 GB iGPU shared memory)

| Model | Size | Notes |
|-------|------|-------|
| `OpenVINO/Phi-3.5-mini-instruct-fp16-ov` | ~8 GB | Best Phi quality |
| `OpenVINO/llama-3.2-3b-instruct-fp16-ov` | ~6 GB | Best Llama 3.2-3B quality |
| `OpenVINO/DeepSeek-R1-Distill-Qwen-7B-fp16-ov` | ~15 GB | Strong reasoning, large |
