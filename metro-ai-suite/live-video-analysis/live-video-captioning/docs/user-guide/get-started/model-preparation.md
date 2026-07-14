# Model Preparation

Live Video Captioning needs at least one Vision Language Model (VLM) in `ov_models/`. Object detection is optional and uses models in `ov_detection_models/`.

The provided helper uses the ephemeral model-download container flow from the [Model Download project](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/index.html) in Open Edge Platform. It starts a temporary container, downloads or converts the model, writes the files to this repository, and removes the container when finished. No separate model-download setup is required.

## Prerequisites

- Docker is installed and running.
- `curl` and `python3` are available on the host.
- The commands are run from the `live-video-captioning` directory.
- For gated Hugging Face models, set a token first:

  ```bash
  export HUGGINGFACEHUB_API_TOKEN=<your-huggingface-token>

  # Optional: To download the model to a different path (for example, ~/edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag for live-video-captioning-rag standalone deployment), export:
  export MODEL_PATH=~/edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag
  ```

## Usage

Use the helper script with the following arguments:

```bash
./model_download_scripts/download_models.sh \
  --model <huggingface-model-id> \
  --type <vlm|vision|llm> \
  --weight-format <int4|int8|fp16> \
  --device <CPU|GPU>
```

**Parameters:**
- `--model`: Hugging Face model identifier (for example, `OpenGVLab/InternVL2-1B`).
- `--type`: Model category. Use `vlm` for Vision Language Models, `vision` for object-detection models, or `llm` for text-only LLMs.
- `--weight-format`: Precision/quantization format. Supported values are `int4`, `int8`, and `fp16`.
- `--device`: Target conversion device (for example, `CPU` or `GPU`, depending on host support).

**Weight format options:**

Supported weight formats are `int4`, `int8`, and `fp16`. The default is `int8`.

| Format | Memory use | Accuracy | When to use |
|--------|-----------|----------|-------------|
| `int4` | Lowest | Lower | Memory-constrained systems |
| `int8` | Medium | Good | Recommended default |
| `fp16` | Highest | Best | Maximum accuracy, more RAM required |

## Download a VLM model

You can use the following commands to run conversion for the desired target device. The corresponding models are generated under `ov_models/`.

- For CPU:

    ```bash
    ./model_download_scripts/download_models.sh \
      --model OpenGVLab/InternVL2-1B \
      --type vlm \
      --weight-format int8 \
      --device CPU
    ```

- For GPU:

    ```bash
    ./model_download_scripts/download_models.sh \
      --model OpenGVLab/InternVL2-1B \
      --type vlm \
      --weight-format int8 \
      --device GPU
    ```

- For NPU, use `int4` quantization:

    ```bash
    ./model_download_scripts/download_models.sh \
      --model OpenGVLab/InternVL2-1B \
      --type vlm \
      --weight-format int4 \
      --device NPU
    ```

    > Note: NPU currently requires `int4` quantization for VLM/LLM conversion. If you pass `--device NPU` with `int8` or `fp16`, the script automatically overrides it to `int4`.

You can also download and convert for multiple target devices in a single command by passing a comma-separated `--device` list:

```bash
./model_download_scripts/download_models.sh \
  --model OpenGVLab/InternVL2-1B \
  --type vlm \
  --weight-format int8 \
  --device CPU,GPU,NPU
```

Downloaded VLM models are stored under per-device directories in `ov_models/`.

Each VLM output directory is placed under its target device path so the UI can automatically associate models with the selected `VLM Device`:

| `--device` flag | Example Output Directory | VLM Device tag |
|---|---|---|
| `CPU` (or omitted) | `ov_models/cpu/InternVL2-1B` | `CPU` |
| `GPU` | `ov_models/gpu/InternVL2-1B` | `GPU` |
| `NPU` | `ov_models/npu/InternVL2-1B` | `NPU` |

## Optional: Download an Object-Detection Model

Download a YOLO model only if you plan to enable the object-detection pipeline:

```bash
./model_download_scripts/download_models.sh --model yolov8s --type vision
```

The model is prepared under `ov_detection_models/`.

Then enable detection in `.env`:

```bash
ENABLE_DETECTION_PIPELINE=true
```

## Optional: Change the Conversion Device Configuration

For VLM conversion, set the target device:

```bash
./model_download_scripts/download_models.sh \
  --model OpenGVLab/InternVL2-1B \
  --type vlm \
  --weight-format int8 \
  --device CPU
```

Valid device values depend on the model-download container and host hardware. CPU is the safest default.

## RAG and LLM models

RAG is optional and not required for the base Live Video Captioning application. For LLM and RAG model setup, see [RAG Model Download](../how-to-guides/rag-model-download.md).

## Troubleshooting

- If Docker cannot pull `intel/model-download:<tag>`, check the `MODEL_DOWNLOAD_IMAGE_TAG` value in `.env` (defaults to `latest`; this is independent of the application image `TAG`).
- If a gated model fails with an authentication error, set `HUGGINGFACEHUB_API_TOKEN` and rerun the command.
- If a download process is interrupted or fails due to network issues, remove the `ovms_model` folder and the model-specific folder from the failed run (typically named after the model you specified in command depends on the model type: `ov_models/` for VLMs, `ov_detection_models/` for vision models, or `llm_models/` for LLM models). Then rerun the command. The ephemeral model-download container is automatically cleaned up when the helper exits.
