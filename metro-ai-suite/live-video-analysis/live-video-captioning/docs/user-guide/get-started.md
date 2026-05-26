# Get Started

Live Video Captioning processes RTSP streams or USB camera feeds through a DL Streamer pipeline and uses a Vision-Language Model (VLM) to generate real-time captions. It also reports throughput and latency metrics.

This section shows how to:

- **Set up the sample application**: Download the models and use Docker Compose tool to deploy the application quickly in your environment.
- **Run the application**: Execute the application to see real-time captioning from your video stream.
- **Modify application parameters**: Customize settings like inference models and VLM parameters to adapt the application to your specific requirements.

## Prerequisites

- Verify that your system meets the minimum requirements. See [System Requirements](./get-started/system-requirements.md) for details.
- Install Docker platform: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose tool: [Installation Guide](https://docs.docker.com/compose/install/).
- RTSP stream source (live camera or test feed) or simulated RTSP stream source using local video files.

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

| Variable | Purpose |
|----------|---------|
| `HOST_IP` | Host address reachable by the browser for WebRTC signaling. |
| `REGISTRY` | Image registry prefix, for example `intel/`. |
| `TAG` | Image tag, for example `latest`. |
| `DASHBOARD_PORT` | Dashboard port, default `4173`. |
| `ENABLE_DETECTION_PIPELINE` | Enables optional object detection when set to `true`. |
| `CAPTION_HISTORY` | Number of previous captions shown in the UI. |


### 3. Download Models (one-time)

Download the required captioning model:

```bash
./model_download_scripts/download_models.sh \
  --model OpenGVLab/InternVL2-1B \
  --type vlm \
  --weight-format int8
```

For more model options, see [Model Preparation](./get-started/model-preparation.md).

### 4. Start the application

```bash
docker compose up -d
```

### 5. Use the dashboard

Open:

```text
http://<HOST_IP>:4173
```

Then:

1. Enter an RTSP stream URL/USB camera.
2. Select a VLM model.
3. Adjust the prompt and maximum token settings if needed.
4. Click **Start**.

If your network uses a proxy, add your RTSP stream host or IP to `no_proxy` so the stream connection does not go through the proxy.

### 6. Stop the application

```bash
docker compose down
```

## Optional features

- [Enable Alert Mode](./how-to-guides/enable-alert-mode.md)
- [Configure Object Detection Pipeline](./how-to-guides/configure-object-detection-pipeline.md)
- [Configure Embedding Creation with RAG](./how-to-guides/configure-embedding-creation-with-rag.md)

## Advanced paths

- [Build from Source](./get-started/build-from-source.md)
- [Deploy with Helm](./get-started/deploy-with-helm.md)
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
