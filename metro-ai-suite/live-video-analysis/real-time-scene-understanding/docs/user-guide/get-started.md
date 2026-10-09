# Get Started

Real Time Scene Understanding is an AI-powered application for analyzing live RTSP video streams in real time using FFMpeg Python bindings (PyAV) and OpenVINO Vision Language Models (VLMs). By combining prompt-driven scene understanding with temporal reasoning across consecutive video frames, it provides both instant scene insights and context-aware event interpretation. The application enables users to process streaming video, perform natural language-based scene analysis, and monitor system and inference performance through an intuitive web dashboard.

This section shows how to:

- **Set up the sample application**: Download the models and use Docker Compose tool to deploy the application in your environment. Compared to quick start guide, this documentation allows the user to personalize the application.
- **Run the application**: Execute the application to see real-time captioning and event alerting from your video stream. Obtaining the temporal analysis summary from consecutive frames helps in understanding the context and evolution of events over time.
- **Modify application parameters**: Customize settings like inference models and VLM parameters to adapt the application to your specific requirements.

## Prerequisites

- Verify that your system meets the minimum requirements. See [System Requirements](./get-started/system-requirements.md) for details.
- Install Docker platform: [Installation Guide](https://docs.docker.com/engine/install/). Install the Ubuntu platform version.
- In case the sample application is used with RTSP streams, setup of the RTSP stream source (live camera or test feed) or simulated RTSP stream source using local video files should be done separately. Reference instructions are provided [here](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/live-video-captioning/get-started/simulated-rtsp-stream-guide.html).

## Run the Application

### 1. Clone the suite

```bash
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set metro-ai-suite
cd metro-ai-suite/live-video-analysis/real-time-scene-understanding
```

### 2. Create `.env`

Run the setup helper:

```bash
bash scripts/setup_env.sh
```

The helper copies `.env.example` to `.env` and fills host-specific values such as `HOST_IP`, `WEBRTC_SIGNALING_URL`, and `RENDER_GROUP_ID`.

Use `--force` only if you want to overwrite an existing `.env`:

```bash
bash scripts/setup_env.sh --force
```

The setup template sets these important values:

| Variable | Default | Purpose |
|----------|---------|---------|
| `HOST_IP` | Detected automatically | Host address reachable by the browser for WebRTC signaling. |
| `TAG` | `latest` | Docker image tag. |
| `PORT` | `9100` | Host port for the dashboard and REST API. Add this to `.env` to change the published host port; the container port remains `9100`. |
| `DASHBOARD_PORT` | `9100` | Internal backend port. Compose currently fixes this to `9100`; changing the `.env.example` value does not change the published host port. |
| `ALERT_VLM_MODEL` | `Qwen3-VL-2B-Instruct` | Model used for the alert pipeline VLM inference. |
| `ALERT_VLM_DEVICE` | `CPU` | Device used for the alert pipeline VLM inference. |
| `ALERT_VLM_INTERVAL` | `2.0` | Interval (in seconds) between alert pipeline VLM inferences. |
| `ALERT_VLM_MAX_TOKENS` | `128` | Maximum number of tokens for the alert pipeline VLM inference. |
| `DEEP_ANALYZER_MODEL` | `Qwen3-VL-8B-Instruct` | Model used for the deep analyzer. |
| `DEEP_ANALYZER_DEVICE` | `GPU` | Device used for the deep analyzer. |
| `DEEP_ANALYZER_MAX_FRAMES` | `8` | Maximum number of frames for the deep analyzer to process. |
| `DEEP_ANALYZER_MAX_TOKENS` | `256` | Maximum number of tokens for the deep analyzer. |
| `DEEP_ANALYZER_DEDUP_CACHE_SIZE` | `500` | Size of the deduplication cache for the deep analyzer. |
| `FRAME_REGISTRY_MAX_RECORDS_PER_STREAM` | `500` | Maximum number of records per stream in the frame registry. |
| `SEGMENT_MAX_ON_DISK` | `50` | Maximum number of finalized segments retained on disk per stream. |
| `HUGGINGFACEHUB_API_TOKEN` | *(empty)* | Required for downloading gated Hugging Face models. |

### 3. Download Models (one-time)

You are required to download two Vision Language Models (VLMs) for real-time scene understanding:

1. **ALERT_VLM_MODEL** - Used for initial single-frame based scene understanding.
2. **DEEP_ANALYZER_MODEL** - Used for temporal-based understanding on consecutive frames.

### Setting Hugging Face Token

If a model is gated on Hugging Face, set your token first:

```bash
export HUGGINGFACEHUB_API_TOKEN="your-token"
```

### Specifying the conversion device

By default, conversion runs on CPU. To target another device:

```bash
./model_download_scripts/download_models.sh \
	--model <model_name> \
	--type <vlm|llm> \
	--weight-format int8 \
	--device <CPU|GPU|NPU>
```
> **Note:** NPU support currently only works with `int4` quantization when converting VLM models. If `--device NPU` is specified alongside `int8` or `fp16`, the script will automatically switch the quantization to `int4`.
> **Note**: NPU compatibility varies by model. Before selecting a model, confirm NPU support in [OpenVINO Supported Models](https://docs.openvino.ai/2026/documentation/compatibility-and-support/supported-models.html).

### Downloading the Models

Run:

```bash
# Download "ALERT_VLM_MODEL" for single-frame based scene understanding
./model_download_scripts/download_models.sh \
	--model Qwen/Qwen3-VL-2B-Instruct \
	--type vlm \
	--weight-format int4 \
	--device CPU

# Download "DEEP_ANALYZER_MODEL" for temporal-based understanding on consecutive frames

./model_download_scripts/download_models.sh \
	--model Qwen/Qwen3-VL-8B-Instruct \
	--type vlm \
	--weight-format int4 \
	--device GPU
```

> Note: `DEEP_ANALYZER_MODEL` must support video input because deep analysis relies on temporal understanding across consecutive frames. Support is model-specific in OpenVINO GenAI: some VLMs are image-only. Before choosing a model, verify it in the official [Supported Models (VLM)](https://openvinotoolkit.github.io/openvino.genai/docs/supported-models/#vision-language-models-vlms) page and review [Visual Processing Using VLMs](https://openvinotoolkit.github.io/openvino.genai/docs/use-cases/visual-processing/) for image/video input behavior.

The model names and devices in `.env.example` match the downloads above. The converted model directories must be under `ov_models/<device-lowercase>/<model-name>/`.

### 4. Start the Application

Start the application by running:

```bash
docker compose up -d
```

The first run may take a few minutes while images are downloaded and services become healthy.

You can check the status of the services with:

```bash
docker compose ps
```

### 5. Access the Application

Once the services are ready, open the Real Time Scene Understanding dashboard in your web browser at:

```text
http://<YOUR_IP>:9100
```

#### Using the Dashboard

- Enter a video source (RTSP URL).
- Enter the alert prompt and the deep-analysis prompt.
- Click "Start" to begin the pipeline.

### 6. Stop the Application

To stop the application, run:

```bash
docker compose down
```

## Troubleshooting

### Application Dashboard Unreachable

- Ensure that `real-time-scene-understanding` container is running by running `docker compose ps`. If the services are not in the `Up` state, check the logs with `docker compose logs` for any errors.
- Verify that the port `9100` is open and accessible from your browser.
- Check `http://<YOUR_IP>:9100/api/health` to see if the dashboard is responding correctly.

### RTSP Streams not Running

- Ensure that the RTSP stream source is correctly configured in the dashboard.
- Verify that the RTSP video source is accessible from the machine running the application.
Confirm that the network allows RTSP traffic between the RTSP video source and the application server. If your system runs behind a proxy, add the RTSP stream host or IP to `no_proxy` and retry. Example: `export no_proxy=$no_proxy,<rtsp_host_or_ip>`.
- Check the logs of the `real-time-scene-understanding` container using `docker compose logs` for any errors related to stream ingestion.

### Deep Analyzer Video Input Error

- Deep analyzer reports **"Video preprocessing isn't implemented for this model"**.
- The configured `DEEP_ANALYZER_MODEL` does not support video input in OpenVINO GenAI. Switch to a video-capable VLM and confirm compatibility in [Supported Models (VLM)](https://openvinotoolkit.github.io/openvino.genai/docs/supported-models/#vision-language-models-vlms) and [Visual Processing Using VLMs](https://openvinotoolkit.github.io/openvino.genai/docs/use-cases/visual-processing/).

## Advanced Paths

- [Build from Source](./get-started/build-from-source.md)
- [Run Unit Tests](./get-started/run-unit-tests.md)
- [API Reference](./api-reference.md)
- [Known Issues](./known-issues.md)
