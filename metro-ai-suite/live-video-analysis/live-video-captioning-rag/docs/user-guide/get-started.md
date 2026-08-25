# Get Started

The Live Video Captioning RAG sample application is a retrieval-augmented generation workflow that creates caption-text embeddings and stores them in a vector database together with the corresponding video frames and metadata, using an LLM that is optimized and deployed using OpenVINO™ toolkit, for response generation. The application works with the [Live Video Captioning](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/live-video-captioning/index.html) sample application that processes a Real-Time Streaming Protocol (RTSP) video stream, runs video analytics pipelines, and uses a Vision-Language Model (VLM) to generate live captions for video frames. The Live Video Captioning sample application then sends the frame data, caption text, and associated metadata to the Live Video Captioning RAG sample application so the latter can build an embedding context and store it in the vector database. The Live Video Captioning RAG sample application then provides chatbots that answer questions based on the caption text generated from the video frames.

By following this guide, you will learn how to:

- **Set up the sample application**: Use Docker Compose tool to deploy the application in your system environment.
- **Run the sample application**: Launch the application and use the chatbots to answer questions.
- **Customize application parameters**: Customize settings, for example, the LLM models and deployment configurations, to adapt the application to your specific requirements and environment.

## Prerequisites

- Verify that your system meets the minimum requirements. See [System Requirements](./get-started/system-requirements.md) for details.
- Install Docker platform: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose tool: [Installation Guide](https://docs.docker.com/compose/install/).
- OpenVINO toolkit-compatible VLM/LLM. Follow the guide in [section](#3-download-models-one-time) below.

## Run the Application

### 1. Clone the suite

Go to the target directory of your choice and clone the suite.
If you want to clone a specific release branch, replace `main` with the desired tag.
To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/2026.2/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

```bash
git clone --filter=blob:none --sparse --branch release-2026.2.0 https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set metro-ai-suite
cd metro-ai-suite/live-video-analysis/live-video-captioning-rag
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

This script sets the following important values:
| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST_IP` | Auto-detected from host network (fallback `127.0.0.1`) | Host IP used by browser-accessible services and dashboard URLs. |
| `REGISTRY` | `intel/` | Image registry prefix. |
| `TAG` | `2026.2.0-rc2` | Docker image tag. |
| `LVC_DASHBOARD_PORT` | `4173` | Port for the LVC web dashboard. |
| `LVC_RAG_DASHBOARD_PORT` | `4172` | Port for the LVC-RAG web dashboard. |
| `EVAM_HOST_PORT` | `8040` | Port for the pipeline management REST API. |
| `WHIP_SERVER_PORT` | `8889` | Port for WebRTC/WHIP signaling (mediamtx). |
| `MQTT_PORT` | `1883` | Port for the internal MQTT broker. |
| `WEBRTC_BITRATE` | `2048` | WebRTC stream bitrate in kbps. Lower values reduce bandwidth. |
| `ENABLE_DETECTION_PIPELINE` | `false` | Enables optional object-detection pre-filtering when set to `true`. |
| `ALERT_MODE` | `false` | Enables alert-style visual highlighting based on keyword rules when set to `true`. |
| `CAPTION_HISTORY` | `3` | Number of previous captions shown in the UI. |
| `DEFAULT_RTSP_URL` | *(empty)* | Pre-fills the RTSP URL field in the dashboard on load. |
| `HUGGINGFACEHUB_API_TOKEN` | *(empty)* | Required for downloading gated Hugging Face models. |
| `MODEL_CACHE_PATH` | `<repo>/llm_models` | Host path used for cached/downloaded model artifacts. |
| `EMBEDDING_MODEL_NAME` | `QwenText/qwen3-embedding-0.6b` | Embedding model identifier used by embedding service configuration. |
| `EMBEDDING_DEVICE` | `CPU` | Target device for embedding inference runtime (for example `CPU`, `GPU`, or `NPU`). |
| `LLM_MODEL_ID` | `Qwen/Qwen2.5-3B-Instruct` | LLM model identifier used for RAG response generation. |
| `LLM_DEVICE` | `CPU` | Target device for LLM inference runtime (for example `CPU`, `GPU`, or `NPU`). |
| `MAX_TOKENS` | `1024` | Maximum number of generated output tokens per response. |
| `TOP_K` | `1` | Number of top retrieved context entries used during RAG answering. |
| `SCORE_THRESHOLD` | `0.3` | Minimum retrieval similarity score required to include context. |
| `VDMS_HOST` | `vdms-vector-db` | Hostname of the VDMS vector database service used by the app. |
| `VDMS_VDB_HOST` | `vdms-vector-db` | Vector DB hostname used by compatibility paths in the backend stack. |

### 3. Download models (one-time)

Download a VLM model that required to generate captions for LVC. For default `CPU` example:

```bash
./model_download_scripts/download_models.sh \
  --model OpenGVLab/InternVL2-1B \
  --type vlm \
  --weight-format int8
```

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
  --device <CPU|GPU|NPU>
```
> Note: NPU currently requires `int4` quantization for VLM/LLM conversion. If you pass `--device NPU` with `int8` or `fp16`, the script automatically overrides it to `int4`.

The VLM models stored under `ov_models`.

See [Model Preparation](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/live-video-captioning/get-started/model-preparation.html) for detailed usage.

Download a LLM model for RAG.

```bash
# Set --model to the Hugging Face model you want to convert.
# Set --device to the preferred conversion target (for example, CPU or GPU).
# Set --weight-format to the precision/quantization format (`int4`, `int8`, or `fp16`).
./model_download_scripts/download_models.sh \
  --model Qwen/Qwen2.5-3B-Instruct \
  --type llm \
  --device CPU \
  --weight-format int8
```
> Note: LLM model support for NPU is not yet enabled in Live-Video-Captioning-RAG application.

This stores the model under `llm_models/`.

For gated Hugging Face models, set a token first:

```bash
export HUGGINGFACEHUB_API_TOKEN=<your-huggingface-token>
```

### 4. Start the application

From the `live-video-analysis/live-video-captioning-rag` directory, start the sample application using the Docker Compose tool:

```bash
docker compose up -d
```

> **Note:** Docker Compose automatically reads values from `.env` in the project root.

> **Note:** The application will take some time to start. Check the container status and ensure that they are in the `"healthy/running"` state using the `docker ps` command before accessing the application.

### 5. Access the application

Follow these steps to use the application:

1. Open the Live Video Captioning UI at `http://<HOST_IP>:4173`.
2. Start a captioning run with a valid RTSP stream.
3. Confirm that captions are being generated.
4. Click the `chat icon` in the top bar (visible only when embedding is enabled).
5. This opens the Live Caption RAG dashboard at `http://<HOST_IP>:4172`.
6. Ask questions related to the current or recent scene.

### 6. Stop the application

```bash
docker compose down
```


## Troubleshooting

###  Live Caption RAG dashboard Does not Open or is Unreachable

- Confirm that `live-video-captioning-rag` container is running.
- Confirm that port mapping `${LIVE_VIDEO_RAG_HOST_PORT:-4172}:4172` is available.
- Check `http://localhost:4172/api/health`.

### Caption pipeline with RTSP not Running in LVC Dashboard

- If your network uses a proxy, add your RTSP stream host or IP to `no_proxy` so the stream connection does not go through the proxy.
- For more detail on LVC, please refer to the [LVC Documentation](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/live-video-captioning/get-started.html)

### Embeddings are Not Being Stored

- Ensure that the caption pipeline is actively running (not running means no ingestion).
- Verify the embedding service health on `http://localhost:9777/health`.
- Verify that the VDMS container is running.
- If containers are running but no embeddings are stored, remove the volume and restart the services:

   ```bash
   docker volume rm live-video-caption_vdms-db
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

./get-started/system-requirements.md
./get-started/build-from-source.md
./get-started/deploy-with-helm.md
./get-started/run-unit-tests.md

:::
hide_directive-->
