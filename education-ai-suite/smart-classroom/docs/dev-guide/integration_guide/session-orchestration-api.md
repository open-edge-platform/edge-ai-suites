# Smart Classroom Session API — User Integration Guide

This guide is for **customers and partners integrating Smart Classroom**. It shows
how to drive a complete classroom processing run (transcription, summarization,
mind map, video analytics, topic segmentation) through just 3 endpoints, letting
the backend handle everything automatically.

You only need to:
1. Call **1 endpoint** to submit a task.
2. Poll **1 endpoint** to check progress.
3. When done, read the results from the directory the API returns.

The backend handles execution order, stage dependencies, and parallel
audio/video processing — you don't need to understand the internals or chain
features yourself.

---

## Workflow (3 steps)

```
Step 1  Submit a task            →  get session_id
Step 2  Poll for progress        →  until "completed" or "failed"
Step 3  Get the results          →  read files from output_dir
```

---

## Endpoints Overview

| Endpoint | Purpose |
|---|---|
| `POST /sessions/process` | Submit a processing task (auto-creates session, runs async in background) |
| `GET /sessions/{session_id}/status` | Query a task's state and progress |
| `GET /sessions` | (Optional) List all task records |

---

## 1. Submit a Task

**`POST /sessions/process`**

### Request Body

| Field | Required | Description |
|---|---|---|
| `audio_path` | no | Local path to the audio file. **Only needed if you want audio processing.** |
| `video_sources` | no | Local paths to video files (multiple allowed). **Only needed if you want video analytics.** |
| `stages` | **yes** | Which stages to run this session. **At least one is required.** |

`video_sources` supports: `front` (front camera), `back` (back camera), `content`
(board/screen) — provide any subset.

`stages` allowed values:

| Value | Description | Requires LLM |
|---|---|---|
| `transcribe` | Speech-to-text (audio → text) | no |
| `summarize` | Classroom summary | yes |
| `mindmap` | Mind map | yes |
| `va` | Video analytics (pose / classroom behavior) | no |
| `segmentation` | Content / topic segmentation | yes |

Notes:

- `stages` declares **which** stages to run; the execution order is decided by the
  backend. You don't need to sort them.
- Stages not requested are shown as `skipped`.
- To run transcription only: `["transcribe"]` (no LLM calls).
- To run video analytics only: `["va"]` (audio is completely ignored).
- Requesting a stage without its required input (e.g. `transcribe` without
  `audio_path`) returns an error.

### Examples

**Full session:**
```json
{
  "audio_path": "D:\\media\\class1.wav",
  "video_sources": {
    "front": "D:\\media\\front.mp4",
    "back": "D:\\media\\back.mp4"
  },
  "stages": ["transcribe", "summarize", "mindmap", "va", "segmentation"]
}
```

**Transcription only:**
```json
{
  "audio_path": "D:\\media\\class1.wav",
  "stages": ["transcribe"]
}
```

**Video analytics only:**
```json
{
  "video_sources": { "front": "D:\\media\\front.mp4" },
  "stages": ["va"]
}
```

### Response (returns immediately; processing continues in background)

```json
{
  "session_id": "20260807-143518-0085",
  "stages": { "transcribe": "pending", "va": "pending" },
  "output_dir": "C:\\...\\storage\\smart-classroom\\20260807-143518-0085",
  "started_at": "2026-08-07T06:35:18+00:00"
}
```

**Keep the `session_id`** — you'll use it in the next step.

---

## 2. Query Task Status

**`GET /sessions/{session_id}/status`**

Fill in the `session_id` from the previous step.

### Response

```json
{
  "session_id": "20260807-143518-0085",
  "state": "running",
  "current_stage": "va",
  "stages": {
    "transcribe": "done",
    "summarize": "done",
    "mindmap": "done",
    "va": "running",
    "segmentation": "pending"
  },
  "sources": {
    "audio": "class1.wav",
    "video": { "front": "front.mp4", "back": "back.mp4" }
  },
  "output_dir": "C:\\...\\storage\\smart-classroom\\20260807-143518-0085",
  "error": null,
  "started_at": "2026-08-07T06:35:18+00:00",
  "updated_at": "2026-08-07T06:42:39+00:00"
}
```

### Key Fields

| Field | Description |
|---|---|
| `state` | Overall task state: `pending` (queued) / `running` / `completed` / `failed`. **`completed` = task finished, results are ready.** |
| `current_stage` | The stage currently executing. |
| `stages` | Per-stage status: `pending` / `running` / `done` / `skipped` / `failed`. |
| `sources` | Source file names for this session. |
| `output_dir` | **Full path to the results directory**; read files here once done. |
| `error` | Failure reason (only present when `state = failed`). |
| `started_at` / `updated_at` | Start / last-update timestamps; use them to compute elapsed time. |

### How to Tell It Succeeded

Poll this endpoint until:
- `state == "completed"` → success, get the results from `output_dir`.
- `state == "failed"` → failure, check the `error` field.

---

## 3. List All Tasks (Optional)

**`GET /sessions`**

Returns all task records for management / overview:

```json
{
  "total": 2,
  "sessions": [
    {
      "session_id": "20260807-140806-8df1",
      "state": "completed",
      "current_stage": "segmentation",
      "stages": {
        "transcribe": "done",
        "summarize": "done",
        "mindmap": "done",
        "va": "done",
        "segmentation": "done"
      },
      "sources": {
        "audio": "input_part_5min.wav",
        "video": {
          "front": "qian5.mp4",
          "back": "hou5.mp4"
        }
      },
      "started_at": "2026-08-07T06:08:06+00:00",
      "updated_at": "2026-08-07T06:16:40+00:00"
    }
  ]
}
```

---

## Where the Results Are

When processing completes, read files under `output_dir`. The directory is
organized into three areas:

| Directory | Contents | Examples |
|---|---|---|
| `result/` | Final LLM outputs | `summary.md`, `mindmap.mmd`, `topics.json` |
| `raw/` | Intermediate data and originals | `transcription.txt`, recorded videos, video analytics stats |
| `logs/` | Monitoring / run logs | performance metrics, run logs |

Read the file you need by name.

---

## Notes

- **Files must be local**: `audio_path` / `video_sources` are **local paths on the
  machine running Smart Classroom**. These endpoints do not support RTSP streams.
- **Polling**: there is no callback. Poll `status` every few seconds (5–10s is
  recommended) until it finishes.
- **Fail-fast**: if any stage fails, the whole task is marked `failed` and stops;
  `error` carries the reason.
- **One task at a time**: the current version processes one session at a time;
  concurrent multi-session is not supported.

---

## Full Example

```bash
# 1. Submit a task
curl -X POST http://<host>:8000/sessions/process \
  -H "Content-Type: application/json" \
  -d '{
    "audio_path": "D:\\media\\class1.wav",
    "video_sources": { "front": "D:\\media\\front.mp4" },
    "stages": ["transcribe", "va"]
  }'

# 2. Check progress (fill in the session_id)
curl http://<host>:8000/sessions/20260807-143518-0085/status

# 3. List all tasks
curl http://<host>:8000/sessions
```

---

## Appendix: LLM / VLM Service (Standalone Endpoint)

Smart Classroom also exposes a **directly callable LLM/VLM endpoint**. Clients can
use it as a standalone model service, without going through the full classroom
processing flow.

### Endpoint

```
POST http://<host>:8000/v1/chat/completions
```

**OpenAI-compatible** — use a standard OpenAI client.

- Text-only requests (use as an **LLM**)
- Text + image requests (use as a **VLM**, include image path/URL in the message)
- Streaming and non-streaming supported

### Supported Models

The server currently supports the following models (OpenVINO quantized):

| Model | Supported Quantization |
|---|---|
| `Qwen/Qwen3-VL-8B-Instruct` | int4, int8 |
| `Qwen/Qwen3.5-9B` | int4, int8 |
| `Qwen/Qwen3.6-35B-A3B` | int4 (no int8) |

Notes:

- **Current default** is `Qwen/Qwen3-VL-8B-Instruct` (config `vlm_name`), multimodal.
- `Qwen/Qwen3.5-9B` and `Qwen/Qwen3.6-35B-A3B` are validated only on
  `device: GPU` + `weight_format: int8`.
- **To switch models**, edit `config.yaml` (`text_gen.vlm_name`, plus
  `weight_format` / `device`) and restart the service.
- The `model` parameter in the request is **ignored** — the server-side configured
  model is always used. Passing a different `model` name does not switch models.
- Actual model availability and quantization depend on the deployment; contact the
  service provider to add models.

### OpenAI Client Usage (recommended)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",   # point at the VLM endpoint
    api_key="unused",                        # no auth on this service
)

# Text-only (as LLM)
resp = client.chat.completions.create(
    model="Qwen/Qwen3-VL-8B-Instruct",       # optional; server config used if omitted
    messages=[
        {"role": "system", "content": "You are a classroom assistant. Be concise."},
        {"role": "user", "content": "Summarize this classroom transcript."},
    ],
    temperature=0.3,
)
print(resp.choices[0].message.content)

# Text + image (as VLM; image_url can be a local path or URL)
resp = client.chat.completions.create(
    model="Qwen/Qwen3-VL-8B-Instruct",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What is written on this board?"},
            {"type": "image_url", "image_url": {"url": "C:/path/to/board.jpg"}},
        ],
    }],
)
```

### curl Usage

```bash
# Text-only
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello, introduce yourself"}]}'

# Text + image
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages":[{
      "role":"user",
      "content":[
        {"type":"text","text":"What is in this image?"},
        {"type":"image_url","image_url":{"url":"C:\\path\\to\\board.jpg"}}
      ]
    }]
  }'
```

### Capabilities

| Feature | Description |
|---|---|
| Text / text+image | Text-only is treated as LLM; with images, as VLM |
| Streaming | Add `"stream": true`; response is an SSE stream (`data: {...}` until `data: [DONE]`) |
| `model` | Optional; ignored — server config decides |
| `temperature` / `max_completion_tokens` / `enable_thinking` | Configurable |

### Notes

- **No authentication**: this endpoint has no access control; suitable for
  local/Intranet use only. Add your own protection before exposing it publicly.
- **Single-turn**: only the last user message is used as input. For multi-turn
  conversations, the client must assemble history into the last user message.
- **Model must be loaded**: ensure the service is running and the model is loaded
  (`text_gen` enabled) before calling.
