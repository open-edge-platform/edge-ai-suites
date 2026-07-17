---
name: sc-upload
description: >
  Upload a file to the Content Search backend and poll the ingestion task until
  the file is fully indexed (status COMPLETED). Handles duplicate detection
  (code 40901), cleanup-and-retry, and task timeout. Supported file types: pdf,
  txt, docx, doc, pptx, ppt, xlsx, xls, jpg, jpeg, png, mp4, avi, mov, mkv.
  Use when the user says "upload a file", "ingest a document", "upload pdf",
  "index a file", "add course material", "upload video", "upload image", or
  "ingest content".
---

# SC Upload

Upload a file to the Content Search backend and wait for ingestion to complete.
**Agent: execute every command below directly using your terminal tool and relay
the output.** Endpoints use the base URL `http://127.0.0.1:9011`.

Set `$BASE = "http://127.0.0.1:9011"` for all snippets.

---

## Preconditions

### Set corporate proxy (required for any outbound download; localhost API calls bypass it)

Probe health first — if the backend is unreachable, use
[`sc-doctor`](../sc-doctor/SKILL.md) / [`sc-up`](../sc-up/SKILL.md):

```powershell
$BASE = "http://127.0.0.1:9011"
Invoke-WebRequest -Uri "$BASE/api/v1/system/health" -UseBasicParsing |
    Select-Object -ExpandProperty Content
```

The file must be one of the supported extensions:
`pdf`, `txt`, `docx`, `doc`, `pptx`, `ppt`, `xlsx`, `xls`,
`jpg`, `jpeg`, `png`, `mp4`, `avi`, `mov`, `mkv`.

---

## 1. Upload and trigger ingestion

**🤖 Agent instruction:** Before executing the command below, use the `vscode_askQuestions` tool to:
1. **Get the file path** to upload (user must provide full path)
2. **Optionally ask for tags** (comma-separated, e.g., "knowledge,ai,tutorial")

`POST /api/v1/object/upload-ingest` is a multipart form request with two fields:
- `file` — the binary file
- `meta` — a JSON string with optional metadata (tags, description)

See [`references/upload-request.md`](./references/upload-request.md) for the
full `meta` schema.

```powershell
$BASE     = "http://127.0.0.1:9011"
# Agent: Set $FilePath to the user-provided file path from ask_user
$FilePath = "<USER_PROVIDED_FILE_PATH>"
# Agent: Set $Tags to user-provided tags (or empty string if none)
$Tags     = "<USER_PROVIDED_TAGS_OR_EMPTY>"

# Determine file type from extension
$extension = [System.IO.Path]::GetExtension($FilePath).TrimStart('.').ToLower()
$fileType = switch ($extension) {
    { $_ -in @('pdf','txt','docx','doc','pptx','ppt','xlsx','xls') } { "document" }
    { $_ -in @('jpg','jpeg','png') } { "image" }
    { $_ -in @('mp4','avi','mov','mkv') } { "video" }
    default { "document" }
}

$fileName = [System.IO.Path]::GetFileName($FilePath)

# Manually construct JSON to ensure tags is always an array (not a string)
if ($Tags) {
    $tagsList = ($Tags -split ',' | ForEach-Object { "`"$($_.Trim())`"" }) -join ","
    $meta = "{`"file_name`":`"$fileName`",`"type`":`"$fileType`",`"tags`":[$tagsList]}"
} else {
    $meta = "{`"file_name`":`"$fileName`",`"type`":`"$fileType`"}"
}

# Build multipart form and POST
Add-Type -AssemblyName System.Net.Http
$client   = [System.Net.Http.HttpClient]::new()
$content  = [System.Net.Http.MultipartFormDataContent]::new()
$fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
$fileContent = [System.Net.Http.ByteArrayContent]::new($fileBytes)
$fileContent.Headers.ContentType =
    [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/octet-stream")
$content.Add($fileContent, "file", $fileName)
$content.Add([System.Net.Http.StringContent]::new($meta), "meta")

$response = $client.PostAsync("$BASE/api/v1/object/upload-ingest", $content).Result
$body     = $response.Content.ReadAsStringAsync().Result | ConvertFrom-Json
$body | ConvertTo-Json -Depth 5
```

**Expected response:**
```json
{
  "code": 20000,
  "data": {
    "task_id": "<TASK_ID>",
    "status": "PROCESSING",
    "file_key": "<FILE_KEY>"
  },
  "message": "Success",
  "timestamp": 1234567890
}
```

> **Duplicate detection:** if `code == 40901`, the file already exists (detected by SHA256 hash). The response includes the existing `task_id` and `file_hash`. Re-upload is allowed if the previous task status is `FAILED`. Go to step 1b (cleanup and retry) or skip directly to step 2 to poll the existing task.

### 1b. Handle duplicate (code 40901)

The cleanup endpoint deletes:
- Entire run directory: `runs/{run_id}/` (raw files, derived files, OCR outputs)
- ChromaDB vector index entries
- FileAsset database record
- AITask database record

```powershell
# Agent: Extract task_id from the 40901 response ($body.data.task_id)
$TASK_ID = $body.data.task_id
Invoke-WebRequest -Uri "$BASE/api/v1/object/cleanup-task/$TASK_ID" `
    -Method Delete -UseBasicParsing
# Now retry the upload from step 1
```

> **Note**: Cleanup fails if the task status is `PROCESSING`. Wait for completion or failure first.

---

## 2. Poll task status until complete

Poll `GET /api/v1/task/query/{task_id}` every 3 seconds.
Terminal statuses are `COMPLETED` and `FAILED`.

> **Note**: The `progress` field is always 100 (hardcoded) and is not a real progress indicator. Status transitions are: `QUEUED` → `PROCESSING` → `COMPLETED`/`FAILED`.

```powershell
# Agent: Extract $TASK_ID from the response in step 1 ($body.data.task_id)
$TASK_ID = $body.data.task_id
$deadline = (Get-Date).AddMinutes(10)

do {
    Start-Sleep -Seconds 3
    $r = Invoke-WebRequest -Uri "$BASE/api/v1/task/query/$TASK_ID" `
         -UseBasicParsing
    $task = ($r.Content | ConvertFrom-Json).data
    Write-Host "[$([datetime]::Now.ToString('HH:mm:ss'))] status=$($task.status)  progress=$($task.progress)"

    if ($task.status -in @("COMPLETED","FAILED")) { break }
} while ((Get-Date) -lt $deadline)

Write-Host "Final status: $($task.status)"
```

- **`COMPLETED`** → file is indexed and ready for Q&A. Note the `file_key` for deletion later. If the file is a PDF and OCR is enabled, the result will include `ocr_text_key`. If video summarization was requested, result includes `video_summary` and `video_summary_status`.
- **`FAILED`** → ingestion error. Read `task.result.error` for the reason; check backend logs with `sc-doctor`. Failed tasks trigger automatic cleanup of FileAsset, physical file, and ChromaDB entries.
- **Timeout (10 min)** → the backend is overloaded or stalled. Check `sc-doctor`.

---

## 3. Confirm the file appears in the index

```powershell
$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/files/list?page=1&page_size=20" `
     -UseBasicParsing
$files = ($r.Content | ConvertFrom-Json).data.files
$files | Select-Object file_name, @{N="type";E={$_.meta.type}}, @{N="vectors";E={$_.index.vector_count}}, status |
    Format-Table -AutoSize
```

**Note**: The file is searchable when the task status is `COMPLETED`. Vector indexing may
take a few additional seconds to appear in the list, but the task completion is the
source of truth for searchability.

---

## 4. Advanced Backend Features

### OCR Processing (PDFs)

When `OCR_ENABLED=true` (environment variable), PDF files are automatically processed:
1. External OCR service is called at `http://127.0.0.1:8000` (timeout: 120s)
2. Extracted text is saved as `.ocr.txt` file in the same run directory
3. Vector indexing uses the OCR text file instead of the original PDF
4. The `task.result` includes `ocr_text_key` pointing to the extracted text

### Video Summarization

When `VIDEO_SUMMARIZATION_ENABLED=true` (default), videos can be summarized:
1. Pass `vs_enabled: true` in the `meta` object to enable per-file
2. Optionally provide `prompt` and `chunk_duration` in the upload request
3. Summarization runs AFTER the task is marked `COMPLETED` (file is already searchable)
4. The `task.result` includes `video_summary` and `video_summary_status`
5. Generated summaries are stored in `runs/{run_id}/derived/`

### File Integrity Validation

PDF and video files (PDF, MP4, AVI, MOV, MKV) undergo integrity validation:
- PDF: checked for valid structure
- Video: validated for proper format and codec
- Corrupted files result in FAILED task with `error_type: "corrupted_file"`

### Automatic Cleanup on Failure

When indexing fails, the backend automatically cleans up:
- FileAsset database record
- Physical file in storage
- ChromaDB vector index entries

This prevents orphaned data and allows re-upload with the same file.

---

## Response Codes Reference

| Code | Meaning | Action |
|---|---|---|
| `20000` | Success | Continue to next step |
| `40000` | Bad request | Check request parameters |
| `40002` | Invalid file | File failed validation (unsupported type) |
| `40901` | File already exists (duplicate) | Cleanup and retry, or poll existing task |
| `41301` | File too large | Reduce file size or increase backend limits |
| `50002` | Task not found | Task may have expired or been deleted |
| `50003` | Process failed | Check backend logs for details |

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `code: 40901` | File already exists (duplicate hash) | Cleanup task (step 1b) then retry, or skip to step 2 if re-uploading after FAILED task |
| `code: 40002` | Invalid/unsupported file type | Check file extension against allowed list; convert to supported format |
| `code: 41301` | File too large | Default limits: documents 100MB, videos 1024MB; check/update env vars `DOCUMENT_MAX_MB`, `VIDEO_MAX_MB` |
| `FAILED` status | Ingestion pipeline error | Check `task.result.error`; check backend logs via `sc-doctor` |
| Timeout after 10 min | Backend overloaded or stalled | Restart backend (`sc-up`); reduce file size |
| Connection reset during upload | Large video upload timeout | Backend accepts large files; check network/firewall settings |
| Corrupted file error | File integrity check failed | Re-download or re-export the file; ensure proper encoding |
| OCR timeout | OCR service unavailable | Ensure OCR service is running at port 8000; check `OCR_ENABLED` env var |

---

## Output

Report: **task_id** → **status polling log** → **final `COMPLETED`** →
file appears in `GET /api/v1/object/files/list`.

**Note**: Task `COMPLETED` status means the file is searchable. Vector counts in the file
list may take a few seconds to update, but searchability is determined by task completion.
