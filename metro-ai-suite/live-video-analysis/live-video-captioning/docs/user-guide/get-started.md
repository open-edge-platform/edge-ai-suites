# Get Started

The Live Video Captioning sample application demonstrates real-time video captioning using Deep Learning Streamer (DL Streamer) and OpenVINO™ toolkit. The sample application processes the Real-Time Streaming Protocol (RTSP) video stream, applies video analytics pipelines for efficient decoding and inference, and leverages a Vision-Language Model (VLM) to generate live captions for the video content. In addition to captioning, the application provides performance metrics such as throughput and latency, enabling developers to evaluate and optimize end-to-end system performance for real-time scenarios.

This section shows how to:

- **Set up the sample application**: Use Docker Compose tool to deploy the application quickly in your environment.
- **Run the application**: Execute the application to see real-time captioning from your video stream.
- **Modify application parameters**: Customize settings like inference models and VLM parameters to adapt the application to your specific requirements.

## Prerequisites

- Verify that your system meets the minimum requirements. See [System Requirements](./get-started/system-requirements.md) for details.
- Install Docker platform: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose tool: [Installation Guide](https://docs.docker.com/compose/install/).
- RTSP stream source (live camera or test feed) or simulated RTSP stream source using local video files.
- OpenVINO toolkit-compatible VLM in `ov_models/`. See [Model Preparation](./get-started/model-preparation.md) to prepare the model.
- OpenVINO-compatible Object Detection Models in `ov_detection_models/`. This is only required
when object detection in the pipeline is enabled. See [Object Detection Pipeline configuration](./how-to-guides/configure-object-detection-pipeline.md) to enable.

## Run the Application

1. Clone the suite:

   Go to the target directory of your choice and clone the suite.
   If you want to clone a specific release branch, replace `main` with the desired tag.
   To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

   ```bash
   git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
   cd edge-ai-suites
   git sparse-checkout set metro-ai-suite
   cd metro-ai-suite/live-video-analysis/live-video-captioning
   ```

2. Configure the image registry and tag:

   If you prefer to use prebuilt images from Docker Hub, export the variables below.

   ```bash
   export REGISTRY="intel/"
   export TAG="latest"
   ```

   If you prefer to build the sample application from source code instead, skip this step and follow the [Build from Source](./get-started/build-from-source.md) guide.

3. Configure the environment:

   Create an `.env` file in the repository root:

   ```bash
   WHIP_SERVER_IP=mediamtx
   WHIP_SERVER_PORT=8889
   WHIP_SERVER_TIMEOUT=30s
   PROJECT_NAME=live-captioning
   HOST_IP=<HOST_IP>
   EVAM_HOST_PORT=8040
   EVAM_PORT=8080
   DASHBOARD_PORT=4173
   WEBRTC_PEER_ID=stream
   WEBRTC_BITRATE=5000
   ALERT_MODE=False
   ENABLE_DETECTION_PIPELINE=False
   CAPTION_HISTORY=3
   ```

   Notes:
   - `HOST_IP` must be reachable by the browser client for WebRTC signaling.
   - `PIPELINE_SERVER_URL` defaults to `http://dlstreamer-pipeline-server:8080`.
   - `WEBRTC_BITRATE` controls the video bitrate in kbps for WebRTC streaming (default: 2048).
   - `CAPTION_HISTORY` controls how many previous captions are shown in the caption timeline. The UI shows the current and `CAPTION_HISTORY` previous entries (`0` means only current). You can also change this value from the UI.

   Follow the steps outlined in the [Model Preparation](./get-started/model-preparation.md) section.

4. Start the Live Video Captioning application:

   From the `live-video-analysis/live-video-captioning` directory, start the application using Docker Compose:

   ```bash
   docker compose up -d
   ```

5. Access the application:

   To start processing video with live captioning:

   a. Open the dashboard at `http://<HOST_IP>:4173`.
   b. Enter an RTSP URL for your video stream.
   c. Select a VLM model from the dropdown.
   d. Customize the prompt and maximum tokens as needed.
   e. Click **Start** to begin captioning.

   > **Note:** If running in a proxy network, add your RTSP stream URLs or IPs to the `no_proxy` environment variable to allow direct connections to the stream source without going through the proxy.

6. Stop the Live Video Captioning sample application services:

   ```bash
   docker compose down
   ```

## Additional Features Reference

If you want to use the application with additional features, see:

- [Alert Mode](./how-to-guides/enable-alert-mode.md) - Enable alert-style responses for binary detection scenarios
- [Enable Detection Pipeline](./how-to-guides/configure-object-detection-pipeline.md) - Enable object detection for live captioning.
- [Enable Embedding Creation with RAG](./how-to-guides/configure-embedding-creation-with-rag.md) - Enable embedding creation and RAG for live captioning.

## Testing and Coverage

The project uses **pytest** for unit testing. Tests are located in the `tests/` directory
under the `app/` folder.

### Install Test Dependencies

```bash
cd app
uv sync --group test
```

### Run All Tests

```bash
uv run pytest
```

### Run a Specific Test File

```bash
uv run pytest tests/test_routes_runs.py
```

### Run Tests with Coverage Report

```bash
uv run pytest --cov=backend --cov=main --cov-report=term-missing
```

### Generate an HTML Coverage Report

```bash
uv run pytest --cov=backend --cov=main --cov-report=html
```

Open `htmlcov/index.html` in a browser to view the detailed coverage report.

## Learn More

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Model Download Microservice Get Started Guide](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/docs/user-guide/get-started.md)
- [Model Preparation](./get-started/model-preparation.md)
- [Build from Source](./get-started/build-from-source.md)
- [Deploy with Helm](./get-started/deploy-with-helm.md) - Deploy the application on Kubernetes with the bundled Helm chart.
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
