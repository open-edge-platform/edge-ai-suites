<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Edge Workloads and Benchmarks Guide

## Overview

The [Edge Workloads and Benchmarks](https://github.com/open-edge-platform/edge-workloads-and-benchmarks) suite validates Intel edge platform performance across four workload categories: vision AI inference, hardware-accelerated media processing, end-to-end video analytics pipelines, and generative AI. It measures throughput, latency, power consumption, and power efficiency across CPU, GPU, and NPU devices.

Use this guide after provisioning an edge node with the Infrastructure software to quantify platform performance and validate hardware acceleration readiness.

## Benchmark Categories

| Category | What It Measures | Devices | Backend |
|----------|-----------------|---------|---------|
| **Vision Benchmarks** | AI model inference (detection, classification) | CPU, GPU, NPU | OpenVINO benchmark_app |
| **Media Benchmarks** | Hardware video decode throughput and stream density | GPU (VA-API) | GStreamer + VA-API |
| **Edge AI Pipelines** | End-to-end video analytics (decode + detect + track + classify) | GPU, NPU, GPU+NPU | DL Streamer |
| **GenAI Benchmarks** | LLM/VLM token generation (1st token latency, throughput) | CPU, GPU, NPU | OpenVINO GenAI |

## Prerequisites

- [Edge Node Infrastructure software](https://github.com/open-edge-platform/edge-node-infrastructure-blueprint) deployed.
- During target system installation, set `host_type=container` in the `config-file`.
- Network connectivity for model and media downloads.

### Verify Hardware Readiness

Confirm GPU and NPU are visible before proceeding:

```bash
# GPU — should list Intel render nodes
ls /dev/dri/render*

# NPU — present only on supported platforms
ls /dev/accel/accel*

# VA-API codec support
vainfo 2>/dev/null | grep -i "profile"
```

## Setup

### Clone the Repository

```bash
git clone https://github.com/open-edge-platform/edge-workloads-and-benchmarks.git -b main
cd edge-workloads-and-benchmarks
```

### Install Prerequisites and Download Collateral

GPU and NPU drivers are already installed by the Infrastructure software provisioning step, so disable their installation by passing `INCLUDE_GPU=False INCLUDE_NPU=False` to `make prereqs`. Then download the benchmark collateral and validate the environment:

```bash
make prereqs INCLUDE_GPU=False INCLUDE_NPU=False
make collateral INCLUDE_GENAI=True
make check
```

The `make collateral` step downloads AI models and media files. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `INCLUDE_GPU` | `True` | Install GPU compute drivers |
| `INCLUDE_NPU` | `True` | Install NPU drivers |
| `INCLUDE_VISION` | `True` | Download vision models (YOLOv11, ResNet-50, MobileNet-v2) |
| `INCLUDE_MEDIA` | `True` | Download and encode media files (H.264, H.265, 1080p, 4K) |
| `INCLUDE_GENAI` | `False` | Download GenAI models (requires Hugging Face token) |

> **Note:** GenAI models require significant storage for original Hugging Face weights plus INT8/INT4 quantized artifacts. After quantization, reclaim space by removing `~/.cache/huggingface/hub/` and temporary venvs in `tools/genai-downloader/`.

### Hugging Face Token (GenAI only)

Some GenAI models require authentication:

```bash
export HF_TOKEN=<your-hugging-face-token>
```

## Running Benchmarks

### Vision Benchmarks

Measures inference throughput (FPS), latency, and power efficiency for detection models (YOLOv11n/m, YOLOv5m) and classification models (ResNet-50, MobileNet-v2), all at INT8 precision.

```bash
cd workloads/vision-benchmarks && make benchmarks
cd ../..
```

Execution modes: `tput` (maximum throughput) and `latency` (single-inference). Batch sizes: 1, 8, 16. Supports GPU+NPU concurrent mode for aggregate platform throughput.

### Media Benchmarks

Measures hardware-accelerated video decode performance using VA-API across H.265 and H.264 codecs at 1080p and 4K, scaling from 1 to 8 parallel streams.

```bash
cd workloads/media-benchmarks && make benchmarks
cd ../..
```

Key metrics: decode throughput (FPS), maximum stream density at 30 FPS target, power consumption.

### Edge AI Pipelines

Measures end-to-end video analytics pipeline performance using DL Streamer. Each pipeline chains media decode, preprocessing, object detection, tracking, and classification over 1080p HEVC input.

```bash
cd workloads/edge-ai-pipelines && make benchmarks
cd ../..
```

Three intensity levels (Light, Medium, Heavy) with increasing model complexity. Device placement modes: GPU-only, NPU-only, GPU+NPU split, and GPU+NPU concurrent.

### GenAI Benchmarks

Measures generative AI inference for LLMs (Llama 3.2 3B, DeepSeek-R1-1.5B, Mistral 7B) and VLMs (Phi-4 Multimodal, Gemma 3 4B, MiniCPM-V 2.6) at INT8_ASYM and INT4_SYM_CW precisions.

```bash
cd workloads/genai-benchmarks && make benchmarks
cd ../..
```

Key metrics: 1st token latency (ms), 2nd token throughput (tokens/s), power consumption (W), and power efficiency (tokens/s/W).

## Benchmark Execution Options

Common parameters available across all workload categories:

| Parameter | Description |
|-----------|-------------|
| `DRY_RUN=True` | List all test configurations without executing |
| `RESUME=True` | Skip tests that already have results |
| `DURATION=<seconds>` | Set test duration (default: 60-120s) |
| `POWER=True` | Enable power measurement (requires sudo) |
| `CORES=pcore` | Pin execution to performance cores |
| `CORES=ecore` | Pin execution to efficiency cores |
| `CORES=0-11` | Pin to specific core range |
| `CLEAR=True` | Remove previous results before running |

Example — dry run to preview vision test matrix:

```bash
cd workloads/vision-benchmarks && make benchmarks DRY_RUN=True
```

Example — run media benchmarks with power measurement, resuming from prior results:

```bash
cd workloads/media-benchmarks && make benchmarks POWER=True RESUME=True
```

## Generating Reports

After running benchmarks, generate an interactive HTML dashboard:

```bash
make report
make serve
```

The report is accessible at `http://localhost:8000` and includes per-model throughput and latency charts, device comparisons, power efficiency rankings, and stream density results.

Check which configurations have completed:

```bash
make status
```

Results are stored under each workload directory at `workloads/<category>/results/` in JSON format, organized by model, device, mode, and batch size.

## Cleanup

```bash
make clean-results    # Remove benchmark results only
make clean-all        # Remove all generated content (models, media, results)
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `make check` reports missing GPU | Verify drivers: `sudo apt install intel-opencl-icd intel-media-va-driver-non-free` |
| NPU not detected | Check kernel module: `lsmod \| grep intel_vpu` and device nodes: `ls /dev/accel/` |
| GenAI download fails | Verify `HF_TOKEN` is set and has access to gated models |
| Low GPU throughput | Ensure no other workloads are using the GPU; check `intel_gpu_top` |
| Power measurement fails | `POWER=True` requires sudo access for RAPL/hwmon readings |
| Docker permission denied | Add user to docker group: `sudo usermod -aG docker $USER` and re-login |
| Insufficient storage | Run without GenAI (`INCLUDE_GENAI=False`) or remove HF cache after conversion |

## References

- [Edge Workloads and Benchmarks Repository](https://github.com/open-edge-platform/edge-workloads-and-benchmarks)
- [OpenVINO Toolkit](https://docs.openvino.ai/)
- [DL Streamer Documentation](https://github.com/open-edge-platform/dlstreamer)
- [Container Device Interface Guide](./configure-cdi.md) — CDI setup for GPU/NPU access
- [DL Streamer Pipelines Guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/how-to/build-dlstreamer-pipelines.html) — Building custom pipelines
- [Platform Capabilities](./platform-capabilities.md) — Hardware and software stack details
