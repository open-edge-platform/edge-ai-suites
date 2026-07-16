---
name: sc-files
description: >
  List, inspect, filter, and delete files that have been indexed in the Content
  Search backend. Also lists available tags for use in Q&A filtering.
  Use when the user says "list files", "show indexed files", "what files are
  uploaded", "delete a file", "remove file", "list tags", or "manage files".
---

# SC Files

List, inspect, and delete files indexed in the Content Search backend.
**Agent: execute every command below directly using your terminal tool and relay
the output.** Endpoints use the base URL `http://127.0.0.1:9011`.

Set `$BASE = "http://127.0.0.1:9011"` for all snippets.

---

## Preconditions

Backend must be reachable — probe first:

```powershell
$BASE = "http://127.0.0.1:9011"
Invoke-WebRequest -Uri "$BASE/api/v1/system/health" -UseBasicParsing |
    Select-Object -ExpandProperty Content
```

If unreachable, use [`sc-doctor`](../sc-doctor/SKILL.md) / [`sc-up`](../sc-up/SKILL.md).

---

## 1. List all indexed files

`GET /api/v1/object/files/list` — supports pagination and optional type filter.
**The response is wrapped:** `{ "data": { "files": [...] } }` — not a bare array.

```powershell
$BASE = "http://127.0.0.1:9011"
$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/files/list?page=1&page_size=50" `
     -UseBasicParsing
$files = ($r.Content | ConvertFrom-Json).data.files
$files | Select-Object file_name, @{N="type";E={$_.meta.type}}, @{N="size_mb";E={[math]::Round($_.size_bytes / 1MB, 2)}}, @{N="vectors";E={$_.index.vector_count}}, status |
    Format-Table -AutoSize
```

### Filter by file type

```powershell
# Only documents
$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/files/list?file_type=document" `
     -UseBasicParsing

# Only videos
$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/files/list?file_type=video" `
     -UseBasicParsing

# Only images
$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/files/list?file_type=image" `
     -UseBasicParsing
```

### Paginate through large libraries

```powershell
$page = 1; $pageSize = 20; $allFiles = @()
do {
    $r = Invoke-WebRequest -Uri "$BASE/api/v1/object/files/list?page=${page}&page_size=${pageSize}" `
         -UseBasicParsing
    $batch = ($r.Content | ConvertFrom-Json).data.files
    $allFiles += $batch
    $page++
} while ($batch.Count -eq $pageSize)
Write-Host "Total files: $($allFiles.Count)"
$allFiles | Select-Object file_name | Format-Table -AutoSize
```

---

## 2. Inspect a single file

The `file_hash` (SHA-256 hex, 64 chars) uniquely identifies a file and is the
key used for deletion. Extract it from the list:

```powershell
$target = "lecture-notes.pdf"
$file = ($files | Where-Object { $_.file_name -eq $target })
if ($file) {
    $file | ConvertTo-Json -Depth 5
    Write-Host "file_hash: $($file.file_hash)"
} else {
    Write-Host "File '$target' not found in index"
}
```

The `file_hash` is also referred to as `file_key` in the upload response and
in the Flutter `UploadEntry.fileKey` field.

---

## 3. List available tags

Tags can be used to filter Q&A retrieval. See all distinct tags across indexed files:

```powershell
$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/tags" -UseBasicParsing
$tags = ($r.Content | ConvertFrom-Json).data
Write-Host "Available tags: $($tags -join ', ')"
```

---

## 4. Delete a file

`DELETE /api/v1/object/files/{file_hash}` — the `file_hash` (SHA-256 hex, 64 chars)
comes from the list response. **Deletion removes the file and all its vectors from
the index. This cannot be undone — confirm with the user first.**

```powershell
# ⚠️  Destructive — confirm before running
$FILE_HASH = "<file_hash_from_step_2>"
$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/files/$FILE_HASH" `
     -Method Delete `
     -UseBasicParsing
Write-Host "Delete response: $($r.StatusCode)"
$r.Content | ConvertFrom-Json | ConvertTo-Json
```

Verify deletion by listing files again (step 1) — the file should no longer appear.

### Bulk delete by type or tag

```powershell
# ⚠️  Destructive — confirm before running
$BASE = "http://127.0.0.1:9011"
$r = Invoke-WebRequest -Uri "$BASE/api/v1/object/files/list?page=1&page_size=200" `
     -UseBasicParsing
$files = ($r.Content | ConvertFrom-Json).data.files

# Delete all video files (example)
$toDelete = $files | Where-Object { $_.meta.type -eq "video" }
foreach ($f in $toDelete) {
    Write-Host "Deleting: $($f.file_name) ($($f.file_hash))"
    Invoke-WebRequest -Uri "$BASE/api/v1/object/files/$($f.file_hash)" `
        -Method Delete -UseBasicParsing | Out-Null
}
Write-Host "Deleted $($toDelete.Count) video(s)"
```

---

## FileAsset response shape

The Flutter app maps `GET /api/v1/object/files/list` through `FileAsset.fromJson`:

| JSON path | Flutter field | Notes |
|---|---|---|
| `file_name` | `fileName` | Display name |
| `file_hash` | `fileHash` | SHA-256 hex — used as `file_key` for deletion |
| `meta.type` | `fileType` | `"document"` \| `"video"` \| `"image"` |
| `index.total_vectors` | `totalVectors` | Number of embedding chunks |

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| Empty files list | No files uploaded yet | Run `sc-upload` |
| Delete returns 404 | Wrong `file_hash` / file already deleted | Re-list files to get correct `file_hash` |
| Tags list is empty | No tags set at upload time | Re-upload with `meta.tags` set |
| File has 0 vectors | Indexing in progress or failed | Check task status: `GET /api/v1/task/query/{task_id}` for status and errors |

---

## Output

Report: **total file count** → **file names + types + vector counts** →
**available tags** → **deletion confirmation** (if requested).
