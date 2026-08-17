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

## Chapter 1: Session APIs

### Workflow (3 steps)

```
Step 1  Submit a task            →  get session_id
Step 2  Poll for progress        →  until "completed" or "failed"
Step 3  Get the results          →  read files from output_dir
```

---

### Endpoints Overview

| Endpoint | Purpose |
|---|---|
| `POST /sessions/process` | Submit a processing task (auto-creates session, runs async in background) |
| `GET /sessions/{session_id}/status` | Query a task's state and progress |
| `GET /sessions` | (Optional) List all task records |

---

### 1. Submit a Task

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

### 2. Query Task Status

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

### 3. List All Tasks (Optional)

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
    },
    {
      "session_id": "20260807-142413-93cd",
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
      "started_at": "2026-08-07T06:24:13+00:00",
      "updated_at": "2026-08-07T06:31:44+00:00"
    }
  ]
}
```

---

### Where the Results Are

When processing completes, read files under `output_dir`. The directory is
organized into three areas:

| Directory | Contents | Examples |
|---|---|---|
| `result/` | Final LLM outputs | `summary.md`, `mindmap.mmd`, `topics.json` |
| `raw/` | Intermediate data and originals | `transcription.txt`, recorded videos, video analytics stats |
| `logs/` | Monitoring / run logs | performance metrics, run logs |

Read the file you need by name.

---

### Notes

- **Files must be local**: `audio_path` / `video_sources` are **local paths on the
  machine running Smart Classroom**. These endpoints do not support RTSP streams.
- **Polling**: there is no callback. Poll `status` every few seconds (5–10s is
  recommended) until it finishes.
- **Fail-fast**: if any stage fails, the whole task is marked `failed` and stops;
  `error` carries the reason.
- **One task at a time**: the current version processes one session at a time;
  concurrent multi-session is not supported.

---

### Full Example

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

## Chapter 2: Legacy Audio Endpoints (`/upload-audio` / `/transcribe`)

> ⚠️ **Prefer `/sessions/process`**
>
> These two endpoints were exposed by earlier versions as standalone audio
> interfaces. They still work and remain available — but because they are already
> in the wild, they cannot be removed. **For all new integrations, use the
> session-orchestration flow in the main part of this guide
> (`POST /sessions/process` + `GET /sessions/{session_id}/status`)**. This appendix
> exists only for compatibility with existing callers.
>
> Differences vs. the session interface:
> - `/upload-audio` + `/transcribe` require uploading the file first, then
>   consuming the transcription chunk-by-chunk over a stream, and managing the
>   session / concurrency lock yourself (429).
> - `/sessions/process` takes `audio_path` + `stages` in a single call; the backend
>   runs the full flow (including transcription) and returns an `output_dir` to
>   read results from.

### 1. `POST /upload-audio`

**Purpose**: Upload an audio file for later use by `/transcribe`.

**Request:**

| Type | Parameter | Required | Format | Description |
|------|-----------|----------|--------|-------------|
| Body | `file` | Yes | multipart/form-data | Audio file (field name **must be exactly `file`**) |

**Constraints:**
- Extension must be `.wav` / `.mp3` / `.m4a`
- Max file size 300 MB
- If a previous session is still processing (`audio_pipeline_lock` held), returns **429** `"Session Active, Try Later"`

**Response:**
```json
{
  "filename": "input_part_5min.wav",
  "message": "File uploaded successfully",
  "path": "storage/smart-classroom/audio/input_part_5min.wav"
}
```

> **Note**: `path` is a **relative path**, resolved against the server process's
> working directory. Pass it verbatim as `audio_filename` in the next step.

**Example:**
```bash
curl -X POST http://<host>:8000/upload-audio \
  -F "file=@input_part_5min.wav"
```

---

### 2. `POST /transcribe`

**Purpose**: Transcribe an uploaded audio file with ASR, streaming text and
timestamps back chunk by chunk.

**Request:**

| Type | Parameter | Required | Format | Description |
|------|-----------|----------|--------|-------------|
| Header | `x-session-id` | No | string | Session ID (optional) |
| Body | `audio_filename` | Yes | string | The `path` returned by `/upload-audio` (**full path**, not the bare filename) |
| Body | `source_type` | No | string | `audio_file` (default) or `microphone` |

**Request Body:**
```json
{
  "audio_filename": "storage/smart-classroom/audio/input_part_5min.wav",
  "source_type": "audio_file"
}
```

**Response (streaming, one JSON object per line — one per chunk):**

```json
{
  "chunk_path": "chunks/chunk_0_7f2288.wav",
  "start_time": 0.0,
  "end_time": 15.0,
  "chunk_index": 0,
  "text": "好，\n小朋友们，\n上课前呢田老师想先跟小朋友们讲解一下我们今天这节课的课堂评价。\n",
  "segments": [
    { "speaker": "教师", "text": "好，", "start": 7.54, "end": 7.78 }
  ]
}
```

Final event:
```json
{
  "event": "final",
  "teacher_speaker": "教师",
  "speaker_text_stats": { "教师": 5234 }
}
```

**Notes:**
- The response header carries `x-session-id`, usable for later lookups.
- After a transcription finishes, wait for the lock to be released before starting
  the next one (otherwise **429**).
- `audio_filename` also works with forward slashes
  (`storage/smart-classroom/audio/...`); no need to escape backslashes on Windows.

**Example:**
```bash
curl -X POST http://<host>:8000/transcribe \
  -H "Content-Type: application/json" \
  -d '{"audio_filename": "storage/smart-classroom/audio/input_part_5min.wav", "source_type": "audio_file"}'
```

---

## Chapter 3: VLM / LLM Service (Standalone Endpoint)

External customers integrating Smart Classroom can also call the endpoint below
**directly** to use the VLM / LLM capability, without going through the full
classroom processing flow.

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
| `Qwen/Qwen3.6-35B-A3B` | int4, int8 |

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
