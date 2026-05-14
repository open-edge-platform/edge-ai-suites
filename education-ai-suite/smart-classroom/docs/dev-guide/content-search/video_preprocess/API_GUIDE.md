# Video Chunk Summarization — API Guide

Base URL: `http://<host>:8001`

---

## Table of Contents

1. [Health Check](#health-check)
2. [Preprocess Video](#preprocess-video)
   - [Request Body](#request-body)
   - [Response Format (NDJSON)](#response-format-ndjson)
   - [Example Requests](#example-requests)
3. [Storage Output Layout](#storage-output-layout)
4. [Per-chunk Ingestion](#per-chunk-ingestion)
5. [Error Responses](#error-responses)

---

## Health Check

### `GET /health`

Check whether the preprocess service is running.

**Request**

```bash
curl http://localhost:8001/health
```

**Response**

```json
{ "status": "ok" }
```

---

## Preprocess Video

### `POST /preprocess`

Processes a source video from Storage and streams progress as each chunk completes:

1. Download video from Storage
2. Split into time-based chunks
3. Sample frames per chunk
4. Call VLM endpoint to summarize each chunk
5. Upload chunk summary and metadata back to Storage
6. (Optional) Ingest chunk summary into vector database
7. Yield one NDJSON line per completed chunk, then a final summary line

The response uses **chunked transfer encoding** — the HTTP connection stays open and lines are streamed as work completes. This is suitable for long videos (e.g., 1-hour lectures with 120+ chunks).

### Request Body

| Field | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `file_key` | string | Yes | — | non-empty | Storage object key of source video |
| `job_id` | string | No | auto UUID | — | Caller-provided job id for tracing |
| `run_id` | string | No | auto UUID | — | Run namespace used in derived output paths |
| `asset_id` | string | No | filename from `file_key` | — | Asset id used in derived output paths |
| `tags` | string[] | No | `null` | — | Optional tags forwarded to the ingestion service meta for each chunk |
| `chunk_duration_s` | integer | No | `30`* | `>= 1` | Chunk duration (seconds) |
| `chunk_overlap_s` | integer | No | `4`* | `>= 0` | Overlap between adjacent chunks (seconds) |
| `max_num_frames` | integer | No | `8`* | `>= 1` | Max sampled frames per chunk |
| `prompt` | string | No | `Please summarize this video.` | — | Prompt used for each chunk summary |
| `max_completion_tokens` | integer | No | `500` | `>= 1` | Max completion tokens sent to VLM |
| `vlm_endpoint` | string | No | service default | — | Override VLM endpoint (normally `/v1/chat/completions`) |
| `vlm_timeout_seconds` | integer | No | service default | `>= 1` | Override VLM request timeout |
| `reuse_existing` | boolean | No | `true` | — | Reuse existing summary if parameters match |

\* Runtime defaults can be configured at service startup (`start_service.py` / config).

---

### Response Format (NDJSON)

The response body is a stream of newline-delimited JSON lines (`Content-Type: application/x-ndjson`).

#### Chunk line — emitted after each chunk completes

```json
{
  "type": "chunk",
  "chunk_id": "chunk_0001",
  "chunk_index": 1,
  "start_time": 0.0,
  "end_time": 30.0,
  "reused": false,
  "ingest_status": "pending",
  "error": null
}
```

| Field | Description |
|---|---|
| `chunk_id` | Chunk identifier, e.g. `chunk_0001` |
| `chunk_index` | 1-based index |
| `start_time` / `end_time` | Time range in seconds |
| `reused` | `true` if an existing summary was reused |
| `ingest_status` | `pending` \| `ok` \| `failed` \| `skipped` — `pending` means ingest is still running in background |
| `error` | Error message if VLM or Storage write failed for this chunk; `null` on success |

#### Done line — emitted after all chunks complete and ingestion finishes

```json
{
  "type": "done",
  "job_id": "5d7c2c6b-1d19-4f60-b4fb-22ac5df43f4b",
  "run_id": "run_20260319_001",
  "asset_id": "asset_001",
  "total_chunks": 3,
  "succeeded_chunks": 3,
  "failed_chunks": 0,
  "ingest_ok_chunks": 3,
  "ingest_failed_chunks": 0,
  "elapsed_seconds": 205.3
}
```

#### Error line — emitted if a fatal error occurs before processing starts

```json
{ "type": "error", "message": "RuntimeError: Object not found: ..." }
```

> **Note:** Per-chunk errors (e.g., a single chunk VLM failure) do **not** produce an error line — they appear in the `error` field of the corresponding chunk line, and processing continues with the next chunk.

---

### Example Requests

**curl — print each line as it arrives**

```bash
curl -N -X POST http://localhost:8001/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "file_key": "runs/raw/video/asset_001/demo.mp4",
    "chunk_duration_s": 30,
    "chunk_overlap_s": 4,
    "max_num_frames": 8,
    "prompt": "Summarize key events in this segment.",
    "max_completion_tokens": 300,
    "tags": ["lecture", "demo"]
  }'
```

(`-N` disables buffering so lines appear immediately.)

**PowerShell — real-time line-by-line output**

```powershell
$req = [pscustomobject]@{
    file_key       = "runs/raw/video/asset_001/demo.mp4"
    chunk_duration_s      = 30
    chunk_overlap_s       = 4
    max_num_frames        = 8
    prompt                = "Summarize key events in this segment."
    max_completion_tokens = 300
} | ConvertTo-Json -Depth 10

$webRequest = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:8001/preprocess")
$webRequest.Method = "POST"
$webRequest.ContentType = "application/json"
$webRequest.Timeout = -1  # no timeout — required for long videos

$body = [System.Text.Encoding]::UTF8.GetBytes($req)
$webRequest.ContentLength = $body.Length
$reqStream = $webRequest.GetRequestStream()
$reqStream.Write($body, 0, $body.Length)
$reqStream.Close()

$reader = [System.IO.StreamReader]::new($webRequest.GetResponse().GetResponseStream())
while (-not $reader.EndOfStream) {
    $line = $reader.ReadLine()
    if ($line) { $line | ConvertFrom-Json }
}
$reader.Close()
```

**PowerShell — wait for all results then parse (short videos only)**

```powershell
# Invoke-WebRequest buffers the full response — only suitable for short videos
$response = Invoke-WebRequest -Uri "http://127.0.0.1:8001/preprocess" `
    -Method POST -ContentType "application/json" -Body $req -TimeoutSec 0
$response.Content -split "`n" | Where-Object { $_ } | ForEach-Object { $_ | ConvertFrom-Json }
```

---

## Storage Output Layout

For each request, the service writes derived artifacts under:

- `runs/{run_id}/derived/video/{asset_id}/chunksum-v1/summaries/{chunk_id}/summary.txt`
- `runs/{run_id}/derived/video/{asset_id}/chunksum-v1/summaries/{chunk_id}/metadata.json`
- `runs/{run_id}/derived/video/{asset_id}/chunksum-v1/manifest.json`

`manifest.json` records run parameters, per-chunk keys, and final ingest status for all chunks.

---

## Per-chunk Ingestion

If `ingest.enabled = true` is set in `config.json`, each chunk's summary is automatically posted to the ingestion service (`POST /v1/dataprep/ingest_text`) after it is written to Storage. Ingestion runs in a background thread and does not block the next chunk's VLM call.

The request payload sent to the ingestion service for each chunk:

| Field | Description |
|---|---|
| `bucket_name` | Storage bucket name |
| `file_path` | Storage object key of `summary.txt` |
| `text` | Summary text content (the full chunk summary string) |
| `meta` | Metadata object — see table below |

The `meta` object contains:

| Field | Description |
|---|---|
| `tags` | Tags from the original request (`null` if not provided) |
| `chunk_id` | e.g. `chunk_0001` |
| `chunk_index` | 1-based index |
| `asset_id` | Video asset identifier |
| `run_id` | Run UUID |
| `file_key` | Source video object key |
| `start_time` / `end_time` | Time range in seconds |
| `start_frame` / `end_frame` | Frame range |
| `summary_key` | Storage key of the summary text file |
| `reused` | Whether the summary was reused from a previous run |

Enable ingestion in `scripts/config.json`:

```json
{
  "ingest": {
    "enabled": true,
    "ingest_port": 7000,
    "bucket": "your-bucket-name"
  }
}
```

---

## Error Responses

| Code | Meaning |
|---|---|
| `422` | Validation error in request body (e.g., missing `file_key`, invalid numeric range) |
| `500` | Fatal processing failure before streaming starts (e.g., Storage config missing, VLM endpoint not configured) |

Per-chunk failures (VLM error, Storage write error) do **not** return HTTP 500 — they are reported inline in the stream as `"error": "..."` on the corresponding chunk line, and processing continues with remaining chunks.
