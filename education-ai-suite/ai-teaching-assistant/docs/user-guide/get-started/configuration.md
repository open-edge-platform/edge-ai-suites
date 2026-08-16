# Configuration

AI Teaching Assistant uses three configuration layers:

1. Launcher environment variables from `.env`
2. Service YAML config files (`audio-analyzer`, `text-to-speech`, `rag-service`)
3. Per-session runtime parameters from UI requests

This guide documents where to change each type.

## 1) `.env` (Launcher-Level)

File:
- [.env](../../../.env)

Loaded by:
- [start_ata.ps1](../../../start_ata.ps1)

Typical variables:

| Variable | Purpose |
|---|---|
| `KIOSK_CORE_ANALYZER_URL` | `kiosk-core` -> `audio-analyzer` endpoint |
| `KIOSK_CORE_RAG_URL` | `kiosk-core` -> `rag-service` endpoint |
| `KIOSK_CORE_TTS_URL` | `kiosk-core` -> `text-to-speech` endpoint |
| `KIOSK_CORE_METRICS_URL` | `kiosk-core` -> `metrics-collector` endpoint |
| `KIOSK_CORE_SAMPLE_RATE` | Default sample rate |
| `KIOSK_CORE_CHUNK_SECONDS` | Chunk duration |
| `KIOSK_CORE_SILENCE_TIMEOUT_SECONDS` | Silence timeout |
| `KIOSK_CORE_MAX_SESSION_SECONDS` | Max session length |
| `KIOSK_CORE_SILENCE_THRESHOLD` | Speech detection threshold |
| `SMART_KIOSK_RAG__MODELS__LLM__BACKEND` | RAG LLM backend (`openvino`, local-only) |
| `KIOSK_CORE_ORDERING_ENABLED` | Ordering agent (disabled for teaching) |
| `KIOSK_CORE_IDENTITY_ENABLED` | Face/voice identity (disabled for teaching) |
| `KIOSK_CORE_QUEUE_SERVICE_ENABLED` | Queue service (disabled for teaching) |
| `KIOSK_CORE_DIARIZATION_ENABLED` | Speaker diarization (disabled for teaching) |

After `.env` changes, restart services.

## 2) Service YAML Files

### audio-analyzer
Active runtime file:
- [edge-ai-libraries/microservices/audio-analyzer/config.yaml](../../../edge-ai-libraries/microservices/audio-analyzer/config.yaml)

### text-to-speech
Active runtime file:
- [edge-ai-libraries/microservices/text-to-speech/config.yaml](../../../edge-ai-libraries/microservices/text-to-speech/config.yaml)

### rag-service
Active runtime file:
- [voice-enabled-interactions/smart-kiosk-assistant/rag-service/config.yaml](../../../voice-enabled-interactions/smart-kiosk-assistant/rag-service/config.yaml)

Key model fields in `rag-service/config.yaml`:
- `models.llm.hf_id`
- `models.embedding.hf_id`
- `retrieval.reranker.hf_id`
- per-model `device` and `weight_format`

## 3) UI Runtime Parameters

The React UI sends stream session options through
`POST /api/v1/sessions/start-stream`:

- `sample_rate`
- `chunk_seconds`
- `silence_timeout_seconds`
- `max_session_seconds`
- `silence_threshold`

Defaults are defined in:
- [assistant-react-ui/src/config.ts](../../../assistant-react-ui/src/config.ts)

## UI Proxy Configuration

The `ai-teaching-assistant ui` reverse-proxy routes are configured in:
- [ata_ui_server.py](../../../ata_ui_server.py)

Proxy env vars:
- `KIOSK_UI_KIOSK_CORE_URL`
- `KIOSK_UI_RAG_URL`
- `KIOSK_UI_TTS_URL`
- `KIOSK_UI_ANALYZER_URL`

## Recommended Change Workflow

1. Edit one config surface at a time (`.env`, YAML, or UI defaults).
2. Restart only impacted services.
3. Verify health endpoints.
4. Run one upload + voice query validation.

## Validation Commands

```powershell
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:8011/health
curl http://127.0.0.1:8020/health
curl http://127.0.0.1:8012/health
curl http://127.0.0.1:7860/healthz
```
