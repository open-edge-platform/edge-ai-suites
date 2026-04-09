# Configure Embedding Creation with RAG

This guide explains how to enable caption embedding creation in Live Video Captioning and connect it with the [Live-Video-Captioning-RAG](../../../live-video-captioning-rag/) service for Retrieval-Augmented Generation (RAG) chat.

When enabled:

- Caption pipeline metadata includes frame blobs.
- Live Video Captioning sends `caption_text` + `image_data` + metadata to the RAG embedding API.
- Embeddings are created and stored in VDMS.
- You can open the Live Caption RAG dashboard and query generated context.

## How Data Flows

1. Live Video Captioning receives metadata from MQTT which published by DLSPS.
2. With `ENABLE_EMBEDDING=true`, frame blobs are forwarded to `live-video-captioning-rag` at `/api/embeddings`.
3. RAG service generates embeddings through `multimodal-embedding-serving`.
4. Embeddings + metadata are stored in `vdms-vector-db`.
5. RAG chat (`/api/chat`) retrieves relevant context and generates answers with the configured LLM.

## Prerequisites

- Docker and Docker Compose are installed.
- Complete the base setup in [Get Started](./get-started.md).
- VLM models are prepared for the captioning pipeline (`ov_models/`) and LLM models are prepared for the RAG pipeline (`llm_models/`). Please refer to [Model Preparation section](./model-preparation.md) to download and convert the models.
- Ensure this is a fresh installation. If you previously deployed only live-video-captioning or only live-video-captioning-rag, stop those deployments and follow this guide to deploy both together.

## Enabling Embedding Creation with RAG

1. From the `live-video-captioning` directory, use the provided helper script to setup the environment variables:

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

     Notes:
     - Update the helper script values to use your preferred embedding and LLM models.
     - For gated models, please export your HF_TOKEN before running the `setup_embeddings.sh` script above:
       ```bash
       export HF_TOKEN=<your-huggingface-token>
       ```

2. Then, now you are ready to deploy the live-video-captioning with embedding creation and RAG.
     ```bash
     docker compose up
     ```

## Verify Services Are Running

Make sure that all the services containers are up and running using `docker ps` command. Make sure the state are in `healthy` state before proceed.

Optionally, you may verify health endpoints:

```bash
curl -f http://<HOST_IP>:4173/api/health
curl -f http://<HOST_IP>:4172/api/health
```

## Run End-to-End with Embedding + RAG

1. Open Live Video Captioning UI at `http://<HOST_IP>:4173`.
2. Start a captioning run with a valid RTSP stream.
3. Confirm captions are being generated.
4. Click the `chat icon` in the top bar (visible only when embedding is enabled).
5. This opens Live Caption RAG dashboard at `http://<HOST_IP>:4172`.
6. Ask questions related to current or recent scene context.

## Stop the Services

```bash
docker compose down
```

## Troubleshooting

### Chat icon not visible in live captioning UI

- Ensure `ENABLE_EMBEDDING=true` and `COMPOSE_PROFILES=EMBEDDING` is exported before startup.

### RAG page does not open or is unreachable

- Confirm `live-video-captioning-rag` container is running.
- Confirm port mapping `${LIVE_VIDEO_RAG_HOST_PORT:-4172}:4172` is available.
- Check `http://localhost:4172/api/health`.

### Embeddings not being stored

- Ensure caption pipeline is actively running (no run means no ingestion).
- Verify embedding service health on `http://localhost:9777/health`.
- Verify VDMS container is running.
- If containers is running still no embeddings stored. Remove the volume and restart the services.
     ```bash
     docker volume rm live-video-caption_vdms-db
     ```

## Next Steps

- [Get Started](./get-started.md) - Base setup and deployment flow
- [API Reference](./api-reference.md) - Live Video Captioning API endpoints
- [System Requirements](./get-started/system-requirements.md) - Hardware and software requirements