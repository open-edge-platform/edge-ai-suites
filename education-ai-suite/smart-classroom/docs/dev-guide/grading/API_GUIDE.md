# Grading API Reference

The grading component exposes a FastAPI service at

```
http://127.0.0.1:9012
```

Every route below is prefixed with `/api/v1`.
---

## Overview

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Service health incl. backend dependencies |
| GET | `/api/v1/grading/config` | Read effective grading config |
| PUT | `/api/v1/grading/config` | Update grading config |
| GET | `/api/v1/fs/list` | List a directory on disk |
| GET | `/api/v1/rubrics` | List rubric files |
| POST | `/api/v1/rubrics/upload` | Upload a rubric file |
| GET | `/api/v1/rubrics/{filename}/content` | Read a rubric's content |
| PUT | `/api/v1/rubrics/{filename}/content` | Update a rubric's content |
| POST | `/api/v1/grading/tasks` | Create a grading task |
| GET | `/api/v1/grading/tasks` | List tasks |
| GET | `/api/v1/grading/tasks/{task_id}` | Get task status |
| GET | `/api/v1/grading/tasks/{task_id}/log` | Read task log |
| GET | `/api/v1/grading/tasks/{task_id}/summary` | Grading summary |
| GET | `/api/v1/grading/tasks/{task_id}/students/{slot}/result` | Per-student result |
| POST | `/api/v1/grading/tasks/{task_id}/pause` | Pause a task |
| POST | `/api/v1/grading/tasks/{task_id}/resume` | Resume a task |
| POST | `/api/v1/grading/tasks/{task_id}/cancel` | Cancel a task |
| DELETE | `/api/v1/grading/tasks/{task_id}` | Delete a task |

## Error conventions

| HTTP status | Meaning |
|---|---|
| `400` | Invalid request / illegal parameter value |
| `404` | Task, rubric, or config resource not found |
| `409` | State conflict (e.g. `pause` on a task that is not running) |
| `500` | Unexpected server-side error |

Error bodies are FastAPI default or `{"detail": "<message>"}`.

---

## GET `/api/v1/health`

Service + dependency health probe.

**Response** — `HealthResponse`

| Field | Type | Description |
|---|---|---|
| `status` | string | `"ok"` |
| `service` | string | `"grading"` |
| `language` | string | Active language (`en` / `zh`) |
| `dependencies` | object | Backend status map |

`dependencies` contains `vlm` and `layout_detection`, each `"healthy" |
"unavailable"`. OCR is local and not probed here.

```json
{
  "status": "ok",
  "service": "grading",
  "language": "zh",
  "dependencies": {
    "vlm": "healthy",
    "layout_detection": "unavailable"
  }
}
```

---

## Config

### GET `/api/v1/grading/config`

Read the effective grading configuration (subset surfaced for the UI).

**Response** — `GradingConfigResponse`: `dpi`, `page_columns`,
`column_split_ratio`, `force_split`, `force_split_pairs`, `contrast_enhance`,
`contrast_factor`, `max_tokens`, `vlm_temperature`, `max_image_pixels`,
`poll_interval`, `stable_checks`, `idle_timeout`, `min_score`, `sort_boxes`,
`expand_margin`, `merge_overlapping`, `iou_threshold`, `vlm_model` (queried
from the VLM service, falls back to `"VLM service"`), `ocr_model`,
`layout_model`. Values are `null` when not configured.

### PUT `/api/v1/grading/config`

Update the runtime grading config. Accepts a partial body of the same fields as
the GET response (excluding the read-only `vlm_model` / `ocr_model` /
`layout_model`). Unset fields keep their current values. Runtime edits persist to
`config.yaml` and take effect on the next task.

**Notes:**

- `force_regrade` and `debug_mode` are not exposed here (live in `config.yaml`).
- `page_columns` accepts `1`, `2`, or `auto`. With `auto` the layout is inferred
  per task from layout detection, and `column_split_ratio` is only used as a
  fallback when inference cannot decide.

---

## File system

### GET `/api/v1/fs/list`

List a directory for picking `paper_path` in the UI.

**Query params:** `path` (optional, defaults to some root).

**Response** — `FsListResponse`

| Field | Type | Description |
|---|---|---|
| `path` | string | The directory listed |
| `parent` | string/null | Parent directory, `null` at root |
| `entries` | array | `{name, path, is_dir}` |

---

## Rubrics

### GET `/api/v1/rubrics`

List rubric files.

**Response** — `RubricListResponse`

| Field | Type | Description |
|---|---|---|
| `total` | int | Number of rubrics |
| `rubrics` | array | `{filename, rubric_path, size_bytes, modified_at}` |

### POST `/api/v1/rubrics/upload`

Upload a rubric file. Multipart form with a single `file` field.

**Response** — `RubricUploadResponse`: `status`, `filename`, `rubric_path`,
`size_bytes`.

### GET `/api/v1/rubrics/{filename}/content`

Read a rubric's content.

**Response** — `RubricContentResponse`: `filename`, `content` (string).

### PUT `/api/v1/rubrics/{filename}/content`

Overwrite a rubric's content.

**Body** — `RubricUpdateRequest`: `content` (string).

**Response** — `RubricUpdateResponse`: `filename`, `size_bytes`.

---

## Tasks

### Create — POST `/api/v1/grading/tasks`

Start an async grading run. `paper_path` must be a **directory** containing one
subfolder per student (not a single PDF). `rubric_path` is required.

**Body** — `GradingTaskCreateRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| `paper_path` | string | yes | Absolute path to the paper directory |
| `rubric_path` | string | yes | Absolute path to the rubric `.txt` file |

> Even though `rubric_path` is declared `None` in the schema, the pipeline
> rejects a missing value, so always pass it.

**Response** — `GradingTaskCreateResponse`: `task_id`, `task_type`
(`"grading.run"`), `status`, `current_step`, `progress`, `created_at`,
`log_path`.

```json
{
  "task_id": "d99aae12-4247-4f55-b303-68961bab249e",
  "task_type": "grading.run",
  "status": "PENDING",
  "current_step": "queued",
  "progress": 0,
  "created_at": "2026-09-07T02:32:48.513622+00:00",
  "log_path": ".../outputs/jobs/logs/grading_run_<task_id>.log"
}
```

### List — GET `/api/v1/grading/tasks`

**Query params:** `status` (optional; filters, e.g. `COMPLETED`).

**Response** — `TaskListResponse`: `total`, `status_counts`
(`{COMPLETED: n, RUNNING: n, ...}`), `tasks` (array of task summaries with
`dir_info`).

### Status — GET `/api/v1/grading/tasks/{task_id}`

**Response** — `GradingTaskStatusResponse`: `task_id`, `task_type`, `status`,
`current_step`, `progress`, `error_message`, `created_at`, `updated_at`,
`log_path`, `dir_info`.

`status` is one of: `PENDING`, `RUNNING`, `PAUSING`, `PAUSED`, `CANCELLING`,
`COMPLETED`, `FAILED`, `CANCELLED`.

### Log — GET `/api/v1/grading/tasks/{task_id}/log`

**Query params:** `tail` (optional, default `50`) — number of trailing lines.

**Response** — `TaskLogResponse`: `task_id`, `log_path`, `lines` (array of
strings).

### Summary — GET `/api/v1/grading/tasks/{task_id}/summary`

Reads the task's `summary.json`.

**Response** — `TaskSummaryJsonResponse`: `metadata` (dict), `students` (dict
keyed by student), `updated_at`, `student_count`.

### Per-student result — GET `/api/v1/grading/tasks/{task_id}/students/{slot}/result`

`slot` is a student slot identifier (e.g. the student directory name).

**Response** — raw JSON of the student's `grading_result.json`.

### Pause — POST `/api/v1/grading/tasks/{task_id}/pause`

Pause a running task.

### Resume — POST `/api/v1/grading/tasks/{task_id}/resume`

Resume a paused task.

### Cancel — POST `/api/v1/grading/tasks/{task_id}/cancel`

Cancel a task.

**Control response** (pause / resume / cancel) — `GradingTaskControlResponse`:
`task_id`, `task_type`, `status`, `current_step`, `progress`,
`control_action`, `updated_at`, `log_path`.

### Delete — DELETE `/api/v1/grading/tasks/{task_id}`

Delete a task (including its stored outputs). Returns `204 No Content`.


