# Grading Service API

- **Base URL:** `http://127.0.0.1:9012/api/v1`
- **Content-Type:** `application/json` (except `POST /rubrics/upload` which is `multipart/form-data`)
- **Docs:** `/docs` (Swagger), `/redoc`

---

## Concepts

A task is created by `POST /grading/tasks`. `paper_path` may be a single PDF or a directory. Directory tasks grade each student paper serially, pick up new files as they appear, and auto-complete after `idle_timeout` seconds with no new arrivals. A `.grading.lock` file prevents duplicate submissions of the same directory.

**Status flow:** `PENDING → RUNNING → COMPLETED | FAILED`. Control actions add `PAUSING`, `PAUSED`, `CANCELLING`, `CANCELLED`.

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Service liveness |
| GET | `/rubrics` | List rubric files |
| POST | `/rubrics/upload` | Upload a rubric file |
| GET | `/rubrics/{filename}/content` | Read rubric content |
| PUT | `/rubrics/{filename}/content` | Update rubric content |
| GET | `/grading/config` | Read config |
| PUT | `/grading/config` | Update config |
| GET | `/fs/list` | Browse server filesystem |
| POST | `/grading/tasks` | Create a task |
| GET | `/grading/tasks` | List tasks |
| GET | `/grading/tasks/{id}` | Get task status |
| GET | `/grading/tasks/{id}/summary` | Score summary (live) |
| GET | `/grading/tasks/{id}/students/{slot}/result` | Full per-student `grading_result.json` |
| GET | `/grading/tasks/{id}/log` | Tail task log |
| DELETE | `/grading/tasks/{id}` | Delete task and outputs |
| POST | `/grading/tasks/{id}/pause` | Pause task |
| POST | `/grading/tasks/{id}/resume` | Resume task |
| POST | `/grading/tasks/{id}/cancel` | Cancel task |

---

### GET `/health`

```json
{ "status": "ok", "service": "grading", "language": "en",
  "dependencies": { "vlm": "healthy", "layout_detection": "healthy" } }
```

---

### GET `/rubrics`

```json
{ "total": 1, "rubrics": [{ "filename": "math.txt", "rubric_path": "...", "size_bytes": 2048, "modified_at": "..." }] }
```

---

### POST `/rubrics/upload`

`multipart/form-data`, field `file`. Accepts `.txt` and `.json`.

```bash
curl -X POST http://127.0.0.1:9012/api/v1/rubrics/upload -F "file=@math.txt"
```

```json
{ "status": "ok", "filename": "math.txt", "rubric_path": "...", "size_bytes": 2048 }
```

Errors: `400` (empty / unsupported extension / invalid JSON), `500`.

---

### GET `/rubrics/{filename}/content`

```json
{ "filename": "math.txt", "content": "..." }
```

Errors: `404`, `500`.

---

### PUT `/rubrics/{filename}/content`

Body: `{ "content": "..." }` → `{ "filename": "math.txt", "size_bytes": 2100 }`

Errors: `400`, `404`, `500`.

---

### GET `/grading/config`

Returns the UI-editable config subset plus the read-only model names resolved from the smart-classroom config.

```json
{
  "dpi": 50, "page_columns": 1, "column_split_ratio": 0.55,
  "contrast_enhance": true, "contrast_factor": 1.5,
  "max_tokens": 4096, "vlm_temperature": 0.2, "max_image_pixels": 4000000,
  "poll_interval": 5, "stable_checks": 2, "idle_timeout": 100,
  "min_score": 0.5, "sort_boxes": true, "expand_margin": 10,
  "merge_overlapping": false, "iou_threshold": 0.7,
  "vlm_model": "Qwen/Qwen3.5-9B", "ocr_model": "...", "layout_model": "..."
}
```

`vlm_model` / `ocr_model` / `layout_model` are read-only (resolved from the smart-classroom config, not writable through this endpoint).

---

### PUT `/grading/config`

All fields optional. Changes apply to the next task only. The three model-name fields are read-only and ignored if sent.

| Field | Type | Description |
|---|---|---|
| `dpi` | integer | PDF render DPI |
| `page_columns` | integer | Page layout: `1` single column, `2` two columns (left/right) |
| `column_split_ratio` | float | For `page_columns=2`, left-column width fraction (`0.5` = middle) |
| `contrast_enhance` | bool | Apply contrast enhancement to rendered pages |
| `contrast_factor` | float | Contrast multiplier when `contrast_enhance` is on |
| `max_tokens` | integer | Max completion tokens per VLM request |
| `vlm_temperature` | float | VLM temperature (0–2) |
| `max_image_pixels` | integer | Section images larger than this are downscaled before the VLM call |
| `poll_interval` | integer | Directory scan interval (s) |
| `stable_checks` | integer | Polls before a PDF is considered stable |
| `idle_timeout` | integer | Idle seconds before directory task auto-completes |
| `min_score` | float | Min layout-detection confidence to keep a box (0–1) |
| `sort_boxes` | bool | Sort detected boxes top-to-bottom |
| `expand_margin` | integer | Expand each kept box by this many px |
| `merge_overlapping` | bool | Merge overlapping boxes |
| `iou_threshold` | float | IoU cutoff for merging — only applied when `merge_overlapping` is true |

Returns the updated config. Errors: `400`, `500`.

---

### GET `/fs/list`

Browses the server filesystem. Used by the browser UI to select `paper_path` — browsers cannot read host absolute paths directly; Electron uses the native file picker instead.

| Param | Default | Description |
|---|---|---|
| `path` | — | Absolute path to list; omit for drive roots (Windows) or `/` (Unix) |

```json
{ "path": "C:\\papers", "parent": "C:\\", "entries": [
  { "name": "student1", "path": "C:\\papers\\student1", "is_dir": true }
]}
```

Errors: `400`, `500`.

---

### POST `/grading/tasks`

| Field | Required | Description |
|---|---|---|
| `paper_path` | yes | Absolute path to a PDF or directory |
| `rubric_path` | yes | Absolute path to the rubric file |

```bash
curl -X POST http://127.0.0.1:9012/api/v1/grading/tasks \
  -H "Content-Type: application/json" \
  -d '{"paper_path":"/papers","rubric_path":"/rubrics/math.txt"}'
```

```json
{ "task_id": "506797cd-...", "status": "PENDING", "progress": 0, "created_at": "..." }
```

Errors: `400` (invalid paths, directory already active), `500`.

---

### GET `/grading/tasks`

| Param | Description |
|---|---|
| `status` | Filter by status (e.g. `RUNNING`). Omit for all. |

`status_counts` always spans the full task set regardless of filter.

```json
{ "total": 2, "status_counts": { "COMPLETED": 1, "RUNNING": 1 }, "tasks": [...] }
```

---

### GET `/grading/tasks/{id}`

Returns a single task object (same shape as items in the list). Poll to track progress.

Errors: `404`.

---

### GET `/grading/tasks/{id}/summary`

Live score summary. Readable at any time — does not require `COMPLETED`. Returns an empty shell before any student finishes.

```json
{
  "metadata": { "task_id": "...", "paper_title": "Exam 2025", "subject": "Math" },
  "students": {
    "1": {
      "student_id": "student1", "student_name": "Alice",
      "total_score": 70, "total_max": 102,
      "objective_score": 50, "subjective_score": 20,
      "result_path": "outputs/<task_id>/student1/grading_result.json",
      "questions": { "1": { "catalog": "objective", "type": "choice", "score": 4, "max_score": 4 } }
    }
  },
  "updated_at": "...", "student_count": 1
}
```

The map key (`"1"` above) is the student **slot** — pass it to the student-result endpoint below. `result_path` is the absolute path stored so a table row can be traced back to its `grading_result.json`.

Errors: `400` (invalid id), `500`. Never `404`.

---

### GET `/grading/tasks/{id}/students/{slot}/result`

Returns the full `grading_result.json` for one student. `slot` is the key from the summary `students` map. Resolves the file via the `result_path` recorded in `summary.json` and guards against paths outside the task output directory.

```json
{
  "summary": { "total_score": 70, "total_max": 102, "objective_score": 50, "subjective_score": 20 },
  "questions": { "1": { "catalog": "objective", "type": "choice", "student_answer": "A", "vlm_score": 4, "max_score": 4 } },
  "graded_count": 22,
  "paper_meta": { "paper_title": "Exam 2025", "subject": "Math" },
  "student_meta": { "student_name": "Alice", "exam_number": "20250101" }
}
```

Errors: `404` (task/slot/result not found, or `result_path` missing/outside task dir), `500`.

---

### GET `/grading/tasks/{id}/log`

| Param | Default | Description |
|---|---|---|
| `tail` | 50 | Lines to return (1–5000) |

```json
{ "task_id": "...", "log_path": "...", "lines": ["[...] step render started"] }
```

Errors: `404`, `500`.

---

### DELETE `/grading/tasks/{id}`

Deletes the job record, `outputs/<id>/`, and log file. Force-cancels active tasks first. Removes `.grading.lock` from the papers directory.

**204** — no body. Errors: `404`, `500`.

---

### POST `/grading/tasks/{id}/pause`

Signals the worker to stop at its next checkpoint. Returns immediately with `status: PAUSING`.

Allowed from: `RUNNING`, `PENDING`. Errors: `404`, `409`.

---

### POST `/grading/tasks/{id}/resume`

Spawns a new worker continuing from where the task left off.

Allowed from: `PAUSED`. Errors: `404`, `409`.

---

### POST `/grading/tasks/{id}/cancel`

Stops the worker at its next checkpoint. Status becomes `CANCELLING` until the current VLM call returns, then `CANCELLED`.

Allowed from: `RUNNING`, `PAUSING`, `PAUSED`, `PENDING`. Errors: `404`, `409`.

---

## Output Files

| File | Path |
|---|---|
| Per-student result | `outputs/<task_id>/<student_id>/grading_result.json` |
| Task summary | `outputs/<task_id>/summary.json` |

**`grading_result.json`**

```json
{
  "summary": { "total_score": 70, "total_max": 102, "objective_score": 50, "subjective_score": 20 },
  "questions": {
    "1": { "catalog": "objective", "type": "choice", "student_answer": "A", "vlm_score": 4, "max_score": 4 }
  },
  "graded_count": 22,
  "paper_meta": { "paper_title": "Exam 2025", "subject": "Math" },
  "student_meta": { "student_name": "Alice", "exam_number": "20250101" }
}
```

- `catalog`: `objective` | `subjective`
- `type`: `choice` | `blank` | `calculation`

---

