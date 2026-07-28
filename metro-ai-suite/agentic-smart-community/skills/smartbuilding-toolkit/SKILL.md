---
name: smartbuilding-toolkit
description: >-
  Generic, use-case-agnostic guide to the smart-community MCP server and its
  smartbuilding_* video tool set. Read this before touching any smartbuilding_* tool.
  IMPORTANT: this toolkit must not create/register new use cases directly; for any new
  use case request, first load video-summary-prompt-studio and follow its Q1/Q2 schema
  confirmation gate before any smartbuilding_use_case_register call.
  Teaches the full tool catalog, the SQLite data model, how to discover which monitor to
  act on, how to generate reports, and how pushed alerts reach a session.
  Framework-agnostic — works for any MCP client (OpenClaw, Hermes, Claude Desktop,
  Cursor, …) with no persona required.
---

# smart-community Toolkit

Every tool is keyed on **`monitor_id`** (the camera id, e.g. `cam_child`). There is no
global `source_id`; ids are per-monitor and never assume they are unique across use cases.

## Mandatory handoff for new use cases

If the user asks to create/register a new use case, do not draft a prompt and do not call
`smartbuilding_use_case_register` from this toolkit. First load the
`video-summary-prompt-studio` skill. That skill owns the Q1/Q2 customer interaction,
final schema confirmation, prompt authoring, use-case registration, and monitor registration.
This toolkit resumes only after the use case exists, or for ordinary monitor/report/query work.

---

## 1. Tool catalog

All tool ids are defined in MCP server: `smart-community`, with prefixed `smartbuilding_`. Times are ISO-8601; show users `HH:MM`/`HH:MM:SS`.

### smartbuilding_alert_query — read/ack the important alerts
Every row in `alerts` is already rule-engine-filtered, so you do **not** re-filter by
severity/type. `severity`/`event`/`desc` live on the linked task, returned via JOIN.
- `monitor_id` (req), `action` (req): `latest | by_date | ack | stats`
- `latest` → newest N (`limit`, default 20), each with `taskDetails` + `eventDetails`.
- `by_date` → `start_date`/`end_date` (`YYYY-MM-DD`, inclusive; equal = one day).
- `ack` → `alert_id` + `ack_by`; marks an alert acknowledged.
- `stats` → `{ total, unacked }` (COUNT only; optional date range).

### smartbuilding_scene_query — one-shot VLM look at the live frame
Reads the monitor's `latest.jpg` and asks vllm-serving-ipex to describe it now.
- `monitor_id` (req), `prompt` (optional override), `model`/`vlm_url`/`max_edge_px` (optional).
- Returns `{ scene }`. Use this for any "what is happening right now?" question — never
  invent a scene. This is also how you ask targeted questions about the current frame
  (e.g. "list every food item visible in the fridge") by passing a custom `prompt`.

### smartbuilding_generate_report — build a period report from the DB
Queries a data source over a period, builds an SRT timeline, and calls the video summary service
(caption-only) to write a narrative. Persists a row in `reports`. See §4.
- `monitor_id` (req), `type`: `daily | weekly | monthly | custom` (default `daily`),
  `data_source`: `events | alerts | video_summary_tasks` (default `alerts`), `filter` (object),
  `period_start`/`period_end` (for `custom`; `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`).
- Returns `{ periodStart, periodEnd, type, dataSource, eventCount, reportText, latencySeconds }`.
- `daily` = today, `weekly` = last 7 days, `monthly` = last 30 days.

### smartbuilding_plan_ctl — per-monitor plans (arbitrary JSON by name)
The rule engine can read today's plan before deciding to fire. Plan shape is
user-defined (the tool doesn't interpret it).
- `monitor_id` (req), `action` (req): `list | upsert | delete`,
  `name` (unique per monitor, req for upsert/delete), `plan` (object, for upsert),
  `plan_date` (optional `YYYY-MM-DD` hint), `active_only` (default true, for list).
- `delete` is a **soft delete** (`active=0`) — still a destructive action (see §5).

### smartbuilding_video_db — read-only SQL escape hatch
`SELECT`-only against all tables. Any write (`INSERT`/`UPDATE`/`DELETE`) is rejected.
- `query` (req, SELECT only), `params` (array, `?` placeholders).
- Use this for anything the typed tools don't cover, e.g. reading `monitor_state`.
- Alerts are created automatically by the worker's rule engine when a summary task
  completes — you never trigger evaluation yourself; just read alerts with
  `smartbuilding_alert_query`.

### smartbuilding_monitor_ctl — single-monitor lifecycle
- `action` (req): `list | status | start | stop | register_source | unregister`,
  `monitor_id` (req except `list`); for `register_source`: `source_url` (req),
  `use_case` (req, must be a `config.yaml` `use_case_dict` key), `name`,
  `pipeline_config`, `webhook_url`, `persist`.
- **Naming conventions for `register_source`** (keep new monitors consistent with the
  built-ins `cam_fridge` / `cam_child` / `cam_elder_bedroom`):
  - `monitor_id`: use `cam_<use_case>` (e.g. `cam_pet_safety`). Do NOT invent ad-hoc
    ids like `pet_monitor_001`.
  - `name`: a short **English** display name (e.g. `"Pet Safety Camera"`), even when
    the user's request is in Chinese.
  - `persist: true`: mirror the monitor (incl. `pipeline_config`, which is not stored
    in the DB) back to `monitors.yaml` so it survives an MCP restart.
- `list` → all monitors + live analytics reachability. `status` → one monitor.
- `start`/`stop` resume/pause streaming. `register_source` validates the use case
  first (see `smartbuilding_use_case_validate`) then coordinates DB + analytics + worker
  atomically.
- `stop`/`unregister` are **destructive** (see §5).

### smartbuilding_monitors_compose — docker-compose-style batch over a monitors.yaml
- `action` (req): `validate | up | down | restart | ps`, `file` (req, yaml path),
  `monitor_id` (optional single target).
- `validate`/`ps` are read-only; `up` is idempotent (skips already-running);
  `down`/`restart` are **destructive** (see §5).

### smartbuilding_use_case_validate — check a use case is wired end-to-end
- `use_case` (req). Verifies: known in `use_case_dict`, its video summary service task is registered,
  and every `required` schema field appears in the task's LOCAL_PROMPT. Returns
  `{ valid, checks, required_fields, missing_required_in_prompt, suggestion, … }`.

> Creating/authoring new use cases (drafting prompts, choosing schema, registering video summary service tasks)
> is handled by `video-summary-prompt-studio`, not this toolkit. Do not call
> `smartbuilding_use_case_register` until that skill has asked Q1/Q2 and the user has confirmed
> Final Schema + Rule Path.

---

## 2. Data model (SQLite)

`smartbuilding_video_db` reads these tables (SELECT only):

- **monitors** — registered cameras: `id` (= monitor_id), `name`, `use_case`, `status`.
- **events** — pipeline events. Key column `motion_type` ∈ `motion | static | recording | status`;
  `start_time`, `end_time`, `prefilter_classes` (YOLO hits).
- **video_summary_tasks** — one per event clip: `id`, `event_id`, `clip_file_path`,
  `status` (`pending → completed`), `summary_text` (raw video summary service output), plus **user-defined
  extension columns** declared in `config.schema` — commonly `event`, `severity`, `desc`,
  `confidence`. Extension columns are how use cases carry structured results.
- **alerts** — rule-engine output: `id`, `monitor_id`, `task_id`, `event_id`, `use_case`,
  `alert_type`, `description`, `created_at`, `acked_at`, `acked_by`.
  **`severity` is not stored here** — JOIN `video_summary_tasks` on `task_id` for it.
- **recordings** — `file_path`, `start_time`, `end_time`, `duration`.
- **reports** — generated report rows (from `smartbuilding_generate_report`).
- **plans** — per-monitor JSON plans (`smartbuilding_plan_ctl`).
- **monitor_state** — per-monitor runtime state as JSON (e.g. `last_alert_at`, and
  use-case keys like `last_get_up_at`). Read it with `smartbuilding_video_db`.

---

## 3. Which monitor do I act on? (discovery)

Tools require `monitor_id`. To resolve it:

1. **If given a default / explicit id**, use it — but confirm it exists by checking the
   monitor list (below) before relying on it.
2. **Discover by use case.** Call `smartbuilding_monitor_ctl action=list` (or read the
   `smartbuilding://monitors` resource) and filter by the `use_case` you serve
   (e.g. `child_safety`, `elder_wakeup`, `refrigerator_monitor`):
   - **exactly one match** → bind it for this session.
   - **multiple matches** (e.g. two elder-bedroom cameras) → **ask the user** which one.
   - **no match** → tell the user no monitor is registered for this use case; offer to
     register one (`smartbuilding_monitor_ctl action=register_source`).

A persona typically declares only its `use_case` (and maybe a hardcoded default id);
the resolution algorithm above lives here in the toolkit.

---

## 4. Reports are two layers

1. **Tool layer (raw).** `smartbuilding_generate_report` deterministically pulls the
   chosen `data_source` with `filter`, builds an SRT, calls the video summary service, and **writes the raw
   report to the `reports` table**. Pick the source per your use case:
   - narration of activity → `data_source: events` (often `filter: { motion_type: motion }`)
   - a log of triggered alerts → `data_source: alerts` (usually `filter: {}`)
   - video summary service-analyzed outcomes on a schema field → `data_source: video_summary_tasks` with a `filter` on an
     extension column (e.g. `{ event: wakeup }`).
2. **Persona layer (polish).** The agent reads `reportText`, then decides **whether to
   push, and in what voice** — rewrite in the user's language/tone, lead with the
   headline, don't ask "shall I send it?", just send the finished body.

---

## 5. Alerts, pushes, and destructive ops

**How alerts reach a chat.** When the rule engine creates an alert, the server emits a
resource-updated notification; a framework adapter may deliver it into a session.

**Never fabricate.** If a query returns nothing, say so plainly. If a frame is ambiguous,
say it's unclear rather than guessing.

**Two-phase confirmation for destructive actions.** These change or tear down state —
first explain what will happen and get explicit user confirmation, then execute:
- `smartbuilding_monitor_ctl action=stop | unregister`
- `smartbuilding_monitors_compose action=down | restart`
- `smartbuilding_plan_ctl action=delete`

(`smartbuilding_video_db` is read-only, so there is no "clear database" tool — reads are
always safe.)

---

## 6. Resources (read surface)

Alongside tools, the server exposes MCP **resources** — read-only JSON (or JPEG) endpoints
under the `smartbuilding://` scheme. Any MCP client can `resources/read` them; most agents
never need to, because the typed tools (§1) wrap the same data with friendlier shapes.
Resources exist mainly for the **subscription path** (§7) and for clients that prefer a
resource model.

| URI | Returns |
|---|---|
| `smartbuilding://monitors` | `{ monitors }` — every monitor + online status. Same data as `smartbuilding_monitor_ctl action=list`. |
| `smartbuilding://monitor/{id}/stats` | `{ monitorId, … }` — today's event/alert counts for one monitor. |
| `smartbuilding://monitor/{id}/latest-frame` | `{ monitorId, frame, note }` — base64 JPEG of the last frame. **Currently stubbed** (`frame: null`) pending videostream-analytics integration; use `smartbuilding_scene_query` for a live look instead. |
| `smartbuilding://monitor/{id}/alerts` | `{ monitorId, latestId, alerts }` — newest 20 alerts + the max alert id (the cursor seed). |
| `smartbuilding://monitor/{id}/alerts?since={id}` | Same shape, but only alerts with `id > since` (up to 200). `latestId` echoes `since` when there's no delta. This is the **incremental cursor read**. |

Alert rows in these resources are the raw `alerts` DB rows (same as `smartbuilding_alert_query`) — `severity` is **not** on them; JOIN `video_summary_tasks` for it.

---

## 7. Subscriptions (how a push actually happens)

The server supports MCP resource **subscriptions** (`resources.subscribe: true`). This is
the machinery behind "an alert appeared in my chat" (§5) — you, the agent, do **not**
subscribe yourself; a framework adapter (§8) owns the long-lived subscription. Worth
understanding so you know what is and isn't guaranteed:

1. **Subscribe.** A client calls `resources/subscribe { uri: smartbuilding://monitor/<id>/alerts }`.
   The server records `(sessionId → uri)` in its subscriber registry. Subscriptions require a
   **stateful session** — a per-session `mcp-session-id` over Streamable HTTP, or the stdio
   singleton. Idle sessions are swept from the registry unless a live SSE stream keeps them.
2. **Broadcast.** When the rule engine creates an alert, the server sends
   `notifications/resources/updated { uri }` to every session subscribed to that URI. The
   notification carries **the URI only — no alert payload**.
3. **Delta read.** On the notification the client reads `…/alerts?since=<cursor>` to pull the
   new rows, then advances its cursor to `latestId`.

Delivery properties the SDK adapter guarantees on top of this (so a sink can rely on them):
**at-least-once** per `alert.id` (sinks must be idempotent), **per-monitor ordering** (ascending
id; cross-monitor order is not guaranteed), **no history replay** on a fresh cursor (first sync
just seeds to the current latest), **resume across restarts** with a persistent cursor store, and
**self-heal on id regression** if the source DB is recreated.

---

## 8. Framework adapters (for integrators)

> This section is for wiring the server into a **new host framework**, not for operating a
> monitor. Skip it if you're just answering a user's questions.

The MCP server is **host-agnostic** — it knows nothing about chat sessions, channels, or
personas. A *framework adapter* is the bridge that turns alert notifications into whatever a
host consumes. The heavy lifting lives in the SDK **`@smartbuilding-video/framework-adapter-sdk`**
(`packages/framework-adapter-sdk`), which exports `SmartBuildingAdapter`, the cursor stores
(`FileCursorStore`, `MemoryCursorStore`), and the `AlertSink` / `AdapterConfig` types.

**The SDK owns the hard parts:** MCP client lifecycle, subscribe-before-read, cursor dedup,
per-monitor ordering, reconnect with backoff, optional poll fallback. **You supply one thing:**
an `AlertSink`.

```ts
interface AlertSink { push(payload: { monitorId: string; alert: Alert }): Promise<void>; }
```

**Existing example — `examples/openclaw/`** (the only one today): a production OpenClaw plugin,
`smartbuilding-alerts`. It subscribes to each configured monitor's alerts resource and injects
every new alert into a routed OpenClaw session as if the user had spoken it (raw pass-through —
**no rules, no persona in the adapter**; those live in the agent workspace). It owns the route
table `monitor → session[]` in plugin config, and per route `deliver:false` = inject into the
session with zero LLM, `deliver:true` = also relay to an external channel. Its `src/` shows the
shape of a real sink: `config.ts` (parse/validate), `sink.ts` (the `AlertSink`), `session-inject.ts`
(transcript API) with `session-append.ts` (FS-append fallback), `format.ts`.

**To add a new example (new framework):**

1. Scaffold `examples/<framework>/` and depend on `@smartbuilding-video/framework-adapter-sdk`.
2. Implement `AlertSink.push(payload)` — map `{ monitorId, alert }` to your host's primitive
   (a chat turn, a webhook, a push notification). Make it **idempotent on `alert.id`** — the SDK
   is at-least-once.
3. Build an `AdapterConfig`: `transport` (`{ kind:"http", url:".../mcp", headers? }` or
   `{ kind:"stdio", command, args }`), `monitorIds` (which cameras to watch), `cursorStore`
   (`new FileCursorStore(path)` to survive restarts, else in-memory), optional `pollFallbackMs`
   and `logger`.
4. `const adapter = new SmartBuildingAdapter(config, sink)`; call `await adapter.start()` from
   your framework's service-start hook and `await adapter.stop()` on shutdown.
5. Keep **routing** (which session/channel each monitor's alert goes to) in *your* adapter's
   config — the server never learns about it.
