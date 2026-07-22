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

A single worker runs a task; there is never more than one worker per task.

**Lifecycle / status values.** `PENDING → RUNNING → COMPLETED` (or `FAILED`). Control actions add `PAUSING`, `PAUSED`, `CANCELLING`, `CANCELLED`.

- **pause** — the worker stops at its next checkpoint (between render / detection / section-split / each section) and exits; the process keeps running. State is persisted, so nothing is lost.
- **resume** — spawns a fresh worker that continues from the persisted item table. A paper interrupted mid-way is re-graded whole (there is no per-section resume). A directory task skips items already `completed`.
- **cancel** — the worker stops at its next checkpoint and the task ends as `CANCELLED`.

**Progress** is an integer `0–100`; `current_step` names the stage (`render`, `layout_detection`, `section_split`, `vlm_grading`, `merge`, or a directory-task step such as `grading:<student>`, `waiting`, `idle`, `completed`).

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | Liveness / service info |
| GET  | `/rubrics` | List all rubric / grading-prompt files |
| POST | `/rubrics/upload` | Upload a rubric / grading-prompt file |
| POST | `/grading/tasks` | Create a grading task (single paper or directory) |
| GET  | `/grading/tasks` | List all tasks (optionally filtered by status) |
| GET  | `/grading/tasks/{task_id}` | Task status |
| GET  | `/grading/tasks/{task_id}/result` | Task result (only when `COMPLETED`) |
| POST | `/grading/tasks/{task_id}/pause` | Request pause |
| POST | `/grading/tasks/{task_id}/resume` | Resume a paused task |
| POST | `/grading/tasks/{task_id}/cancel` | Cancel a task |

---

### GET `/health`

Returns service liveness and configured language.

**200 Response**
```json
{ "status": "ok", "service": "grading", "language": "en" }
```

---

### GET `/rubrics`

List every `.txt` / `.json` file under the component `rubrics/` directory, newest first (by file mtime). Any listed `rubric_path` can be passed to `POST /grading/tasks`.

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
    },
    {
      "filename": "yuwen_rubrics.txt",
      "rubric_path": ".../components/grading/rubrics/yuwen_rubrics.txt",
      "size_bytes": 5243,
      "modified_at": "2026-07-21T09:02:11+00:00"
    }
  ]
}
```

---

### POST `/rubrics/upload`

Upload a grading prompt (`.txt`) or rubric (`.json`). `.json` content is validated. The file is saved under the component `rubrics/` directory; the returned `rubric_path` can be passed to `POST /grading/tasks`.

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

**Errors:** `400` (empty file, missing filename, unsupported extension, invalid JSON); `500` (unexpected).

---

### POST `/grading/tasks`

Create a grading task. `dpi`, generation params, and `force_regrade` come from the component `config.yaml` — the request body is intentionally minimal.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `paper_path` | string | yes | Absolute path to a PDF **or** a directory of papers |
| `rubric_path` | string \| null | no | Grading prompt path; omitted → config `grading.default_prompt_path` |
| `exam_id` | string \| null | no | Groups output under `outputs/<exam_id>/`; directory tasks default it to the directory name |

`student_id` is not accepted — it is derived from the paper path (a subfolder name, or a single PDF's parent folder name).

```bash
# Single paper
curl -X POST http://127.0.0.1:9012/api/v1/grading/tasks \
  -H "Content-Type: application/json" \
  -d '{"paper_path":"C:/.../papers/student1/2025_sh_zhongkao_math.pdf","exam_id":"math_test"}'

# Directory of papers
curl -X POST http://127.0.0.1:9012/api/v1/grading/tasks \
  -H "Content-Type: application/json" \
  -d '{"paper_path":"C:/.../papers","exam_id":"math_test_multi","rubric_path":"C:/.../rubrics/math_rubrics.txt"}'
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

If an active task already exists for the same paper and `force_regrade` is off, the existing task is returned instead of a new one.

**Errors:** `400` (missing/invalid `paper_path`); `500` (unexpected).

---

### GET `/grading/tasks`

List all tasks, newest first (by `created_at`). `status_counts` always reflects the **full** task set (it is not affected by the filter). Use it to see how many tasks sit in each state.

**Query parameters**

| Param | Type | Description |
|---|---|---|
| `status` | string \| null | Case-insensitive filter, e.g. `RUNNING`, `PAUSED`, `COMPLETED`. Omitted → all tasks |

```bash
curl -s "http://127.0.0.1:9012/api/v1/grading/tasks"
curl -s "http://127.0.0.1:9012/api/v1/grading/tasks?status=PAUSED"
```

**200 Response**
```json
{
  "total": 3,
  "status_counts": { "COMPLETED": 1, "RUNNING": 1, "PAUSED": 1 },
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
      "log_path": "..."
    }
  ]
}
```

When `status` is supplied, `total` and `tasks` cover only the matching subset; `status_counts` still spans everything.

---

### GET `/grading/tasks/{task_id}`

Current task status. Poll this to track progress.

**200 Response**
```json
{
  "task_id": "506797cd-4a4d-4147-99b1-7d7a4f39d2f8",
  "task_type": "grading.run",
  "status": "RUNNING",
  "current_step": "grading:student2",
  "progress": 63,
  "error_message": null,
  "created_at": "2026-07-22T06:07:39+00:00",
  "updated_at": "2026-07-22T06:09:14+00:00",
  "log_path": ".../outputs/jobs/logs/grading_run_<task_id>.log"
}
```

**Errors:** `404` (task not found).

---

### GET `/grading/tasks/{task_id}/result`

The task result. Available only when `status == "COMPLETED"`; otherwise `409`.

**200 Response — single-paper task**

`result.result_path` points at `grading_result.json`; `result.summary` is the score summary.

```json
{
  "task_id": "506797cd-...",
  "task_type": "grading.run",
  "status": "COMPLETED",
  "result": {
    "result_path": ".../outputs/math_test/student1/grading_result.json",
    "summary": {
      "objective_score": 50, "objective_max": 60,
      "subjective_score": 20, "subjective_max": 42,
      "total_score": 70,     "total_max": 102
    },
    "log_path": ".../outputs/jobs/logs/grading_run_<task_id>.log"
  },
  "log_path": ".../outputs/jobs/logs/grading_run_<task_id>.log"
}
```

**200 Response — directory task**

`result` carries item counts; the per-student breakdown lives in `outputs/<exam_id>/summary.json` (see below).

```json
{
  "task_id": "506797cd-...",
  "task_type": "grading.run",
  "status": "COMPLETED",
  "result": { "total": 3, "completed": 3, "failed": 0, "log_path": "..." },
  "log_path": "..."
}
```

**Errors:** `404` (not found); `409` (not completed yet); `500` (result missing).

---

### POST `/grading/tasks/{task_id}/pause`

Request a pause. Returns immediately with `status: PAUSING`; the worker reaches `PAUSED` at its next checkpoint. Poll `GET /grading/tasks/{task_id}` until `status == "PAUSED"` before calling resume.

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

Allowed from `RUNNING` / `PENDING` (and idempotent from `PAUSING` / `PAUSED`). **Errors:** `404`; `409` (not pausable in the current state).

---

### POST `/grading/tasks/{task_id}/resume`

Resume a paused task. Spawns exactly one fresh worker that continues from the persisted item table. A paper interrupted mid-way is re-graded whole; a directory task skips items already `completed`.

**200 Response** — same `GradingTaskControlResponse` shape; `status: RUNNING`.

Allowed only from `PAUSED`. From `RUNNING` it is a no-op (returns current state). **Errors:** `404`; `409` (`PAUSING` — retry after it reaches `PAUSED`, or any other non-resumable state).

---

### POST `/grading/tasks/{task_id}/cancel`

Cancel a task; the worker stops at its next checkpoint and the task ends as `CANCELLED`.

**200 Response** — `GradingTaskControlResponse`; `status: CANCELLING`.

Allowed from `RUNNING` / `PAUSING` / `PAUSED` / `PENDING` (idempotent once terminal or `CANCELLING`). **Errors:** `404`; `409`.

---

## Output files

Written under `outputs/<exam_id>/`.

### `grading_result.json` (per student)

`outputs/<exam_id>/<student_id>/grading_result.json`

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
  "input": { "paper_path": "...", "prompt_path": "...", "student_id": "student1", "exam_id": "math_test_multi" }
}
```

- `catalog`: `objective` | `subjective`
- `type`: `choice` | `blank` | `calculation`
- `paper_meta` / `student_meta` come from **header extraction** — a VLM read of page 1 driven by the rubric's `【卷头信息】` block. Missing fields degrade to `null` and never block grading.

### `summary.json` (per exam, directory tasks)

`outputs/<exam_id>/summary.json` — rebuilt each time a student finishes. Students are keyed by a sequential index; per-question records are collapsed to one line and use `score` (not `vlm_score`), without `student_answer`.

```json
{
  "metadata": {
    "exam_id": "math_test_multi",
    "prompt_path": "...",
    "paper_title": "2025年上海市初中学业水平考试",
    "subject": "数学试卷"
  },
  "students": {
    "1": {
      "student_id": "student1",
      "student_name": "张伟", "class_name": "初三(2)班", "exam_number": "2025010801",
      "paper_path": "...",
      "total_score": 70, "total_max": 102,
      "objective_score": 50, "objective_max": 60,
      "subjective_score": 20, "subjective_max": 42,
      "questions": {
        "1": {"catalog": "objective", "type": "choice", "score": 4, "max_score": 4},
        "19": {"catalog": "subjective", "type": "calculation", "score": 10, "max_score": 10}
      }
    }
  },
  "updated_at": "2026-07-22T06:10:34+00:00",
  "student_count": 3
}
```

---

## Typical flows

**Grade a directory, watch to completion**
```bash
TASK=$(curl -s -X POST http://127.0.0.1:9012/api/v1/grading/tasks \
  -H "Content-Type: application/json" \
  -d '{"paper_path":"C:/.../papers","exam_id":"math_multi"}' | jq -r .task_id)

# poll until COMPLETED
curl -s http://127.0.0.1:9012/api/v1/grading/tasks/$TASK | jq '{status,current_step,progress}'

# fetch summary counts once done
curl -s http://127.0.0.1:9012/api/v1/grading/tasks/$TASK/result | jq .result
```

**Pause then resume**
```bash
curl -X POST http://127.0.0.1:9012/api/v1/grading/tasks/$TASK/pause
# wait until status == PAUSED
curl -s http://127.0.0.1:9012/api/v1/grading/tasks/$TASK | jq -r .status
curl -X POST http://127.0.0.1:9012/api/v1/grading/tasks/$TASK/resume
```
