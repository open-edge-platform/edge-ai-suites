# Configure Embedding Creation with RAG

This guide explains how to enable caption embedding creation in Live Video Captioning and connect it with the [Live Video Captioning RAG](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/live-captioning-rag/index.html) service for Retrieval-Augmented Generation (RAG) chat.

When enabled:

- Caption pipeline metadata includes frame blobs.
- Live Video Captioning sends `caption_text` + `image_data` + metadata to the RAG embedding API.
- Embeddings are created and stored in VDMS.
- You can open the Live Caption RAG dashboard and query generated context.

## How Data Flows

1. Live Video Captioning receives metadata from MQTT, which are published by DL Streamer Pipeline Server.
2. With `ENABLE_EMBEDDING=true`, frame blobs are forwarded to `live-video-captioning-rag` at `/api/embeddings`.
3. RAG service generates embeddings through `multimodal-embedding-serving`.
4. Embeddings and metadata are stored in `vdms-vector-db`.
5. RAG chat (`/api/chat`) retrieves relevant context and generates answers with the configured LLM.

## Prerequisites

- Docker Engine software and Docker Compose tool are installed.
- Complete the base setup in [Get Started](../get-started.md).
- VLM models are prepared for the captioning pipeline (`ov_models/`) while LLM models are prepared for the RAG pipeline (`llm_models/`). See [Model Preparation section](../get-started/model-preparation.md) to download and convert the models.
- Ensure that this is a fresh installation. If you have deployed only live-video-captioning or only live-video-captioning-rag previously, stop those deployments and follow the instructions in this section to deploy both together.

## Enabling Embedding Creation with RAG

1. From the `live-video-captioning` directory, use the provided helper script to set up the environment variables:

     ```bash
     cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning
     source scripts/setup_embeddings.sh
     ```

     What this does:
     - Sets `ENABLE_EMBEDDING=true`.
     - Enables the Compose profile with `COMPOSE_PROFILES=EMBEDDING`.
     - Configures embedding service, VDMS, and RAG service environment variables.
     - Brings up these additional services:
     - `multimodal-embedding-serving`
     - `vdms-vector-db`
     - `live-video-captioning-rag`

     > **Notes**:
     - Update the helper script values to use your preferred embedding and LLM models.
     - For gated models, export your HF_TOKEN before running the `setup_embeddings.sh` script above:

       ```bash
       export HF_TOKEN=<your-huggingface-token>
       ```

2. Now you are ready to deploy the live-video-captioning with embedding creation and RAG:

     ```bash
     docker compose up -d
     ```

## Verify Services are Running

Ensure that all the services containers are up and running, using the `docker ps` command. Ensure that the state is `healthy` before proceeding.

Optionally, you may verify health endpoints:

```bash
curl -f http://<HOST_IP>:4173/api/health
curl -f http://<HOST_IP>:4172/api/health
```

## Run End-to-End with Embedding and RAG

1. Open the Live Video Captioning UI at `http://<HOST_IP>:4173`.
2. Start a captioning run with a valid RTSP stream.
3. Confirm that captions are being generated.
4. Click the `chat icon` in the top bar (visible only when embedding is enabled).
5. This opens the Live Caption RAG dashboard at `http://<HOST_IP>:4172`.
6. Ask questions related to the current or recent scene.

## Stop the Services

```bash
docker compose down
```

## Troubleshooting

### Chat Icon is not Visible in Live Captioning UI

- Ensure `ENABLE_EMBEDDING=true` and `COMPOSE_PROFILES=EMBEDDING` are exported before startup.

### RAG Page Does not Open or is Unreachable

- Confirm that `live-video-captioning-rag` container is running.
- Confirm that port mapping `${LIVE_VIDEO_RAG_HOST_PORT:-4172}:4172` is available.
- Check `http://localhost:4172/api/health`.

### Embeddings are Not Being Stored

- Ensure that the caption pipeline is actively running (not running means no ingestion).
- Verify the embedding service health on `http://localhost:9777/health`.
- Verify that the VDMS container is running.
- If containers are running but no embeddings are stored, remove the volume and restart the services:

     ```bash
     docker volume rm live-video-caption_vdms-db
     ```

## Supporting Resources

- [Get Started](../get-started.md) - Base setup and deployment flow
- [API Reference](../api-reference.md) - Live Video Captioning API endpoints
- [System Requirements](../get-started/system-requirements.md) - Hardware and software requirements
