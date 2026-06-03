# Get Started

Live Video Captioning processes RTSP streams or USB camera (including webcam) feeds through a DLStreamer pipeline and uses a Vision-Language Model (VLM) to generate real-time captions. It also reports throughput and latency metrics.

This section shows how to:

- **Set up the sample application**: Download the models and use Docker Compose tool to deploy the application in your environment. Compared to quick start guide, this documentation allows the user to personalize the application.
- **Run the application**: Execute the application to see real-time captioning from your video stream.
- **Modify application parameters**: Customize settings like inference models and VLM parameters to adapt the application to your specific requirements.

## Prerequisites

- Verify that your system meets the minimum requirements. See [System Requirements](./get-started/system-requirements.md) for details.
- Install Docker platform: [Installation Guide](https://docs.docker.com/engine/install/). Install the Ubuntu platform version.
- In case the sample application is used with RTSP streams, setup of the RTSP stream source (live camera or test feed) or simulated RTSP stream source using local video files should be done separately. Reference instructions are provided [here](./get-started/simulated-rtsp-stream-guide.md).

## Run the Application

### 1. Clone the suite:

Go to the target directory of your choice and clone the suite.
If you want to clone a specific release branch, replace `main` with the desired tag.
To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

```bash
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set metro-ai-suite
cd metro-ai-suite/live-video-analysis/live-video-captioning
```

### 2. Create `.env`

Run the setup helper:

```bash
bash scripts/setup_env.sh
```

The helper creates `.env` from `.env.example`, detects `HOST_IP`, and stores image settings such as `REGISTRY` and `TAG` in the file.

Use `--force` only if you want to overwrite an existing `.env`:

```bash
bash scripts/setup_env.sh --force
```

This script sets these important values:

| Variable | Default | Purpose |
|----------|---------|--------|
| `HOST_IP` | *(auto-detected)* | Host address reachable by the browser for WebRTC signaling. |
| `REGISTRY` | `intel/` | Image registry prefix. |
| `TAG` | `latest` | Docker image tag. |
| `DASHBOARD_PORT` | `4173` | Port for the web dashboard. |
| `EVAM_HOST_PORT` | `8040` | Port for the pipeline management REST API. |
| `WHIP_SERVER_PORT` | `8889` | Port for WebRTC/WHIP signaling (mediamtx). |
| `MQTT_PORT` | `1883` | Port for the internal MQTT broker. |
| `WEBRTC_BITRATE` | `5000` | WebRTC stream bitrate in kbps. Lower values reduce bandwidth. |
| `ENABLE_DETECTION_PIPELINE` | `false` | Enables optional object-detection pre-filtering when set to `true`. |
| `ALERT_MODE` | `false` | Enables alert-style visual highlighting based on keyword rules when set to `true`. |
| `CAPTION_HISTORY` | `3` | Number of previous captions shown in the UI. |
| `DEFAULT_RTSP_URL` | *(empty)* | Pre-fills the RTSP URL field in the dashboard on load. |
| `HUGGINGFACEHUB_API_TOKEN` | *(empty)* | Required for downloading gated Hugging Face models. |


### 3. Download Models (one-time)

Download the required captioning model:

```bash
./model_download_scripts/download_models.sh \
  --model <vlm-model-of-choice-from-huggingface> \
  --type vlm \
  --weight-format int8
```

#### Weight format options

The `--weight-format` flag controls the quantization of the downloaded model. Choose based on your accuracy-vs-memory trade-off:

| Format | Memory use | Accuracy | When to use |
|--------|-----------|----------|-------------|
| `int4` | Lowest | Lower | Memory-constrained systems |
| `int8` | Medium | Good | Recommended default |
| `fp16` | Highest | Best | Maximum accuracy, more RAM required |

#### Gated Hugging Face models

Some models (for example, Gemma-3) require a Hugging Face access token. Set the token in `.env` or export it before running the download script:

```bash
export HUGGINGFACEHUB_API_TOKEN=<your-token>
```

#### Specifying the conversion device

By default the model is converted on CPU. To explicitly set the device:

```bash
./model_download_scripts/download_models.sh \
  --model <vlm-model-of-choice-from-huggingface> \
  --type vlm \
  --weight-format int8 \
  --device <CPU|GPU>
```

### 4. Customize your deployment

Before starting, edit `.env` to enable the features you need. The table below summarises the common customizations:

#### Change exposed ports

If the default ports conflict with other services on your host, override them in `.env`:

```bash
DASHBOARD_PORT=4200
EVAM_HOST_PORT=8050
WHIP_SERVER_PORT=9000
```

#### Pre-fill the RTSP URL

Set `DEFAULT_RTSP_URL` to have the dashboard automatically populate the stream field on load:

```bash
DEFAULT_RTSP_URL=rtsp://<RTSP_HOST_IP>:<PORT>/<ROUTE>

# For example:
DEFAULT_RTSP_URL=rtsp://192.168.1.10:8554/stream
```

#### Enable Alert Mode

Set `ALERT_MODE=true` to activate alert-style visual highlighting. After starting the application, define keyword rules directly in the **Alert Rules** panel on the dashboard. See [Enable Alert Mode](./how-to-guides/enable-alert-mode.md) for full details.

```bash
ALERT_MODE=true
```

#### Enable Object Detection

Set `ENABLE_DETECTION_PIPELINE=true` to pre-filter frames using a YOLO model before sending them to the VLM.

```bash
ENABLE_DETECTION_PIPELINE=true
```

Ensure you have downloaded a detection model.

```bash
./model_download_scripts/download_models.sh --model yolov8s --type vision
```

This places the model under `ov_detection_models/`.

See [Configure Object Detection Pipeline](./how-to-guides/configure-object-detection-pipeline.md) for full details.

#### Enable RAG / Embedding

To connect Live Video Captioning to the RAG service for caption-based Q&A, run the provided helper script instead of editing `.env` manually:

```bash
source scripts/setup_embeddings.sh
```

This sets `ENABLE_EMBEDDING=true`, activates the `EMBEDDING` Compose profile, and configures the additional services.

Download a LLM model for RAG.

```bash
./model_download_scripts/download_models.sh \
  --model Qwen/Qwen2.5-3B-Instruct \
  --type llm \
  --device CPU \
  --weight-format int8
```

This places the model under `llm_models/`.

See [Configure Embedding Creation with RAG](./how-to-guides/configure-embedding-creation-with-rag.md) for full details.

### 5. Start the application

```bash
docker compose up -d
```

### 6. Use the dashboard

Open:

```text
http://<HOST_IP>:4173
```

Then:

1. Enter an RTSP stream URL or select the available USB/webcam camera.
2. Select a VLM model.
3. Adjust the prompt and maximum token settings if needed.
4. Click **Start**.

If your network uses a proxy, add your RTSP stream host or IP to `no_proxy` so the stream connection does not go through the proxy.

### 7. Stop the application

```bash
docker compose down
```

## Advanced paths

- [Build from Source](./get-started/build-from-source.md)
- [Deploy with Helm](./get-started/deploy-with-helm.md)
- [Run Unit Tests](./get-started/run-unit-tests.md)
- [API Reference](./api-reference.md)
- [Known Issues](./known-issues.md)

<!--hide_directive
:::{toctree}
:hidden:

get-started/system-requirements.md
get-started/model-preparation.md
get-started/build-from-source.md
get-started/deploy-with-helm.md

:::
hide_directive-->
