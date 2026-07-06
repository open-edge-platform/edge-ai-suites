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
license: Apache-2.0
metadata:
  version: "1.0.0"
  tags: "sc operational upload ingest"
---

<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# SC Upload

Upload a file to the Content Search backend and wait for ingestion to complete.
**Agent: execute every command below directly using your terminal tool and relay
the output.** Endpoints use the base URL `http://127.0.0.1:9011`.

Set `$BASE = "http://127.0.0.1:9011"` for all snippets.

---

## Preconditions

### Set corporate proxy (required for any outbound download; localhost API calls bypass it)

```powershell
$env:HTTPS_PROXY = "http://proxy-chain.intel.com:911"
$env:HTTP_PROXY  = "http://proxy-chain.intel.com:911"
$env:https_proxy = "http://proxy-chain.intel.com:911"
$env:http_proxy  = "http://proxy-chain.intel.com:911"
$env:NO_PROXY    = "localhost,127.0.0.1"
$env:no_proxy    = "localhost,127.0.0.1"
```

> The API calls below go to `127.0.0.1` which is in `NO_PROXY` and bypass the
> proxy automatically. The block above is included so this skill is self-contained.

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

`POST /api/v1/object/upload-ingest` is a multipart form request with two fields:
- `file` — the binary file
- `meta` — a JSON string with optional metadata (tags, description)

See [`references/upload-request.md`](./references/upload-request.md) for the
full `meta` schema.

```powershell
$BASE     = "http://127.0.0.1:9011"
$FilePath = "utils\flutter\sample-files\6.KnowledgeBasedSystems.pdf"   # <-- replace with actual path
$Tags     = "knowledge"                  # optional comma-separated tags

# tags is a JSON array, not a comma-separated string
$tagsArray = $Tags -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
$meta = @{
    file_name = [System.IO.Path]::GetFileName($FilePath)
    type      = "document"   # or "video" / "image" — match the file type
    tags      = $tagsArray
} | ConvertTo-Json -Compress

# Build multipart form and POST
Add-Type -AssemblyName System.Net.Http
$client   = [System.Net.Http.HttpClient]::new()
$content  = [System.Net.Http.MultipartFormDataContent]::new()
$fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
$fileContent = [System.Net.Http.ByteArrayContent]::new($fileBytes)
$fileContent.Headers.ContentType =
    [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/octet-stream")
$content.Add($fileContent, "file", [System.IO.Path]::GetFileName($FilePath))
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
    "status": "QUEUED",
    "file_key": "<FILE_KEY>"
  }
}
```

> **Duplicate detection:** if `code == 40901`, the file already exists. Go to
> step 1b (cleanup and retry) or skip directly to step 2 to poll the existing
> task.

### 1b. Handle duplicate (code 40901)

```powershell
# Extract task_id from the 40901 response, then clean it up
$TASK_ID = $body.data.task_id
Invoke-WebRequest -Uri "$BASE/api/v1/object/cleanup-task/$TASK_ID" `
    -Method Delete -UseBasicParsing
# Now retry the upload from step 1
```

---

## 2. Poll task status until complete

Poll `GET /api/v1/task/query/{task_id}` every 3 seconds.
Terminal statuses are `COMPLETED`, `FAILED`, and `ALREADY_EXISTS`.

```powershell
$TASK_ID = "<TASK_ID>"   # from step 1 response
$deadline = (Get-Date).AddMinutes(10)

do {
    Start-Sleep -Seconds 3
    $r = Invoke-WebRequest -Uri "$BASE/api/v1/task/query/$TASK_ID" `
         -UseBasicParsing
    $task = ($r.Content | ConvertFrom-Json).data
    Write-Host "[$([datetime]::Now.ToString('HH:mm:ss'))] status=$($task.status)  progress=$($task.progress)"

    if ($task.status -in @("COMPLETED","FAILED","ALREADY_EXISTS")) { break }
} while ((Get-Date) -lt $deadline)

Write-Host "Final status: $($task.status)"
```

- **`COMPLETED`** → file is indexed and ready for Q&A. Note the `file_key` for
  deletion later.
- **`FAILED`** → ingestion error. Read `task.error` for the reason; check backend
  logs with `sc-doctor`.
- **Timeout (10 min)** → the backend is overloaded or stalled. Check
  `sc-doctor`.

---

## 3. Confirm the file appears in the index

```powershell
$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/files/list?page=1&page_size=20" `
     -UseBasicParsing
($r.Content | ConvertFrom-Json).data.files |
    Select-Object file_key, file_name, file_type, status |
    Format-Table -AutoSize
```

The newly ingested file should appear with `status = indexed` (or equivalent).

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `code: 40901` | File already exists | Cleanup task (step 1b) then retry, or skip to step 2 |
| `FAILED` status | Ingestion pipeline error | Check `task.error`; check backend logs via `sc-doctor` |
| Timeout after 10 min | Backend overloaded or stalled | Restart backend (`sc-up`); reduce file size |
| Unsupported file type | Extension not in allowed list | Convert to a supported format (e.g. save as PDF) |
| 413 Request Entity Too Large | File exceeds backend upload limit | Check `smart-classroom/content_search/` config for `MAX_UPLOAD_SIZE` |
| Connection reset during upload | Large video upload timeout | Increase Dio `sendTimeout` in `app_config.dart` (currently 15 min) |

---

## Output

Report: **task_id** → **status polling log** → **final `COMPLETED`** →
file appears in `GET /api/v1/object/files/list`.
