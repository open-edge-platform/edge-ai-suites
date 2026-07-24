# System Requirements

## Hardware

- **CPU**: x86_64. Intel Core Ultra (Meteor Lake) or newer is recommended.
  Older Intel Core / Xeon processors will run the stack but may be slower
  on OpenVINO inference paths.
- **Memory**: 32 GB RAM minimum. 64 GB recommended when running the LLM,
  reranker, ASR, and TTS together with a warm cache.
- **Disk**: 60 GB free SSD space recommended for model assets, the Hugging
  Face cache, vector storage, generated audio, and per-session storage.
  NVMe is preferred for faster first-run model export.
- **GPU (optional)**: Intel integrated GPU (Meteor Lake or newer iGPU) or
  a supported discrete GPU exposed via `/dev/dri`. The RAG LLM and reranker
  benefit most from `GPU`; `audio-analyzer` and `text-to-speech` can also be
  pinned to `GPU` for higher throughput.
- **Microphone**: Not required on the host — audio is captured by the
  browser via the Web Audio API and uploaded to `kiosk-core`.

## Operating System

- Ubuntu 22.04 LTS (validated) or a compatible Linux distribution with a
  recent kernel.
- Docker Engine and Docker Compose v2 for container deployment.
- For GPU acceleration on Linux: Intel/OpenVINO host GPU runtime
  (e.g. `intel-opencl-icd`, `level-zero`) installed on the host.

## Host Packages (Standalone Run Only)

When running `kiosk-core` and the Gradio UI directly on the host:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg alsa-utils libsndfile1
```

`audio-analyzer`, `text-to-speech`, and `rag-service` are still recommended
to run in containers even in this mode.

## Python (Standalone Run Only)

- Python 3.10 or newer.
- Dependencies installed from `requirements.txt`.

## Network

- Outbound internet access on first run to download model assets from
  Hugging Face, unless models are pre-staged under the per-service
  `models/` and `.cache/` directories.
- Inbound access on the host for the published TCP ports:
  `7860`, `8010`, `8011`, `8012`, `8020`.

## Browser

- Any modern Chromium-based browser or Firefox with permission to use the
  microphone for `http://127.0.0.1:7860`.
- The browser must be able to reach `kiosk-core` (`http://127.0.0.1:8012`)
  from the same machine, or a routable address if `kiosk-ui` is exposed
  beyond localhost.
