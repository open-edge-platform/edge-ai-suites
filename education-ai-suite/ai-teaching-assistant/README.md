# AI Teaching Assistant

AI Teaching Assistant is a Windows-native, voice-first educational assistant.
It captures speech in the browser, transcribes with Whisper, retrieves grounded
context from uploaded documents, generates answers with a local LLM, and plays
voice responses back in the UI.

The application runs locally on Intel hardware using OpenVINO-backed services.

## What This Project Contains

- A React browser UI in [assistant-react-ui](assistant-react-ui).
- A FastAPI UI server/proxy in [ata_ui_server.py](ata_ui_server.py).
- A FastAPI orchestrator (`kiosk-core`) in [voice-enabled-interactions/smart-kiosk-assistant/main.py](voice-enabled-interactions/smart-kiosk-assistant/main.py).
- A RAG microservice in [voice-enabled-interactions/smart-kiosk-assistant/rag-service](voice-enabled-interactions/smart-kiosk-assistant/rag-service).
- Upstream ASR and TTS services from the `edge-ai-libraries` submodule.
- Windows setup/start/stop scripts in [setup_windows.ps1](setup_windows.ps1), [start_ata.ps1](start_ata.ps1), and [stop_ata.ps1](stop_ata.ps1).

## Runtime Topology

| Service | Port | Role | Entry Point |
|---|---|---|---|
| `ai-teaching-assistant ui` | `7860` | Serves React app and proxies API calls | [ata_ui_server.py](ata_ui_server.py) |
| `kiosk-core` | `8012` | Session orchestration (audio flow, polling state, response audio) | [voice-enabled-interactions/smart-kiosk-assistant/main.py](voice-enabled-interactions/smart-kiosk-assistant/main.py) |
| `audio-analyzer` | `8010` | Speech-to-text (Whisper) | [edge-ai-libraries/microservices/audio-analyzer/main.py](edge-ai-libraries/microservices/audio-analyzer/main.py) |
| `text-to-speech` | `8011` | Speech synthesis | [edge-ai-libraries/microservices/text-to-speech/main.py](edge-ai-libraries/microservices/text-to-speech/main.py) |
| `rag-service` | `8020` | Document ingestion, retrieval, and answer generation | [voice-enabled-interactions/smart-kiosk-assistant/rag-service/main.py](voice-enabled-interactions/smart-kiosk-assistant/rag-service/main.py) |
| `metrics-collector` | `9000` | Platform and runtime metrics | [metrics_collector/windows/metrics_collector.ps1](metrics_collector/windows/metrics_collector.ps1) |

## Quick Start

See [docs/user-guide/get-started.md](docs/user-guide/get-started.md) for the complete flow.

At a high level:

```powershell
git clone --filter=blob:none --sparse https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set education-ai-suite/ai-teaching-assistant
cd education-ai-suite/ai-teaching-assistant
.\setup_windows.ps1
.\start_ata.ps1
```

Open `http://127.0.0.1:7860`.

## Wake-Word Voice Activation (Jarvis)

You can run host-microphone wake-word activation with openwakeword:

```powershell
cd education-ai-suite/ai-teaching-assistant
python mic_session.py --wakeword --wakeword-model "hey jarvis"
```

This arms detection and opens a normal voice session after the wake word is detected.

## Documentation Map

- Overview: [docs/user-guide/index.md](docs/user-guide/index.md)
- Setup: [docs/user-guide/get-started.md](docs/user-guide/get-started.md)
- Architecture: [docs/user-guide/how-it-works.md](docs/user-guide/how-it-works.md)
- API: [docs/user-guide/api-reference.md](docs/user-guide/api-reference.md)
- Configuration: [docs/user-guide/get-started/configuration.md](docs/user-guide/get-started/configuration.md)
- Standalone/manual service run: [docs/user-guide/get-started/run-standalone.md](docs/user-guide/get-started/run-standalone.md)
- Troubleshooting: [docs/user-guide/troubleshooting.md](docs/user-guide/troubleshooting.md)
- Release notes: [docs/user-guide/release-notes.md](docs/user-guide/release-notes.md)
