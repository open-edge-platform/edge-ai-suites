# Smart Kiosk Assistant

Smart Kiosk Assistant is a voice-first retrieval-augmented kiosk stack for retail, QSR, and other customer-facing deployments. A browser session captures microphone audio, streams it through speech-to-text, retrieves grounded answers from a local knowledge base, and plays a generated spoken response back to the user. The full stack is designed to run locally on Intel CPU/GPU with OpenVINO-backed services.

## What This Repository Contains

- A browser-based Gradio kiosk UI with microphone capture and sequential audio playback.
- A FastAPI kiosk orchestrator that coordinates speech-to-text, retrieval, and text-to-speech.
- An internal RAG microservice with ingestion, vector storage, and streamed answers.
- Pinned runtime configuration for upstream `audio-analyzer` and `text-to-speech` microservices.
- Sample knowledge-base content in [knowledge-base-samples/](knowledge-base-samples/).

## Architecture

![Smart Kiosk Assistant architecture](./docs/user-guide/_assets/architecture.png "smart kiosk assistant architecture")

### Request Flow

1. The browser UI captures microphone audio and sends it to `kiosk-core`.
2. `kiosk-core` forwards audio to `audio-analyzer` for transcription.
3. `kiosk-core` sends the transcription, plus any runtime context, to `rag-service`.
4. `rag-service` retrieves relevant chunks from Chroma, prompts the OpenVINO LLM, and streams the answer back.
5. `kiosk-core` forwards the answer text to `text-to-speech`, stores the generated audio, and returns both text and audio metadata to the UI.

## Service Topology

All five services are started by the top-level [docker-compose.yml](./docker-compose.yml).

| Service | Port | Role | Source |
|---|---|---|---|
| `audio-analyzer` | `8010` | Speech-to-text | [intel/audio-analyzer](https://hub.docker.com/r/intel/audio-analyzer) |
| `text-to-speech` | `8011` | Speech synthesis | [intel/text-to-speech](https://hub.docker.com/r/intel/text-to-speech) |
| `rag-service` | `8020` | Retrieval, ingestion, answer generation | [rag-service/README.md](./rag-service/README.md) |
| `kiosk-core` | `8012` | Session API and service orchestration | [main.py](./main.py) |
| `kiosk-ui` | `7860` | Gradio browser interface | [gradio_app.py](./gradio_app.py) |

## Quick Start

Clone the repository and pull the prebuilt images from Docker Hub:

```bash
git clone https://github.com/intel-retail/voice-enabled-interactions.git
cd voice-enabled-interactions/smart-kiosk-assistant
docker compose pull
docker compose up -d
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860) for the browser UI.

All five images (`audio-analyzer`, `text-to-speech`, `rag-service`,
`kiosk-core`, `kiosk-ui`) are pulled from the `intel/` namespace at the
tag pinned in [.env](./.env). Model files and caches are stored in Docker
named volumes, so no host directory layout needs to be prepared in
advance.

To rebuild any service from source instead of pulling, see
[Build from Source](./docs/user-guide/get-started/build-from-source.md).

## Documentation Map

- Start here: [Overview](./docs/user-guide/index.md) and [Get Started](./docs/user-guide/get-started.md)
- Architecture and request flow: [How It Works](./docs/user-guide/how-it-works.md)
- Hardware and OS prerequisites: [System Requirements](./docs/user-guide/get-started/system-requirements.md)
- Build details: [Build from Source](./docs/user-guide/get-started/build-from-source.md)
- Container startup and verification: [Run Container](./docs/user-guide/get-started/run-container.md)
- Host-run kiosk-core and Gradio UI: [Run Standalone](./docs/user-guide/get-started/run-standalone.md)
- `kiosk-core` API: [API Reference](./docs/user-guide/api-reference.md)
- Environment variables, model selection, and inference device: [Configuration](./docs/user-guide/get-started/configuration.md)
- Troubleshooting: [Troubleshooting](./docs/user-guide/troubleshooting.md)
- Release notes: [Release Notes](./docs/user-guide/release-notes.md)
- RAG service: [rag-service/README.md](rag-service/README.md)
- Pinned configs for upstream services: [configs/README.md](configs/README.md)

## Operational Notes

- Browser audio capture means no host microphone device needs to be passed into the containers.
- The compose stack mounts pinned `config.yaml` files for `audio-analyzer` and `text-to-speech` without modifying their upstream sources.
- `rag-service` persists model caches and vector storage in Docker volumes, so knowledge-base state survives container restarts.
- The browser UI supports knowledge-base ingestion with raw text or `.txt` and `.md` uploads routed through the internal RAG service.
