# Model Preparation

Real Time Scene Understanding requires an alert VLM and a second, video-capable VLM for deep analysis under `ov_models/`.

The provided helper uses the ephemeral model-download container flow from the [Model Download project](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/index.html) in Open Edge Platform. It starts a temporary container, downloads or converts the model, writes the files to this repository, and removes the container when finished. No separate model-download setup is required.

## Prerequisites

- Docker is installed and running.
- `curl` and `python3` are available on the host.
- Commands are run from the `real-time-scene-understanding` directory.
- For gated Hugging Face models, set a token first:

	```bash
	export HUGGINGFACEHUB_API_TOKEN="your-huggingface-token"
	```

## Usage

Use the helper script with the following arguments:

```bash
./model_download_scripts/download_models.sh \
	--model <huggingface-model-id> \
	--type vlm \
	--weight-format <int4|int8|fp16> \
	--device <CPU|GPU|NPU>
```

**Parameters:**
- `--model`: Hugging Face model identifier (for example, `Qwen/Qwen3-VL-2B-Instruct`).
- `--type`: Model category. Use `vlm` for Vision Language Models.
- `--weight-format`: Precision/quantization format. Supported values are `int4`, `int8`, and `fp16`.
- `--device`: Target conversion device (for example, `CPU`, `GPU`, or `NPU`, depending on host support).

**Weight format options:**

Supported weight formats are `int4`, `int8`, and `fp16`. The default is `int8`.

| Format | Memory use | Accuracy | When to use |
|--------|-----------|----------|-------------|
| `int4` | Lowest | Lower | Memory-constrained systems |
| `int8` | Medium | Good | Recommended default |
| `fp16` | Highest | Best | Maximum accuracy, more RAM required |

## Download a VLM Model

Use the following commands to run conversion for the desired target device. Generated models are stored under `ov_models/`.

- For CPU:

	```bash
	./model_download_scripts/download_models.sh \
		--model Qwen/Qwen3-VL-2B-Instruct \
		--type vlm \
		--weight-format int4 \
		--device CPU
	```

- For GPU:

	```bash
	./model_download_scripts/download_models.sh \
		--model Qwen/Qwen3-VL-8B-Instruct \
		--type vlm \
		--weight-format int4 \
		--device GPU
	```

- For NPU, use `int4` quantization:

	```bash
	./model_download_scripts/download_models.sh \
		--model Qwen/Qwen3-VL-2B-Instruct \
		--type vlm \
		--weight-format int4 \
		--device NPU
	```

	> Note: NPU currently requires `int4` quantization for VLM conversion. If you pass `--device NPU` with `int8` or `fp16`, the script automatically overrides it to `int4`.
	> Note: Use this NPU conversion only if `Qwen/Qwen3-VL-2B-Instruct` is supported for your hardware and OVMS/OpenVINO version. NPU support varies by model; check the [OpenVINO Model Support Page](https://docs.openvino.ai/2026/documentation/compatibility-and-support/supported-models.html) before converting.

You can also download and convert for multiple target devices in a single command by passing a comma-separated `--device` list:

```bash
./model_download_scripts/download_models.sh \
	--model Qwen/Qwen3-VL-2B-Instruct \
	--type vlm \
	--weight-format int4 \
	--device CPU,GPU
```

Downloaded VLM models are stored under per-device directories in `ov_models/`.

Set `ALERT_VLM_MODEL`, `ALERT_VLM_DEVICE`, `DEEP_ANALYZER_MODEL`, and `DEEP_ANALYZER_DEVICE` in `.env` to match the downloaded directory names and device folders. The alert model is used for frame-level filtering; the deep-analyzer model must support video input.

The application loads each VLM from the device-specific directory that matches its model and device settings in `.env`.

Example:

| `--device` flag | Example output directory | VLM device tag |
|---|---|---|
| `CPU` (or omitted) | `ov_models/cpu/Qwen3-VL-2B-Instruct` | `CPU` |
| `GPU` | `ov_models/gpu/Qwen3-VL-8B-Instruct` | `GPU` |
| `NPU` | `ov_models/npu/Qwen3-VL-2B-Instruct` | `NPU` |

### Models Used in This Guide

The setup examples use these VLMs:

| Pipeline | Model Name | Device |
| --- | --- | --- |
| Alert VLM | Qwen/Qwen3-VL-2B-Instruct | CPU |
| Deep analyzer | Qwen/Qwen3-VL-8B-Instruct | GPU |

> Note: `OVMS_RELEASE_TAG` in `.env` controls the OVMS image version used by the model download/conversion flow. Consult the official OpenVINO documentation for supported models and corresponding OVMS versions. Using a different tag can change the bundled `transformers`/OpenVINO toolchain and may cause conversion failures.
>
> Note: If you want to use newer Hugging Face models, you may need a newer OVMS/OpenVINO stack for conversion, which means updating `OVMS_RELEASE_TAG`.

As of the time of writing, the latest stable DL Streamer release is `2026.1.0`, built on top of OpenVINO `v2026.1`.

## Troubleshooting

- If Docker cannot pull `intel/model-download:<tag>`, check the `MODEL_DOWNLOAD_IMAGE_TAG` value in `.env` (defaults to `latest`; this is independent of the application image `TAG`).
- If a gated model fails with an authentication error, set `HUGGINGFACEHUB_API_TOKEN` and rerun the command.
- If a download process is interrupted or fails due to network issues, remove the `ovms_model` folder and the model-specific folder from the failed run under `ov_models/`. Then rerun the command. The ephemeral model-download container is automatically cleaned up when the helper exits.
