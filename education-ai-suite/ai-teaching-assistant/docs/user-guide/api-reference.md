# API Reference

This document covers the APIs used by the AI Teaching Assistant React UI.

## Base URLs

Direct service ports (default local runtime):
- `kiosk-core`: `http://127.0.0.1:8012`
- `rag-service`: `http://127.0.0.1:8020`
- `text-to-speech`: `http://127.0.0.1:8011`
- `audio-analyzer`: `http://127.0.0.1:8010`

Browser-facing same-origin proxy (recommended for UI):
- `/api/kiosk/*` -> `kiosk-core`
- `/api/rag/*` -> `rag-service`
- `/api/tts/*` -> `text-to-speech`
- `/api/analyzer/*` -> `audio-analyzer`

## Health

### kiosk-core
`GET /health`

Response:
```json
{"status": "ok"}
```

### rag-service
`GET /health`

Response:
```json
{"status": "ok"}
```

## Session APIs (kiosk-core)

### Start Browser Stream Session
`POST /api/v1/sessions/start-stream`

Starts a session and returns immediately with a `session_id`.

Request body (typical):
```json
{
  "sample_rate": 16000,
  "chunk_seconds": 5.0,
  "silence_timeout_seconds": 2.0,
  "max_session_seconds": 60.0,
  "silence_threshold": 80,
  "language": "en",
  "temperature": 0.0,
  "tts_model": "speecht5",
  "tts_language": "English",
  "history": []
}
```

Response: session snapshot object with `status: "running"`.

### Push Audio Chunk
`POST /api/v1/sessions/{session_id}/audio`

Request headers:
- `Content-Type: audio/wav`

Body:
- WAV bytes for one browser chunk

Response:
```json
{"status": "accepted"}
```

### End Audio Stream
`POST /api/v1/sessions/{session_id}/audio/end`

Signals end-of-stream so session finalization and response generation can complete.

Response:
```json
{"status": "eos_accepted"}
```

### Get Session Snapshot
`GET /api/v1/sessions/{session_id}`

Used by UI polling.

Important fields:
- `status`: `created | running | stopping | completed | failed`
- `transcript`: combined transcript
- `response`: streamed answer text
- `tts_audio_segments`: generated audio clip metadata
- `tts_errors`: synthesis errors, if any
- `captured_audio_seconds`
- `end_reason`

### List Sessions
`GET /api/v1/sessions`

Returns all known session snapshots in memory.

### Stop Session
`POST /api/v1/sessions/{session_id}/stop`

Requests early stop of a running session.

### Response Audio Clip
`GET /api/v1/sessions/{session_id}/response-audio/{index}`

Returns WAV audio for playback.

## Device and System APIs (kiosk-core)

### List Input Devices
`GET /api/v1/devices`

Returns host microphone devices (used for host capture workflows and diagnostics).

### Runtime Metrics
`GET /api/v1/metrics`

Proxies metrics-collector response.

### Platform Info
`GET /api/v1/platform-info`

Proxies hardware/platform summary from metrics-collector.

## Knowledge Base APIs (rag-service)

### Ingest Files (Batch)
`POST /api/v1/context/file`

Multipart upload. Supports `.txt`, `.md`, `.docx`, `.pdf`.

Response includes:
- `total_chunks_added`
- `files_processed`
- `files_succeeded`
- `files_failed`
- per-file results

### Clear Context
`DELETE /api/v1/context`

Clears current vector collection documents.

Response:
```json
{"status": "cleared"}
```

If clear fails, returns status `failed` and error details.

### Context Stats
`GET /api/v1/context/stats`

Returns collection-level statistics.

### RAG Performance
`GET /api/v1/performance`

Returns retrieval and LLM latency summaries.

## Service Performance APIs

### TTS Performance
`GET /v1/performance` on `text-to-speech`

### ASR Performance
`GET /v1/performance` on `audio-analyzer`

## Recommended Polling Pattern

1. Start stream session
2. Push chunks continuously
3. Send end-of-stream
4. Poll session every ~400 ms until `completed` or `failed`
5. Play `response-audio` clip URLs in index order

This is the flow implemented by `assistant-react-ui/src/hooks/useVoiceSession.ts`.
