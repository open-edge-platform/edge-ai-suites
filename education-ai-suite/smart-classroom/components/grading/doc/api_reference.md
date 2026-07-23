# Grading Service — API Reference

VLM-based exam grading service.

- **Base URL:** `http://<host>:<port>/api/v1`
- **Default host/port:** `127.0.0.1:9012` (from root `config.yaml` → `grading.host_addr` / `grading.port`)
- **Content type:** `application/json` (except `POST /rubrics/upload`, which is `multipart/form-data`)
- **Interactive docs:** `/docs` (Swagger UI), `/redoc`, `/openapi.json`

---

## Concepts

**Task.** One `POST /grading/tasks` creates one task (a persisted job). `paper_path` may be:

- **a single PDF** → the task grades that one paper.
- **a directory** → the task maintains a table of work items (one per student subfolder or per PDF directly under it), grades them one at a time, refreshes the table to pick up newly added papers, and completes once all are done and the directory has been idle for `idle_timeout` seconds.

A single worker runs a task; there is never more than one worker per task. A directory task is protected by a `.grading.lock` file written into `papers_dir` for its entire lifetime — submitting the same directory while a task is active returns `400`.

**Lifecycle / status values.** `PENDING → RUNNING → COMPLETED` (or `FAILED`). Control actions add `PAUSING`, `PAUSED`, `CANCELLING`, `CANCELLED`.

- **pause** — the worker stops at its next checkpoint and exits; state is persisted.
- **resume** — spawns a fresh worker that continues from the persisted item table. A paper interrupted mid-way is re-graded whole. A directory task skips items already `completed`.
- **cancel** — the worker stops at its next checkpoint and the task ends as `CANCELLED`. Note: the worker only checks the cancel signal at checkpoints; if a VLM call is in flight the status stays `CANCELLING` until that call returns.

**Progress** is an integer `0–100`; `current_step` names the stage (`render`, `layout_detection`, `section_split`, `vlm_grading`, `merge`, or a directory-task step such as `grading:<student>`, `waiting`, `idle`, `completed`).

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET    | `/health` | Liveness / service info |
| GET    | `/rubrics` | List all rubric files |
| POST   | `/rubrics/upload` | Upload a rubric file |
| GET    | `/rubrics/{filename}/content` | Read a rubric file's text content |
| PUT    | `/rubrics/{filename}/content` | Overwrite a rubric file's text content |
| GET    | `/grading/config` | Read editable config fields |
| PUT    | `/grading/config` | Update editable config fields (takes effect on the next task) |
| GET    | `/fs/list` | Browse server-side directories |
| POST   | `/grading/tasks` | Create a grading task (single paper or directory) |
| GET    | `/grading/tasks` | List all tasks (optionally filtered by status) |
| GET    | `/grading/tasks/{task_id}/summary` | Per-task score summary, readable at any time |
| GET    | `/grading/tasks/{task_id}` | Task status |
| GET    | `/grading/tasks/{task_id}/log` | Tail the task log |
| DELETE | `/grading/tasks/{task_id}` | Delete a task and all its output files |
| POST   | `/grading/tasks/{task_id}/pause` | Request pause |
| POST   | `/grading/tasks/{task_id}/resume` | Resume a paused task |
| POST   | `/grading/tasks/{task_id}/cancel` | Cancel a task |

---

### GET `/health`

Returns service liveness and configured language.

**200 Response**
```json
{ "status": "ok", "service": "grading", "language": "en" }
```

---

### GET `/rubrics`

List every `.txt` / `.json` file under the component `rubrics/` directory, newest first (by file mtime).

**200 Response**
```json
{
  "total": 2,
  "rubrics": [
    {
      "filename": "math_rubrics.txt",
      "rubric_path": ".../components/grading/rubrics/math_rubrics.txt",
      "size_bytes": 2048,
      "modified_at": "2026-07-22T05:16:20+00:00"
    }
  ]
}
```

---

### POST `/rubrics/upload`

Upload a grading prompt (`.txt`) or rubric (`.json`). `.json` content is validated. The file is saved under `rubrics/`; the returned `rubric_path` can be passed to `POST /grading/tasks`.

**Request:** `multipart/form-data` with a single field `file`.

```bash
curl -X POST http://127.0.0.1:9012/api/v1/rubrics/upload \
  -F "file=@math_rubrics.txt"
```

**200 Response**
```json
{
  "status": "ok",
  "filename": "math_rubrics.txt",
  "rubric_path": ".../components/grading/rubrics/math_rubrics.txt",
  "size_bytes": 2048
}
```

**Errors:** `400` (empty file, missing filename, unsupported extension, invalid JSON); `500`.

---

### GET `/rubrics/{filename}/content`

Read the full text content of an existing rubric file.

```bash
curl http://127.0.0.1:9012/api/v1/rubrics/math_rubrics.txt/content
```

**200 Response**
```json
{ "filename": "math_rubrics.txt", "content": "..." }
```

**Errors:** `404` (file not found); `500`.

---

### PUT `/rubrics/{filename}/content`

Overwrite an existing rubric file's text content in place.

**Request body**
```json
{ "content": "updated rubric text..." }
```

**200 Response**
```json
{ "filename": "math_rubrics.txt", "size_bytes": 2100 }
```

**Errors:** `404` (file not found); `400` (invalid request); `500`.

---

### GET `/grading/config`

Return the currently active values of the editable config fields (read from `config.yaml` on each call).

**200 Response**
```json
{
  "dpi": 50,
  "vlm_temperature": 0.1,
  "poll_interval": 5,
  "stable_checks": 2,
  "idle_timeout": 180
}
```

---

### PUT `/grading/config`

Update one or more config fields. Only the provided fields are changed; omitted fields are left as-is. Changes are written to `config.yaml` and take effect on the **next** task created (running tasks are not affected).

**Request body** (all fields optional)

| Field | Type | Description |
|---|---|---|
| `dpi` | integer | PDF render resolution sent to the VLM |
| `vlm_temperature` | float | VLM sampling temperature (0–2) |
| `poll_interval` | integer | Seconds between directory scans (directory tasks) |
| `stable_checks` | integer | Consecutive unchanged polls before a PDF is considered stable |
| `idle_timeout` | integer | Seconds without a new item before a directory task auto-completes |

**200 Response** — same shape as `GET /grading/config`, reflecting the updated values.

**Errors:** `400` (invalid value); `500`.

---

### GET `/fs/list`

Browse the server's local file system for directory selection.

**Background.** Grading tasks require a server-side absolute path for `paper_path`. In a browser context the Web API has no mechanism to expose the host machine's directory tree — `<input type="file">` only yields file contents, never an absolute path. This endpoint fills that gap by letting the browser navigate the server's file system through HTTP requests, so the user can pick a directory interactively without typing a raw path.

In Electron mode the native OS file-picker dialog (`dialog.showOpenDialog`) provides the absolute path directly and this endpoint is not needed. The endpoint exists specifically to maintain feature parity between browser and Electron deployments.

**Query parameters**

| Param | Type | Description |
|---|---|---|
| `path` | string \| null | Absolute path to list. Omitted → drive list on Windows, `/` on Unix |

**200 Response**
```json
{
  "path": "C:\\Users\\user\\papers",
  "parent": "C:\\Users\\user",
  "entries": [
    { "name": "student1", "path": "C:\\Users\\user\\papers\\student1", "is_dir": true },
    { "name": "exam.pdf", "path": "C:\\Users\\user\\papers\\exam.pdf", "is_dir": false }
  ]
}
```

**Errors:** `400` (invalid path); `500`.

---

### POST `/grading/tasks`

Create a grading task. `rubric_path` is required — there is no server-side default fallback.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `paper_path` | string | yes | Absolute path to a PDF **or** a directory of papers |
| `rubric_path` | string | yes | Absolute path to the grading prompt file |

```bash
# Single paper
curl -X POST http://127.0.0.1:9012/api/v1/grading/tasks \
  -H "Content-Type: application/json" \
  -d '{"paper_path":"C:/.../student1/exam.pdf","rubric_path":"C:/.../rubrics/math_rubrics.txt"}'

# Directory of papers
curl -X POST http://127.0.0.1:9012/api/v1/grading/tasks \
  -H "Content-Type: application/json" \
  -d '{"paper_path":"C:/.../papers","rubric_path":"C:/.../rubrics/math_rubrics.txt"}'
```

**200 Response**
```json
{
  "task_id": "506797cd-4a4d-4147-99b1-7d7a4f39d2f8",
  "task_type": "grading.run",
  "status": "PENDING",
  "current_step": "created",
  "progress": 0,
  "created_at": "2026-07-22T06:07:39+00:00",
  "log_path": ".../outputs/jobs/logs/grading_run_<task_id>.log"
}
```

**Errors:** `400` (missing/invalid `paper_path` or `rubric_path`; directory already has an active task); `500`.

---

### GET `/grading/tasks`

List all tasks, newest first. `status_counts` always reflects the **full** task set regardless of any filter.

**Query parameters**

| Param | Type | Description |
|---|---|---|
| `status` | string \| null | Case-insensitive filter, e.g. `RUNNING`, `PAUSED`. Omitted → all tasks |

**200 Response**
```json
{
  "total": 3,
  "status_counts": { "COMPLETED": 2, "RUNNING": 1 },
  "tasks": [
    {
      "task_id": "506797cd-...",
      "task_type": "grading.run",
      "status": "RUNNING",
      "current_step": "grading:student2",
      "progress": 63,
      "error_message": null,
      "created_at": "2026-07-22T06:07:39+00:00",
      "updated_at": "2026-07-22T06:09:14+00:00",
      "log_path": "...",
      "dir_info": {
        "papers_dir": "C:/.../papers",
        "dir_name": "papers",
        "rubric_path": "C:/.../rubrics/math_rubrics.txt",
        "rubric_name": "math_rubrics.txt",
        "total": 3,
        "completed": 1,
        "failed": 0,
        "pending": 2,
        "current": "student2",
        "last_new_item_at": "2026-07-22T06:07:40+00:00"
      }
    }
  ]
}
```

`dir_info` is `null` for single-paper tasks.

---

### GET `/grading/tasks/{task_id}/summary`

Return `outputs/<task_id>/summary.json`. Readable at any time — does not require `COMPLETED`. Seeded empty at task creation; rows appear as each student finishes.

**200 Response**
```json
{
  "metadata": {
    "task_id": "506797cd-...",
    "prompt_path": ".../rubrics/math_rubrics.txt",
    "paper_title": "2025年上海市初中学业水平考试",
    "subject": "数学"
  },
  "students": {
    "1": {
      "student_id": "student1",
      "student_name": "张伟",
      "class_name": "初三(2)班",
      "exam_number": "2025010801",
      "paper_path": "...",
      "total_score": 70, "total_max": 102,
      "objective_score": 50, "objective_max": 60,
      "subjective_score": 20, "subjective_max": 42,
      "questions": {
        "1":  { "catalog": "objective",  "type": "choice",      "score": 4,  "max_score": 4  },
        "19": { "catalog": "subjective", "type": "calculation", "score": 10, "max_score": 10 }
      }
    }
  },
  "updated_at": "2026-07-22T06:10:34+00:00",
  "student_count": 1
}
```

**Errors:** `400` (invalid `task_id`); `500`. Never `404`.

---

### GET `/grading/tasks/{task_id}`

Current task status. Poll this to track progress.

**200 Response** — same shape as a task object in `GET /grading/tasks`.

**Errors:** `404` (task not found).

---

### GET `/grading/tasks/{task_id}/log`

Return the last N lines of the task's log file.

**Query parameters**

| Param | Type | Default | Description |
|---|---|---|---|
| `tail` | integer | 50 | Number of lines to return (clamped to 1–5000) |

**200 Response**
```json
{
  "task_id": "506797cd-...",
  "log_path": ".../outputs/jobs/logs/grading_run_<task_id>.log",
  "lines": [
    "[2026-07-22T06:07:39+00:00] directory task created papers_dir=C:/.../papers",
    "[2026-07-22T06:07:40+00:00] step render started"
  ]
}
```

**Errors:** `404` (task not found); `500`.

---

### DELETE `/grading/tasks/{task_id}`

Delete a task and all associated data: job record, `outputs/<task_id>/` directory, and log file. If the task is active (PENDING / RUNNING / PAUSED / PAUSING), it is force-cancelled before deletion. The `.grading.lock` file in the papers directory is also removed.

```bash
curl -X DELETE http://127.0.0.1:9012/api/v1/grading/tasks/506797cd-...
```

**204 Response** — no body.

**Errors:** `404` (task not found); `500`.

---

### POST `/grading/tasks/{task_id}/pause`

Request a pause. Returns immediately with `status: PAUSING`; the worker reaches `PAUSED` at its next checkpoint.

**200 Response** (`GradingTaskControlResponse`)
```json
{
  "task_id": "506797cd-...",
  "task_type": "grading.run",
  "status": "PAUSING",
  "current_step": "pause_requested",
  "progress": 63,
  "control_action": "pause",
  "updated_at": "2026-07-22T06:08:00+00:00",
  "log_path": "..."
}
```

Allowed from `RUNNING` / `PENDING`. **Errors:** `404`; `409`.

---

### POST `/grading/tasks/{task_id}/resume`

Resume a paused task. Spawns one fresh worker continuing from the persisted item table.

**200 Response** — same `GradingTaskControlResponse` shape; `status: RUNNING`.

Allowed only from `PAUSED`. **Errors:** `404`; `409`.

---

### POST `/grading/tasks/{task_id}/cancel`

Cancel a task. The worker stops at its next checkpoint and the task ends as `CANCELLED`. If a VLM call is in flight, the status stays `CANCELLING` until that call returns.

**200 Response** — `GradingTaskControlResponse`; `status: CANCELLING`.

Allowed from `RUNNING` / `PAUSING` / `PAUSED` / `PENDING`. **Errors:** `404`; `409`.

---

## Output files

Written under `outputs/<task_id>/`.

### `grading_result.json` (per student)

`outputs/<task_id>/<student_id>/grading_result.json`

```json
{
  "summary": {
    "objective_score": 50, "objective_max": 60,
    "subjective_score": 20, "subjective_max": 42,
    "total_score": 70,     "total_max": 102
  },
  "questions": {
    "1":  { "catalog": "objective",  "type": "choice",      "student_answer": "A", "vlm_score": 4,  "max_score": 4 },
    "19": { "catalog": "subjective", "type": "calculation", "student_answer": "5", "vlm_score": 10, "max_score": 10 }
  },
  "graded_count": 22,
  "task_id": "506797cd-...",
  "paper_meta":   { "paper_title": "2025年上海市初中学业水平考试", "subject": "数学" },
  "student_meta": { "student_name": "张伟", "class_name": "初三(2)班", "exam_number": "2025010801" },
  "input": { "paper_path": "...", "prompt_path": "...", "student_id": "student1" }
}
```

- `catalog`: `objective` | `subjective`
- `type`: `choice` | `blank` | `calculation`
- `paper_meta` / `student_meta` come from VLM header extraction driven by the rubric's `【卷头信息】` block. Missing fields degrade to `null`.

### `summary.json` (per task)

`outputs/<task_id>/summary.json` — seeded empty at task creation, rebuilt each time a student finishes. See `GET /grading/tasks/{task_id}/summary` for the full schema.

---

## Typical flows

**Grade a directory, watch to completion**
```bash
TASK=$(curl -s -X POST http://127.0.0.1:9012/api/v1/grading/tasks \
  -H "Content-Type: application/json" \
  -d '{"paper_path":"C:/.../papers","rubric_path":"C:/.../rubrics/math_rubrics.txt"}' \
  | jq -r .task_id)

# poll until COMPLETED
curl -s http://127.0.0.1:9012/api/v1/grading/tasks/$TASK | jq '{status,current_step,progress}'

# watch per-student scores appear in real time
curl -s http://127.0.0.1:9012/api/v1/grading/tasks/$TASK/summary | jq '{student_count,students}'

# tail the log
curl -s "http://127.0.0.1:9012/api/v1/grading/tasks/$TASK/log?tail=20" | jq -r '.lines[]'
```

**Pause then resume**
```bash
curl -X POST http://127.0.0.1:9012/api/v1/grading/tasks/$TASK/pause
# wait until status == PAUSED
curl -s http://127.0.0.1:9012/api/v1/grading/tasks/$TASK | jq -r .status
curl -X POST http://127.0.0.1:9012/api/v1/grading/tasks/$TASK/resume
```

**Delete a task**
```bash
curl -X DELETE http://127.0.0.1:9012/api/v1/grading/tasks/$TASK
```
