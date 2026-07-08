# Upload Request — `meta` Schema Reference

The `meta` field in `POST /api/v1/object/upload-ingest` is a **JSON string**
(not a nested object) passed as a form field alongside the file binary.

## Minimal `meta`

```json
{
  "file_name": "lecture-notes.pdf",
  "type": "document"
}
```

`file_name` and `type` are always included by the Flutter `UploadNotifier`. All other fields are optional.

## Full `meta` schema

```json
{
  "file_name": "lecture-notes.pdf",
  "type": "document",
  "tags": ["mathematics", "week1", "linear-algebra"]
}
```

## Field reference

| Field | Type | Required | Description |
|---|---|---|---|
| `file_name` | `string` | Yes | Original filename. Always sent by `UploadNotifier`. |
| `type` | `string` | Yes | Inferred file category: `"document"` \| `"video"` \| `"image"`. Always sent. |
| `tags` | `array<string>` | No | **JSON array of tag strings** — NOT a comma-separated string. Omitted entirely when no tags are set. Tags are indexed for filtering in Q&A. |

## `type` inference rules

| Extensions | `type` value |
|---|---|
| `mp4`, `avi`, `mov`, `mkv` | `"video"` |
| `jpg`, `jpeg`, `png` | `"image"` |
| `pdf`, `txt`, `docx`, `doc`, `pptx`, `ppt`, `xlsx`, `xls` | `"document"` |

## How tags work in the Flutter UI

Tags are added per-file in the Upload screen **before** clicking Upload:
1. Each `UploadEntry` starts with `tags: []` when staged.
2. The user types a tag in the inline text field on the entry card and presses
   Enter or comma — each keystroke calls `UploadNotifier.updateEntryTags(id, tags)`.
3. On upload, `UploadNotifier.uploadEntry()` reads `entry.tags` (a `List<String>`) and
   includes it in `meta` only when non-empty.
4. Tags can be queried later via `GET /api/v1/object/tags` which returns all distinct
   tags across indexed files.
5. Tags filter Q&A retrieval when passed in `POST /api/v1/object/qa` → `filter.tags`.

## Example PowerShell invocation

```powershell
# Tags must be a JSON array — not a comma-separated string
$meta = @{
    file_name = "lecture-notes.pdf"
    type      = "document"
    tags      = @("mathematics", "week1", "linear-algebra")
} | ConvertTo-Json -Compress
# $meta = '{"file_name":"lecture-notes.pdf","type":"document","tags":["mathematics","week1","linear-algebra"]}'
```
