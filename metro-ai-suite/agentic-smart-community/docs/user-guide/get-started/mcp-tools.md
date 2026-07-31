# MCP Tools Guide

This document lists every tool exposed by the `smart-community` (`smartbuilding-video`) MCP
server — its purpose, `action` enum, parameters, and return shape.

Every tool id is prefixed `smartbuilding_`. Every tool is keyed on **`monitor_id`** (the camera
id, e.g. `cam_child`); ids are per-monitor and are never assumed unique across use cases. Times
are ISO-8601 internally — present `HH:MM` / `HH:MM:SS` to users.

The tools fall into four groups:

| Group | Tools |
|---|---|
| **Query & report** | `alert_query` · `scene_query` · `generate_report` · `video_db` |
| **Monitor lifecycle** | `monitor_ctl` · `monitors_compose` |
| **Use-case authoring** | `use_case_validate` · `use_case_register` |
| **Rules & plans** | `plan_ctl` · `rule_eval` |

---

## 1. `smartbuilding_alert_query`

Query or acknowledge alerts. Switch mode via `action`.

Every row in `alerts` is already rule-engine-filtered, so you do **not** re-filter by
severity/type. `severity` / `event` / `desc` are **not stored on the alert** — they live on the
linked task and are returned via a `task_id` JOIN into `video_summary_tasks`.

| Param | Type | Required | Description |
|---|---|---|---|
| `monitor_id` | string | ✅ | Monitor ID |
| `action` | enum | ✅ | See below |
| `limit` | number | — | Max rows (default 20, for `latest`) |
| `start_date` | string | — | `YYYY-MM-DD`, inclusive start (required for `by_date`; optional for `stats`) |
| `end_date` | string | — | `YYYY-MM-DD`, inclusive end. `start_date == end_date` = one day |
| `alert_id` | number | — | Alert to acknowledge (for `ack`) |
| `ack_by` | string | — | Who acknowledged (for `ack`) |

**Actions**

| action | Purpose | Returns |
|---|---|---|
| `latest` | Newest N alerts (`limit`), each LEFT-JOINed with its task + event | `{ alerts: AlertWithTask[] }` |
| `by_date` | Alerts within `start_date` ~ `end_date`, same JOIN shape | `{ alerts: AlertWithTask[] }` |
| `ack` | Acknowledge one alert (`alert_id` + `ack_by`) | `{ success: true, alert_id }` |
| `stats` | Aggregate counts only, optional date range | `{ total, unacked }` |

`AlertWithTask` carries `taskDetails` (including the user-defined extension columns such as
`event` / `severity` / `desc`) and `eventDetails` (motion type, start/end time).

---

## 2. `smartbuilding_scene_query`

One-shot VLM look at the live frame. Reads the monitor's `latest.jpg` and asks
**vllm-serving-ipex** (`:41091`, by default) to describe it now.

| Param | Type | Required | Description |
|---|---|---|---|
| `monitor_id` | string | ✅ | Frame path is `$SMARTBUILDING_DATA_DIR/segments/<monitor_id>/latest.jpg` |
| `prompt` | string | — | Override prompt (default: describe the scene in 1–2 sentences) |
| `vlm_url` | string | — | VLM base URL (default `config.vlmService.url`) |
| `model` | string | — | VLM model id (default `config.vlmService.model`) |
| `max_edge_px` | number | — | Longest-edge cap in px (default `config.vlmService.maxEdgePx`, global 720) |

**Returns** `{ scene }` — the description with `<think>` tags stripped. Use it for any "what is
happening right now?" question, or to ask targeted questions about the current frame via a
custom `prompt` (e.g. "list every food item visible in the fridge"). Resized frames are archived
under `segments/<monitor_id>/queries/<date>/`.

---

## 3. `smartbuilding_generate_report`

Build a period report from the DB: query a data source, build an SRT timeline, call
**multilevel-video-understanding** (`:8192`) in caption-only mode, and write a row to `reports`.

Data source / filter / default type are **derived from `config.yaml`**
`use_case_dict[monitor.use_case].reports`; tool params override the config.

| Param | Type | Required | Description |
|---|---|---|---|
| `monitor_id` | string | ✅ | Monitor ID |
| `type` | enum | — | `daily` \| `weekly` \| `monthly` \| `custom` (default: use-case config, else `daily`) |
| `period_start` | string | — | Inclusive start `YYYY-MM-DD` or `YYYY-MM-DD HH:MM` (for `custom`) |
| `period_end` | string | — | Inclusive end (for `custom`); supports half-day windows, e.g. `06:00`–`12:00` |
| `data_source` | enum | — | `events` \| `alerts` \| `video_summary_tasks` (default: use-case config, else `alerts`) |
| `filter` | object | — | Key-value filter on the data-source columns (incl. user extension columns) |

`daily` = today, `weekly` = last 7 days, `monthly` = last 30 days.

**Returns** `{ periodStart, periodEnd, type, dataSource, eventCount, reportText, latencySeconds }`.
A debug SRT is persisted under `logs/reports/`.

The report is a **two-layer** flow: this tool produces the raw `reportText`; the agent/persona
then decides whether and how to push it (rewrite in the user's voice, lead with the headline).

---

## 4. `smartbuilding_video_db`

Low-level read-only SQL escape hatch against the SQLite DB. **`SELECT` only** — any
`INSERT`/`UPDATE`/`DELETE` is rejected. Use it for anything the typed tools don't cover
(e.g. reading `monitor_state`).

| Param | Type | Required | Description |
|---|---|---|---|
| `query` | string | ✅ | `SELECT` statement (non-SELECT rejected) |
| `params` | array | — | Positional params for `?` placeholders |

**Returns** the result-row array.

---

## 5. `smartbuilding_monitor_ctl`

Single-monitor lifecycle, coordinating all three layers (DB + videostream-analytics +
video-worker) atomically in one call.

For `register_source`, `use_case` must be a key in `config.yaml`'s `use_case_dict`; the tool runs
`smartbuilding_use_case_validate` as a pre-check and **rejects** registration if it fails (no DB
write, no analytics call, no worker start). `video_summary_task` is derived from the use case, not
passed here.

| Param | Type | Required | Description |
|---|---|---|---|
| `action` | enum | ✅ | `list` \| `status` \| `start` \| `stop` \| `register_source` \| `unregister` |
| `monitor_id` | string | — | Required for all except `list` |
| `source_url` | string | — | Source URL — any protocol analytics supports: rtsp / http / onvif / file / … (required for `register_source`) |
| `name` | string | — | Display name (for `register_source`) |
| `use_case` | string | — | `use_case_dict` key (**required** for `register_source`) |
| `pipeline_config` | object | — | Analytics pipeline config (default: motion + recording) |
| `webhook_url` | string | — | Events webhook (default: derived from `config.eventsWebhook.port`) |

**Actions**

| action | Behavior | Returns |
|---|---|---|
| `list` | All registered monitors + live analytics reachability | Monitor[] (`analyticsReachable`, `analyticsStatus`) |
| `status` | One monitor: DB record + live analytics status | Monitor + reachability |
| `register_source` | Validate use case → coordinate DB / analytics / worker (graceful-stop stale worker, then rebuild) | `{ success, monitor_id }` or `{ status: "already_running" }` |
| `unregister` | Graceful-stop worker → analytics DELETE → delete DB record | `{ success, monitor_id }` |
| `start` | Resume: analytics `/resume` + start worker + DB `online` | `{ success, monitor_id, status }` |
| `stop` | Pause: graceful-stop worker → analytics `/pause` → DB `offline` | `{ success, monitor_id, status }` |

> `stop` / `unregister` are **destructive** — confirm with the user first.

---

## 6. `smartbuilding_monitors_compose`

Docker-compose-style batch management of the monitors declared in a `monitors.yaml` file. The
tool **reads the file from disk every time** (independent of the `config.monitors` loaded at
server start), so it can act on a yaml at any path.

| Param | Type | Required | Description |
|---|---|---|---|
| `action` | enum | ✅ | `validate` \| `up` \| `down` \| `restart` \| `ps` |
| `file` | string | ✅ | Path to `monitors.yaml` (absolute or relative to cwd) |
| `monitor_id` | string | — | Act on a single monitor (default: every monitor in the file) |

**Actions** (compose analogues)

| action | ≈ compose | Behavior |
|---|---|---|
| `validate` | `config` | Validate fields only (`source_url`/`use_case` required; `use_case` must exist in `useCaseDict`); no state change |
| `up` | `up -d` | For each `enabled !== false` monitor: skip if DB+analytics+worker all consistent (`already_running`), else `register_source` |
| `down` | `down` | `unregister` each monitor (DB + analytics + worker cleanup) |
| `restart` | `restart` | `down` → `up` |
| `ps` | `ps` | Report each monitor's DB / analytics / worker state; no change |

> `down` / `restart` are **destructive** — confirm first. Per-compose traces are written to
> `logs/monitors/<monitor_id>/<YYYY-MM-DD>.log`.

---

## 7. `smartbuilding_use_case_validate`

Validate a use case end-to-end. Also runs inline as the `monitor_ctl register_source` pre-check;
callable standalone for a dry run.

Three sequential checks (any failure fails overall):

1. **Known** — `use_case` exists in `config.yaml` `use_case_dict`.
2. **Task registered** — its `video_summary_task` exists in multilevel-video-understanding (`GET /v1/tasks/<name>`).
3. **Schema consistent** — every `required: true` schema field appears in the task's `LOCAL_PROMPT` (case-insensitive substring).

| Param | Type | Required | Description |
|---|---|---|---|
| `use_case` | string | ✅ | `use_case_dict` key |

**Returns** `{ valid, use_case, video_summary_task, checks, required_fields, optional_fields,
missing_required_in_prompt, missing_optional_in_prompt, prompt_tail, suggestion }`. `valid` is
decided by required fields only; on failure `prompt_tail` gives the last ~200 chars of the prompt
to help locate the fix.

---

## 8. `smartbuilding_use_case_register`

Manage a use case's lifecycle at runtime, **without restarting the server**.

- `action: generate_task` — step 1 of the recommended two-step flow: run the schema↔prompt
  consistency check, `POST /v1/tasks` to multilevel-video-understanding (auto-`PATCH` on 409),
  and on success write `$SMARTBUILDING_DATA_DIR/use-cases/<use_case>/prompt.md` to disk
  (`~/.mcp-smartbuilding` is the default data directory). On the custom rule path,
  pass `evaluate_rules_path`; the tool reads that file for the consistency check, stages it to
  the same use-case directory as `evaluate_rules.py`, and smoke-tests the staged file. Does not touch the DB
  schema, `use_case_dict`, or `config.yaml`. `prompt_text` is **required** here.
- Any Final Schema field beyond `severity/event/desc` requires `evaluate_rules.py`. Both
  `generate_task` and `register` reject an extended schema without a rule before DB, VLM, config,
  or artifact side effects.
- `action: register` — (1) apply `schema_extensions` via `ALTER TABLE` (idempotent),
  (2) `POST /v1/tasks` to multilevel-video-understanding (auto-`PATCH` on 409),
  (3) inject the entry into the in-memory `use_case_dict` so the task-poller and other tools see
  it, (4) re-run `use_case_validate`. With `persist: true`, also writes the entry back to
  `config.yaml` (comment-preserving). As step 2 of the two-step flow, omit `prompt_text` — it is
  auto-read from the file `generate_task` wrote. If `evaluate_rules_path` is supplied it is staged
  to `<data_dir>/use-cases/<use_case>/evaluate_rules.py` (auto-discovered when the file is already there,
  e.g. staged by step 1), and that conventional absolute path is stored in `config.yaml` for
  runtime rule execution.
- `action: unregister` — `DELETE /v1/tasks/<name>` and remove from `use_case_dict`. The VLM
  delete is skipped when another use case shares the task. Every referencing monitor is detached
  (worker stopped, analytics source removed, DB row left offline with history retained). With
  `persist: true`, the entries are also removed from `config.yaml` and `monitors.yaml`, then
  `<data_dir>/use-cases/<use_case>/` is moved to `<data_dir>/use-cases/.backup/`. Incomplete cleanup keeps `ok: true`
  for the removed in-memory entry but sets `degraded: true` and explains the failure in `warnings`.
- `action: list` — **read-only** inventory of the live in-memory `use_case_dict`; needs no other
  arguments. Returns one entry per use case with `video_summary_task`, `schema_fields`,
  `rule_path` (`defaultRuleEvaluator` \| `evaluate_rules.py` \| `none`), and `report_source`.
  This reflects what the running server actually uses — including entries registered with
  `persist: false` — so prefer it over parsing `config.yaml` from disk. Call it after a
  successful register/unregister to report the system's current use cases.

Prompt authoring is **out of scope** here — draft the `## LOCAL_PROMPT` with the
`video-summary-prompt-studio` skill, then pass it via `prompt_text` (or let register auto-read
`<data_dir>/use-cases/<use_case>/prompt.md`).

| Param | Type | Required | Description |
|---|---|---|---|
| `action` | enum | ✅ | `register` \| `generate_task` \| `unregister` \| `list` |
| `use_case` | string | ✅ (not for `list`) | Key matching `^[a-z][a-z0-9_]{1,63}$` |
| `video_summary_task` | string | — | VLM task name (default `<use_case>_monitor`; must not collide with builtins) |
| `description` | string | — | Human description shown by `/v1/tasks` |
| `evaluate_rules_path` | string | required for extended schema/custom alerts | Path to a custom `evaluate_rules.py`; read for consistency checks, staged to `<data_dir>/use-cases/<use_case>/evaluate_rules.py`, smoke-tested, and the conventional absolute path persisted into `config.yaml` |
| `reports` | object | — | `{ data_source, default_type, filter }` |
| `summarize` | object | — | Per-clip summarize config `{ method, processor_kwargs }` |
| `prompt_text` | string | ✅ for `generate_task` | Full 4-section prompt (Markdown or raw Python). For `register`, omit to auto-read `<data_dir>/use-cases/<use_case>/prompt.md` |
| `schema_extensions` | array | — | Extra `video_summary_tasks` columns `{ name, type: text\|integer\|real, required }`. When omitted, inferred from prompt `KEY:` lines. Any extension selects the custom-rule path |
| `overwrite` | boolean | — | Replace an existing entry (default false) |
| `persist` | boolean | — | Mirror the mutation into the booted `config.yaml` (default true; on unregister also strips bound monitors from `monitors.yaml` and archives `<data_dir>/use-cases/<use_case>/` to `<data_dir>/use-cases/.backup/`) |

---

## 9. `smartbuilding_plan_ctl`

Per-monitor plans: arbitrary JSON records keyed by name. The rule engine can read today's plan
before deciding whether to fire. Plan shape is user-defined; the tool doesn't interpret it.

| Param | Type | Required | Description |
|---|---|---|---|
| `monitor_id` | string | ✅ | Monitor ID |
| `action` | enum | ✅ | `list` \| `upsert` \| `delete` |
| `name` | string | — | Unique plan name within the monitor (required for `upsert` / `delete`) |
| `plan` | object | — | Plan data (for `upsert`, arbitrary JSON) |
| `plan_date` | string | — | Optional `YYYY-MM-DD` hint stored with the plan (not the key) |
| `active_only` | boolean | — | Return only active plans (default true, for `list`) |

`delete` is a **soft delete** (`active=0`, data retained) — still treated as destructive; confirm
first.

---

## 10. `smartbuilding_rule_eval`

Manually re-run the rule evaluator against a completed task (defaults to the monitor's latest
completed task). Rebuilds the same `RuleContext` the task-poller uses. Dry by default.

| Param | Type | Required | Description |
|---|---|---|---|
| `monitor_id` | string | ✅ | Monitor ID |
| `task_id` | number | — | Task to re-evaluate (default: latest completed for the monitor) |
| `create_alert` | boolean | — | When true, insert an alert row on `shouldAlert` (default false — dry run; cooldown honoured) |

> In normal operation you never call this: alerts are created **automatically** by the worker's
> rule-engine callback when a summary task completes. `rule_eval` is a debugging / manual-replay
> aid.

---

## Tool summary

| Tool | Key traits |
|---|---|
| `alert_query` | `latest`/`by_date`/`ack`/`stats`; LEFT-JOIN task+event; severity traced via task |
| `scene_query` | vllm-serving-ipex; live-frame VLM; ffmpeg resize; frame archive; `<think>` stripped |
| `generate_report` | SRT build; caption-only VLM; writes `reports`; config-derived source/filter |
| `video_db` | read-only `SELECT`; writes rejected |
| `monitor_ctl` | single-monitor lifecycle; atomic DB+analytics+worker; use-case pre-check |
| `monitors_compose` | docker-compose over a yaml; `validate`/`up`/`down`/`restart`/`ps`; idempotent |
| `use_case_validate` | 3-step wiring check; case-insensitive; returns missing fields |
| `use_case_register` | runtime use-case register/unregister; schema ALTER; `/v1/tasks`; optional persist; `list` inventory |
| `plan_ctl` | per-monitor JSON plans CRUD; soft-delete |
| `rule_eval` | manual re-run of the rule evaluator; dry by default |

---

## Data model (SQLite)

`smartbuilding_video_db` reads these tables (SELECT only):

- **monitors** — registered cameras: `id` (= monitor_id), `name`, `source_url`, `use_case`,
  `video_summary_task`, `status`.
- **events** — `motion` and `static` pipeline events: `motion_type`, `start_time`, `end_time`,
  `duration_seconds`, optional clip/prefilter fields, and `trajectory_region`. Continuous
  `recording` payloads are stored in the separate `recordings` table; VSA connection status is
  exposed by its control API and is not inserted here.
- **video_summary_tasks** — one per motion clip: `id`, `monitor_id`, `event_id`,
  `summary_clip_input`, `status` (`pending | processing | completed | failed | ignored`),
  `summary_text` (raw VLM output), error/latency/token fields, plus **user-defined extension
  columns** declared by that use case under
  `use_case_dict.<use_case>.schema.video_summary_tasks.extensions` (commonly `event`,
  `severity`, and `desc`).
- **alerts** — use-case-agnostic rule-engine output: `id`, `monitor_id`, `task_id`, `event_id`,
  `use_case`, `description`, `notified`, `created_at`, `ack_at`, `ack_by`. Read structured fields
  such as `severity` or `event` by joining `task_id` to `video_summary_tasks`.
- **recordings** — `file_path`, `start_time`, `end_time`, `duration_seconds`, `file_size_bytes`.
- **reports** — generated report rows (from `generate_report`).
- **plans** — per-monitor JSON plans (`plan_ctl`).
- **monitor_state** — per-monitor runtime state as JSON (e.g. `last_alert_at`, use-case keys such
  as `last_get_up_at`).
