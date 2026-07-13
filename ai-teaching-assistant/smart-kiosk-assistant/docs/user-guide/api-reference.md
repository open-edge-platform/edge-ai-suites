# API Reference

Base URL (default): `http://127.0.0.1:8012`

## Health Check

```
GET /health
```

**Response**

```json
{"status": "ok"}
```

---

## List Input Devices

```
GET /api/v1/devices
```

Returns audio input devices available on the server host. This is only relevant when calling the server-side microphone capture endpoint.

**Response**

```json
{
  "devices": [
    {"index": 0, "name": "default", "channels": 2, "sample_rate": 44100},
    {"index": 1, "name": "HDA Intel PCH: ALC256 Analog", "channels": 2, "sample_rate": 44100}
  ]
}
```

---

## List Sessions

```
GET /api/v1/sessions
```

**Response**

```text
{
  "sessions": [
    {
      "session_id": "3f1e4d2a-...",
      "status": "completed",
      "created_at": "2026-05-08T10:00:00.000Z",
      ...
    }
  ]
}
```

---

## Get Session

```
GET /api/v1/sessions/{session_id}
```

**Response** — session snapshot object (see [Session Snapshot](#session-snapshot)).

---

## Start Microphone Session

```
POST /api/v1/sessions/start
Content-Type: application/json
```

Begins microphone capture on the server. Returns immediately; the session runs in the background.

**Request Body**

| Field | Type | Default | Description |
|---|---|---|---|
| `device` | `int \| string \| null` | system default | PortAudio input device index or name |
| `sample_rate` | `int` | `16000` | Capture sample rate in Hz (`8000`–`48000`) |
| `chunk_seconds` | `float` | `4.0` | Audio chunk length sent to audio-analyzer (`0.5`–`30`) |
| `silence_timeout_seconds` | `float` | `1.5` | Silence after speech that ends the session (`0.2`–`10`) |
| `max_session_seconds` | `float` | `20.0` | Hard cap on session duration (`1`–`300`) |
| `silence_threshold` | `int` | `900` | RMS threshold below which audio is silence (`1`–`32767`) |
| `language` | `string \| null` | `null` | Language code hint for ASR (e.g. `"en"`) |
| `temperature` | `float` | `0.0` | ASR decoding temperature (`0.0`–`1.0`) |
| `analyzer_url` | `string` | env default | audio-analyzer transcription endpoint |
| `rag_url` | `string` | env default | RAG query endpoint |
| `tts_url` | `string` | env default | TTS speech endpoint |
| `tts_model` | `string` | `"qwen-tts"` | Model name for TTS |
| `tts_voice` | `string \| null` | env default | Voice name for TTS |
| `tts_language` | `string \| null` | `"English"` | Language hint for TTS |
| `tts_instructions` | `string \| null` | env default | Style instructions for TTS |

**Example**

```bash
curl --noproxy '*' -X POST http://127.0.0.1:8012/api/v1/sessions/start \
  -H 'Content-Type: application/json' \
  -d '{
        "language": "en",
        "chunk_seconds": 4,
        "silence_timeout_seconds": 1.5,
        "max_session_seconds": 20,
        "silence_threshold": 900
      }'
```

**Response** — initial session snapshot with `"status": "running"`.

---

## Start File Session

```
POST /api/v1/sessions/start-file
Content-Type: multipart/form-data
```

Feeds an uploaded audio file through the same chunking, ASR, RAG, and TTS pipeline as a session started through `/api/v1/sessions/start`. Useful for testing without capture hardware.

**Form Fields**

Accepts the same fields as [Start Microphone Session](#start-microphone-session) plus:

| Field | Type | Default | Description |
|---|---|---|---|
| `file` | binary | required | Audio file to process (WAV recommended) |
| `realtime_factor` | `float` | `1.0` | Playback speed multiplier for simulated real-time pacing (`0.0`–`100.0`). Set to a large value (e.g. `10.0`) to process as fast as possible. |

**Example**

```bash
curl --noproxy '*' -X POST http://127.0.0.1:8012/api/v1/sessions/start-file \
  -F "file=@/path/to/question.wav" \
  -F "sample_rate=16000" \
  -F "chunk_seconds=4" \
  -F "silence_timeout_seconds=1.5" \
  -F "max_session_seconds=20" \
  -F "silence_threshold=900" \
  -F "language=en" \
  -F "temperature=0.0" \
  -F "realtime_factor=10.0"
```

**Response** — initial session snapshot with `"status": "running"`.

---

## Stop Session

```
POST /api/v1/sessions/{session_id}/stop
```

Requests an early stop of a running session.

**Example**

```bash
curl --noproxy '*' -X POST http://127.0.0.1:8012/api/v1/sessions/<session_id>/stop
```

**Response**

```json
{
  "session_id": "3f1e4d2a-...",
  "status": "stopping",
  "stop_requested_at": "2026-05-08T10:00:05.000Z"
}
```

---

## Session Snapshot

The session snapshot returned by **Get Session**, **Start**, and **Start File** has the following structure:

| Field | Type | Description |
|---|---|---|
| `session_id` | `string` | Unique session identifier |
| `source_kind` | `string` | `"microphone"` or `"file"` |
| `status` | `string` | `"created"` / `"running"` / `"stopping"` / `"completed"` / `"failed"` |
| `created_at` | `string` | ISO 8601 timestamp |
| `started_at` | `string \| null` | ISO 8601 timestamp |
| `completed_at` | `string \| null` | ISO 8601 timestamp |
| `stop_requested_at` | `string \| null` | ISO 8601 timestamp |
| `end_reason` | `string \| null` | Why the session ended (`"silence_timeout"`, `"max_duration"`, `"stopped_by_api"`, `"completed"`, `"error"`) |
| `error` | `string \| null` | Error message if status is `"failed"` |
| `speech_started` | `bool` | Whether speech was detected |
| `captured_audio_seconds` | `float` | Total seconds of audio captured |
| `transcript` | `string` | Combined transcript of all processed chunks |
| `partial_transcript` | `string` | Same as `transcript`; updated while running |
| `response` | `string` | Streamed RAG answer text |
| `tts_audio_segments` | `array` | TTS output clips; see below |
| `tts_errors` | `array` | TTS error strings, if any |

### `tts_audio_segments` item

| Field | Type | Description |
|---|---|---|
| `index` | `int` | 1-based sentence index within the session |
| `text` | `string` | Sentence text that was synthesized |
| `audio_file` | `string` | Absolute path to the generated WAV file on the server. Accessible to the Gradio UI when both share the same `generated_audio/` volume mount. |

---

## Polling Pattern

Start a session, then poll until `status` is `"completed"` or `"failed"`:

```bash
# Start
SESSION=$(curl -s --noproxy '*' -X POST http://127.0.0.1:8012/api/v1/sessions/start-file \
  -F "file=@question.wav" -F "realtime_factor=10.0" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# Poll
while true; do
  STATUS=$(curl -s --noproxy '*' http://127.0.0.1:8012/api/v1/sessions/$SESSION | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])")
  echo "Status: $STATUS"
  [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]] && break
  sleep 1
done

# Read result
curl -s --noproxy '*' http://127.0.0.1:8012/api/v1/sessions/$SESSION | python3 -m json.tool
```
