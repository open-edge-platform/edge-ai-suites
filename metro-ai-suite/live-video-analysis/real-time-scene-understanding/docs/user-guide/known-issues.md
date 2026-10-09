# Known Issues and Troubleshooting

## NPU high-resolution inference may require token-length tuning

When using an NPU, inference on high-resolution frames may fail to initialize or fail during runtime if the configured prompt-token limit is too small for the image and prompt. The NPU pipeline uses static input shapes, so higher-resolution input can require a larger prompt-token limit.

Increase the applicable `*_NPU_MAX_PROMPT_LEN` setting in `.env` to allow more input tokens:

- Alert VLM: `NPU_MAX_PROMPT_LEN` (default `1024`)
- Deep analyzer: `DEEP_ANALYZER_NPU_MAX_PROMPT_LEN` (default `4096`)

The corresponding minimum response settings are `NPU_MIN_RESPONSE_LEN` and `DEEP_ANALYZER_NPU_MIN_RESPONSE_LEN` (both default `512`). Increasing the prompt limit can increase memory use and inference latency, including time to first token. A larger minimum response length can also increase generation time. Tune these values incrementally and validate performance at the target resolution.

## Model not found at startup

The model settings in `.env` must match both the downloaded model directory and its device folder, for example `ov_models/cpu/Qwen3-VL-2B-Instruct`. Check `ALERT_VLM_MODEL`, `ALERT_VLM_DEVICE`, `DEEP_ANALYZER_MODEL`, and `DEEP_ANALYZER_DEVICE`, then confirm the corresponding directories exist. See [Model Preparation](./get-started/model-preparation.md).

## Deep analyzer rejects video input

If the logs report **"Video preprocessing isn't implemented for this model"**, the configured deep-analyzer model does not support video input in OpenVINO GenAI. Choose a video-capable model and verify its compatibility in [Supported Models (VLM)](https://openvinotoolkit.github.io/openvino.genai/docs/supported-models/#vision-language-models-vlms).

## Dashboard is unreachable

Run `docker compose ps` and `docker compose logs real-time-scene-understanding`. Confirm the configured `PORT` is reachable from the browser and check `http://<YOUR_IP>:<PORT>/api/health`. By default, `PORT` is `9100`.

## RTSP stream does not start

Confirm the RTSP URL is reachable from the host and the application container. If a proxy is configured, add the camera host or IP to `no_proxy`, then retry. Check container logs with `docker compose logs real-time-scene-understanding`.

## Model download authentication or network failure

For gated Hugging Face models, export `HUGGINGFACEHUB_API_TOKEN` and rerun the download. If a download was interrupted, remove the partial model directory under `ov_models/` and rerun it. See [Model Preparation](./get-started/model-preparation.md).

For complete deployment steps, see [Quick Start](./quick-start-guide.md) or [Get Started](./get-started.md).
