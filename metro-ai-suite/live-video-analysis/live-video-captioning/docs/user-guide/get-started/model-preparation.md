# Model Preparation

Live Video Captioning needs at least one Vision Language Model (VLM) in `ov_models/`. Object detection is optional and uses models in `ov_detection_models/`.

The provided helper uses the ephemeral model-download container flow from the Model Download project. It starts a temporary container, downloads or converts the model, writes the files to this repository, and removes the container when finished. You do not need to clone `edge-ai-libraries` or run a separate model-download service.

## Prerequisites

- Docker is installed and running.
- `curl` and `python3` are available on the host.
- The commands are run from the `live-video-captioning` directory.
- For gated Hugging Face models, set a token first:

  ```bash
  export HUGGINGFACEHUB_API_TOKEN=<your-huggingface-token>
  ```

## Download a VLM model

```bash
./model_download_scripts/download_models.sh \
  --model OpenGVLab/InternVL2-1B \
  --type vlm \
  --weight-format int8
```

The model is prepared under `ov_models/`.

Supported weight formats are `int4`, `int8`, and `fp16`. The default is `int8`.

## Optional: download an object-detection model

Download a YOLO model only if you plan to enable the object-detection pipeline:

```bash
./model_download_scripts/download_models.sh --model yolov8s --type vision
```

The model is prepared under `ov_detection_models/`.

Then enable detection in `.env`:

```bash
ENABLE_DETECTION_PIPELINE=true
```

## Optional: change the conversion device

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

RAG is optional and not required for the base Live Video Captioning application. For LLM and RAG model setup, see [RAG Model Download](../how-to-guides/rag-model-download/README.md).

## Troubleshooting

- If Docker cannot pull `intel/model-download:<TAG>`, check the `TAG` value in `.env`.
- If a gated model fails with an authentication error, set `HUGGINGFACEHUB_API_TOKEN` and rerun the command.
- If a download is interrupted, rerun the same command. The ephemeral container is removed automatically when the helper exits.
