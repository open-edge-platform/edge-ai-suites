<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Report Generator API Frontend Guide

This document is derived from the backend implementation:
- `api/report.py`
- `dto/report_dto.py`
- `model_manager/features/report_feature.py`
- `config.yaml` (`features.report`)

Use it as a frontend integration reference.

## Availability and Feature Switch

Report endpoints are mounted through the feature module system.

- Feature id: `report`
- Config switch: `features.report.enabled`
- Dependency features: `summary`, `mindmap`, `topic_segmentation`

When `features.report.enabled` is `false`, the `/report/*` endpoints are not mounted,
and report generation requests should be treated as unavailable by frontend logic.

## Frontend Quick Start

1. Confirm `report` feature is enabled (recommend calling `/features` and checking `id == "report"`).
2. Call `/report/template-fields` to render checkboxes and manual inputs.
3. Build `selected_fields` from checked items (exclude `always_on` items from UI toggles).
4. Build `manual_fields` for fields marked with `input: "manual"`.
5. Optional: upload mindmap screenshot via `/report/{session_id}/mindmap-image`.
6. Call `/report/generate` and consume NDJSON stream.
7. Only treat generation as success after receiving `report_ready`.
8. If user changes field selection after generation, call `/report/{session_id}/reselect` (no LLM rerun).

## API Summary (All Endpoints)

| Method | Path | Purpose | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/report/generate` | Generate class report with streaming events | `ReportRequest` (`session_id`, `selected_fields`, `manual_fields`, optional `query`) | NDJSON stream (`partial_report`, `report`, `report_ready`, `token`) |
| `GET` | `/report/template-fields` | Get field catalog for UI checkbox selection | None | JSON (`groups`) |
| `POST` | `/report/{session_id}/mindmap-image` | Upload rendered mindmap image for report embedding | `multipart/form-data` with `file` | JSON (`session_id`, `path`) |
| `GET` | `/report/{session_id}/mindmap-image` | Fetch uploaded mindmap image for inline markdown preview | None | `image/png` file |
| `GET` | `/report/{session_id}` | Read generated report markdown | None | JSON (`session_id`, `report`) |
| `GET` | `/report/{session_id}/download?format=docx or pdf` | Download report in DOCX/PDF | None | `.docx` or `.pdf` file |
| `POST` | `/report/{session_id}/reselect` | Re-apply field selection without LLM regeneration | `ReportReselectRequest` (`selected_fields`, `manual_fields`) | JSON (`session_id`, `message`, updated report payload) |

---

## Detailed API Specs

### 1. Generate Report (Streaming)

- Method: `POST`
- Path: `/report/generate`
- Content-Type: `application/json`
- Response: `StreamingResponse` (`application/json`, line-delimited NDJSON)

### Request Body

```json
{
  "session_id": "20260708-100000-abcd",
  "query": "optional, compatibility field",
  "selected_fields": ["school_name", "class_name", "interaction_level"],
  "manual_fields": {
    "school_name": "Example High School",
    "class_name": "Grade 10 - Class 3",
    "course_name": "Physics",
    "teacher_name": "Ms. Zhang"
  }
}
```

Field notes:
- `session_id`: required.
- `query`: optional compatibility field.
- `selected_fields`: optional checked field codes; if omitted, all catalog fields are included.
- `manual_fields`: optional teacher-entered field values.

Manual-field behavior for frontend:
- Valid manual field codes: `school_name`, `class_name`, `course_name`, `teacher_name`.
- Whether a manual field appears in report is controlled by `selected_fields`.
- If selected and manual value is empty, backend uses default placeholders so teachers can see where to edit:
  - `school_name`: `XXX中学`
  - `class_name`: `八（3）班`
  - `course_name`: `《XXXX》`
  - `teacher_name`: `XX老师`
- If not selected, that field is dropped from report.

### Stream Events (NDJSON)

The server emits one JSON object per line. Common event shapes:

1. `partial_report` / `report`
```json
{"type":"partial_report","content":"...markdown..."}
```

2. `report_ready`
```json
{"type":"report_ready","session_id":"20260708-100000-abcd"}
```

3. `token`
```json
{"token":"...","error":""}
```

Error token shape:
```json
{"token":"","error":"[ERROR]: ..."}
```

Frontend stream handling rule:
- Stream ending is not equal to success.
- Success condition: receive `{"type":"report_ready", ...}`.
- If stream ends without `report_ready`, treat as failed/incomplete generation.

Token note:
- Template mode usually emits `partial_report` then final `report`, and `token` appears mainly for status/error text.
- Non-template mode emits generated text progressively via `token` and may not emit a `report` payload.

---

### 2. Report Field Catalog (for UI Checkboxes)

- Method: `GET`
- Path: `/report/template-fields`
- Response: JSON

### Response Example

```json
{
  "groups": [
    {
      "group_key": "basic_info",
      "fields": [
        {
          "code": "school_name",
          "kind": "raw",
          "input": "manual",
          "label_key": "school_name"
        },
        {
          "code": "report_time",
          "kind": "raw",
          "always_on": true,
          "label_key": "report_time"
        }
      ]
    }
  ]
}
```

Notes:
- `group_key` and `label_key` are i18n keys used by the frontend.
- Some fields include `input: "manual"` (teacher-typed values).
- Some fields include `always_on: true` (auto metadata, not user-toggleable).
- `always_on` fields are auto-included by backend and should not be rendered as user checkboxes.
- `groups` is for UI organization only (section display + group toggle); backend ultimately consumes flat `selected_fields` and `manual_fields`.

---

### 3. Upload Mindmap Image (for Report Embedding)

- Method: `POST`
- Path: `/report/{session_id}/mindmap-image`
- Content-Type: `multipart/form-data`
- Form field: `file` (required, usually PNG)

### Response Example

```json
{
  "session_id": "20260708-100000-abcd",
  "path": ".../mindmap_report.png"
}
```

Notes:
- The backend only saves the uploaded image and does not re-render the mindmap.
- The file is saved to the session directory as `mindmap_report.png`.

### 3.1 Get Mindmap Image (for Inline Preview)

- Method: `GET`
- Path: `/report/{session_id}/mindmap-image`
- Response: `image/png`

Notes:
- Returns `404` when the session has no uploaded `mindmap_report.png`.
- The report markdown now contains a direct session-scoped image URL: `/report/{session_id}/mindmap-image`.

---

### 4. Get Generated Report Content

- Method: `GET`
- Path: `/report/{session_id}`
- Response: JSON

### Response Example

```json
{
  "session_id": "20260708-100000-abcd",
  "report": "# Classroom Evaluation Report\n..."
}
```

Returns `404` if the report does not exist.

Frontend suggestion:
- `404` can be mapped to an empty state (no generated report yet), not a fatal page-level error.

---

### 5. Download Report (Unified Endpoint)

- Method: `GET`
- Path: `/report/{session_id}/download?format=docx|pdf`
- Response: `FileResponse` (`.docx` or `.pdf`)

Notes:
- `format=docx` returns Word format (default if format is omitted).
- If only `class_report.md` exists, the backend first generates `class_report.docx` and then returns it.
- `format=pdf` performs server-side conversion from DOCX to PDF and returns the PDF file.

---

Additional PDF notes:
- Requires `LibreOffice` (`soffice`) installed on the server.
- Returns `501` when `soffice` is unavailable.
- Reuses cached PDF when it exists and is up-to-date.

---

### 6. Re-apply Field Selection (No LLM)

- Method: `POST`
- Path: `/report/{session_id}/reselect`
- Content-Type: `application/json`

### Request Body

```json
{
  "selected_fields": ["school_name", "class_name", "interaction_level"],
  "manual_fields": {
    "school_name": "Example High School",
    "class_name": "Grade 10 - Class 3"
  }
}
```

### Response Example

```json
{
  "session_id": "20260708-100000-abcd",
  "message": "Report updated",
  "report": "# Classroom Evaluation Report\n..."
}
```

Notes:
- Reprojects cached fields onto the template quickly and deterministically.
- Does not regenerate AI text. To recompute content, call `/report/generate`.
- Expected use case: user toggled checkboxes or edited manual fields after a report already exists.

---

## Recommended Call Sequence

1. Call `GET /features` and verify `report` is present in the returned feature list.
2. Call `GET /report/template-fields` to load the field catalog.
3. Collect `selected_fields` and `manual_fields` from UI.
4. Optionally upload mindmap image via `POST /report/{session_id}/mindmap-image`.
5. Call `POST /report/generate` for streaming report generation.
6. Call `GET /report/{session_id}` to read markdown content.
7. Download document via `GET /report/{session_id}/download?format=docx|pdf`.

---

## Quick Error Code Reference

- `400`: Empty upload file (`mindmap-image`).
- `404`: Session report not found.
- `404`: Mindmap image not found for session.
- `503`: Report feature disabled or unavailable.
- `500`: Server-side save/convert failure.
- `501`: PDF export unavailable (`soffice` not installed).
