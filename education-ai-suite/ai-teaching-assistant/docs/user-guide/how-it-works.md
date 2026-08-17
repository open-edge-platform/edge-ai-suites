# How It Works

This page describes the runtime architecture and end-to-end request
flow of the AI Teaching Assistant.

## System Architecture

AI Teaching Assistant runs as Windows-native Python services launched by
`start_ata.ps1`. The browser talks to one local origin
(`ai-teaching-assistant ui` on port 7860), and that UI server proxies
requests to backend services.

All inference stays local: speech-to-text, retrieval, LLM generation, and
text-to-speech are served on the same machine.

```
┌─────────────────────────────────────────────────────────────┐
│                     User's Web Browser                     │
│              (React UI + Web Audio API)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
         ┌───────────────────────────────────┐
         │ ai-teaching-assistant-ui-server   │
         │            (Port 7860)            │
         │   - Serves built React UI         │
         │   - Proxies /api/* to services    │
         └───────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
    ┌──────────┐  ┌──────────────┐  ┌──────────┐
    │  audio   │  │  rag-service │  │   tts    │
    │analyzer  │  │  (Port 8020) │  │ (Port    │
    │(Port     │  │ Retrieval &  │  │  8011)   │
    │8010)     │  │  Generation  │  │ Synthesis│
    └──────────┘  └──────────────┘  └──────────┘
        ↓              ↓                ↓
    Whisper ASR   Embedding + RAG      TTS
    (Speech→Text) + Qwen LLM       (Text→Speech)
```

## Component Roles

### `ai-teaching-assistant ui` (Browser Interface, Port 7860)
- Captures microphone audio using the Web Audio API
- Sends audio chunks to `kiosk-core` through the UI proxy (`/api/kiosk/...`)
- Displays question transcript and streaming answer text
- Plays audio response automatically
- Manages course material upload to knowledge base

### `kiosk-core` (Session Orchestrator, Port 8012)
- Receives audio from the browser
- Forwards audio to `audio-analyzer` for transcription
- Sends transcription + conversation history to `rag-service`
- Receives answer stream and forwards to `text-to-speech`
- Exposes session polling and response-audio endpoints

### `audio-analyzer` (Speech-to-Text, Port 8010)
- Runs OpenAI Whisper model via OpenVINO
- Converts audio waveforms to text
- Returns transcription to `kiosk-core`

### `rag-service` (Knowledge Base + LLM, Port 8020)
The core intelligence. It:
- **Ingests** course materials (`.txt`, `.md`, `.docx`, `.pdf`)
- **Embeds** documents using the `BAAI/bge-large-en-v1.5` embedding model
- **Stores** embeddings in a Chroma vector database
- **Retrieves** relevant context chunks for each question
- **Ranks** candidates with the `BAAI/bge-reranker-base` reranker
- **Generates** answers using the `Qwen/Qwen3-4B-Instruct-2507` LLM (OpenVINO backend)
- **Streams** answer tokens back to `kiosk-core` over SSE

### `text-to-speech` (Voice Synthesis, Port 8011)
- Receives answer text as a stream
- Generates audio WAV clips
- Returns WAV files that are played back in order

### `metrics-collector` (System Metrics, Port 9000)
- Collects CPU, memory, and platform metrics
- Serves metrics consumed by `kiosk-core` and UI panels

## Complete Question-Answer Flow

### 1. User Speaks
User clicks the microphone button and asks a question:
> "What are the key themes in Chapter 3?"

### 2. Session Starts
- React UI calls `POST /api/kiosk/api/v1/sessions/start-stream`
- `kiosk-core` creates a browser stream session and returns `session_id`

### 3. Audio Capture
- Browser captures audio stream (16 kHz mono WAV)
- Browser pushes chunks with `POST /api/kiosk/api/v1/sessions/{session_id}/audio`

### 4. Speech-to-Text
- `kiosk-core` applies silence timeout and max-duration rules
- Sends audio to `audio-analyzer`
- Whisper transcribes:
> "What are the key themes in Chapter 3?"

### 5. Knowledge Base Search
`rag-service` retrieves relevant course material:
- Convert question to embedding (BGE model)
- Search Chroma vector DB for similar document chunks
- Retrieve top-K chunks from uploaded materials
- Optionally rerank with cross-encoder

### 6. Answer Generation
Qwen LLM generates grounded answer:
- Input: Question + retrieved context + conversation history
- Output: Streamed token-by-token response
> "The key themes in Chapter 3 are..."

### 7. Speech Synthesis
As `kiosk-core` receives answer tokens:
- Collects complete sentences
- Sends each to `text-to-speech`
- TTS generates audio for each sentence
- Audio files are queued for playback

### 8. Poll + Playback
- UI polls `GET /api/kiosk/api/v1/sessions/{session_id}`
- UI fetches clip URLs from `GET /api/kiosk/api/v1/sessions/{session_id}/response-audio/{index}`
- Browser then:
- Plays each segment sequentially
- Displays transcript and text simultaneously

### 9. Context Persistence
- Answer and source materials saved in session
- Knowledge base persists for future questions
- Conversation history used for follow-up questions

## Multi-File Knowledge Base Ingestion

When uploading course materials:

1. **File Upload** — User selects multiple files in browser
2. **Multi-Part Form** — Browser sends all files in single request
3. **Parsing** — `rag-service` extracts text:
   - `.txt` / `.md` → Direct UTF-8 decode
   - `.docx` → Extract paragraphs via python-docx
   - `.pdf` → Extract text via pypdf
4. **Chunking** — Semantic chunker splits text into overlapping chunks
5. **Embedding** — Each chunk embedded with BGE model
6. **Storage** — Chunks stored in Chroma with source metadata
7. **Persistence** — Vector store auto-saves to disk

## Performance Characteristics

| Operation | Typical Time | Bottleneck |
|-----------|--------------|-----------|
| Speech-to-text | 1-3s | Whisper inference |
| Knowledge retrieval | 0.5-1s | Embedding + search |
| Answer generation | 2-5s | Qwen LLM speed (token/sec) |
| Speech synthesis | 1-2s | TTS model inference |
| **Total end-to-end** | **5-15s** | LLM generation |

Times vary by: CPU speed, answer length, chunk count, model precision.

## Deployment Model

- Windows-native launcher flow (`setup_windows.ps1`, `start_ata.ps1`)
- No container runtime required
- Submodule-based dependency layout (`edge-ai-libraries`, `voice-enabled-interactions`)

## Shared Infrastructure and Disabled Features

`kiosk-core` and `rag-service` are provided by the `voice-enabled-interactions`
submodule, which also ships retail-oriented capabilities. The AI Teaching
Assistant runs a lean, local-only educational configuration and disables those
features via `.env`:

| Feature | Flag | State |
|---------|------|-------|
| Ordering / commerce agent | `KIOSK_CORE_ORDERING_ENABLED` | Disabled |
| Identity / face recognition | `KIOSK_CORE_IDENTITY_ENABLED` | Disabled |
| Queue service | `KIOSK_CORE_QUEUE_SERVICE_ENABLED` | Disabled |
| Speaker diarization | `KIOSK_CORE_DIARIZATION_ENABLED` | Disabled |

Only the voice Q&A path (ASR → RAG → LLM → TTS) and system metrics are active.

## Configuration

Key tunable parameters are documented in
[Configuration](./get-started/configuration.md):
- `.env` variables used by launcher and proxy
- service-level `config.yaml` for ASR/TTS/RAG
- session parameters (`chunk_seconds`, `silence_timeout_seconds`, `max_session_seconds`)

See [Configuration](./get-started/configuration.md) for details.

