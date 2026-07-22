# MCP Webhook Event API Reference

The MCP server exposes an HTTP webhook `POST /events` that ingests pipeline events pushed by any upstream video-analytics client. This document is the **server-side contract**: as long as a client follows it, the MCP server applies the same parsing, DB writes, and downstream pipeline rules regardless of who the sender is. The production sender is `videostream-analytics`, but the same protocol applies equally to third-party analytics services, replay tools, unit-test mocks, and integration fixtures.

Implementation entry point: [packages/mcp-server/src/events-endpoint.ts](../../packages/mcp-server/src/events-endpoint.ts).

---

## 1. Endpoint

| Item | Value |
|------|-------|
| Method | `POST` |
| URL | `http://<mcp-host>:<events_port>/events` |
| Default port | `3101` (configurable in `config.yaml`, passed to `EventsEndpoint.start(port)`) |
| Content-Type | `application/json` |
| Auth | None (loopback / intranet deployment) |
| Client | Any process that can issue an HTTP POST; the production client is `videostream-analytics`, but the protocol is not tied to any implementation |

### 1.1 Health Probe

| Method | URL | Response |
|--------|-----|----------|
| `GET`  | `/health` | `200 {"status":"healthy"}` |
| Other paths / methods | — | `404` |

### 1.2 Response

All non-2xx responses are **errors** the client must handle. We split client errors by failure layer — **transport / framing** (`400`, `413`, `415`) vs. **semantic / business-rule** (`422`) — so the client can react differently without parsing error strings.

| Status | When | Body | DB write |
|--------|------|------|----------|
| `200 OK` | Envelope + payload valid, required fields present, DB writes succeeded. | `{"status":"ok","event_id":<int>,"task_id":<int?>,"recording_id":<int?>}` — the relevant id(s) for the rows just inserted. | ✅ |
| `400 Bad Request` | Body is not valid JSON, **or** the envelope is structurally broken: missing/empty `sourceId`, missing `type`, missing `payload`, or any of those fields has the wrong JSON type (e.g. `sourceId` is a number, `payload` is a string). | `{"error":"<reason>","code":"invalid_json"\|"invalid_envelope"}` — e.g. `"invalid JSON"`, `"envelope.sourceId is required"`, `"envelope.payload must be an object"`. | ❌ |
| `404 Not Found` | Path does not match `/events` or `/health`. | empty | — |
| `405 Method Not Allowed` | Wrong HTTP method on a known path (e.g. `GET /events`, `POST /health`). Sets `Allow` response header. | empty | — |
| `413 Payload Too Large` | Request body exceeds the configured size limit (default **1 MiB**, controlled by `events.max_body_bytes` in `config.yaml`). The connection is closed without buffering the rest of the body. | `{"error":"payload too large","code":"body_too_large","limit_bytes":1048576}` | — |
| `415 Unsupported Media Type` | `Content-Type` is not `application/json` (also rejected when the header is missing entirely). | `{"error":"content-type must be application/json","code":"unsupported_media_type"}` | — |
| `422 Unprocessable Entity` | Envelope parses and is structurally valid, but the event is semantically unprocessable: required payload fields missing for the given `type`, **or** `type` not in the enum `{motion, static, recording}`. Logged at `warn`. | `{"error":"missing required fields","code":"missing_required_fields","missing":["start_time","duration_seconds"]}` or `{"error":"unknown event type","code":"unknown_event_type","type":"foo"}` | ❌ |
| `500 Internal Server Error` | Envelope + payload validated, but a DB write threw an unexpected exception (disk full, schema mismatch, etc.). Logged at `error`. **Safe to retry** once the underlying server problem is resolved. | `{"error":"<exception message>","code":"internal_error"}` | partial / none |

> **Retry policy / back-pressure**:
> - `2xx` ⇒ success. Continue.
> - `4xx` ⇒ **permanent error, do not retry the same body**. The client sent something invalid and must fix it. `400` / `413` / `415` are framing problems; `422` is a payload semantic problem. Whichever it is, retrying the same bytes will produce the same response.
> - `5xx` ⇒ **transient server-side failure**. Client may retry with the same body after a backoff (exponential with jitter is reasonable; the server keeps no idempotency state, so a successful retry produces a new DB row).
> - **No event must ever stall the pipeline.** A `4xx` is logged, dropped, and the client moves on to the next event. The server never blocks the upstream stream on a single bad event.

Why `422` not `400` for the missing-field / unknown-type cases? They are **business-rule** failures, not transport failures — the JSON parsed cleanly, the envelope is well-formed, but the body cannot be applied to a known table. Splitting them into a distinct status code lets the client tell "my serializer is broken" (`400`) from "my pipeline emitted a stale or new event type the server doesn't know about" (`422`) without string-matching the error message. A stable `code` field is included in every error body for the same reason.

This matrix is enforced end-to-end by [packages/mcp-server/src/events-endpoint.ts](../../packages/mcp-server/src/events-endpoint.ts) and pinned by the integration test [tests/dev-mcp-server/test_events_webhook.py](../../tests/dev-mcp-server/test_events_webhook.py).

### 1.3 Request constraints

| Constraint | Value (default) | Configurable via | Violation |
|------------|-----------------|------------------|-----------|
| Max body size | `1 MiB` | `events.max_body_bytes` | `413 Payload Too Large` |
| Required `Content-Type` | `application/json` (charset optional) | — | `415 Unsupported Media Type` |
| Allowed methods on `/events` | `POST` only | — | `405 Method Not Allowed` (`Allow: POST`) |
| Allowed methods on `/health` | `GET` only | — | `405 Method Not Allowed` (`Allow: GET`) |
| Connection / read timeout | `30s` | `events.request_timeout_seconds` | Connection closed; no body sent |

---

## 2. Envelope (shared by all events)

```jsonc
{
  "sourceId":  "cam_child",                          // string, required
  "type":      "motion" | "static" | "recording",    // string enum, required
  "timestamp": "2026-06-25T14:30:45",                // ISO 8601 string, required
  "payload":   { ... }                               // object, required; schema varies by type
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sourceId`  | `string` | ✅ | Unique identifier for a camera / source. Must match `monitors.id`. Used as `monitor_id` for every DB write the handler produces. |
| `type`      | `"motion" \| "static" \| "recording"` | ✅ | Event category. `type` determines payload schema and target tables. Unknown `type` → `logger.warn`, no DB write, server responds `422 Unprocessable Entity` with `code="unknown_event_type"` (do not retry — fix the client). |
| `timestamp` | `string` (ISO 8601) | ✅ | Time the event was generated on the client side; recorded for diagnostic use only. The MCP server does **not** order DB rows by it — DB ordering uses `start_time` / `recording_start`. |
| `payload`   | `object` | ✅ | Business-field container. Schema is determined by `type`; see §3 / §4 / §5. |

---

## 3. `type=motion`

A motion segment event. The clip has already been cut into a standalone MP4 file by the client.

### 3.1 Payload fields

| Field | Type | Required | Description / target DB column |
|-------|------|----------|--------------------------------|
| `event_file_path`      | `string` | ✅ | Absolute path to the original (uncropped) clip. Written to `events.event_file_path`. |
| `summary_clip_input`   | `string` | ✅ | Path to the clip fed into the video-summary service. If the client performed ROI crop, this points to `<name>_input.mp4`; otherwise identical to `event_file_path`. Written to `video_summary_tasks.summary_clip_input`. |
| `start_time`           | `string` (ISO 8601) | ✅ | Clip start time. Written to `events.start_time`. |
| `end_time`             | `string` (ISO 8601) | ⚠️ Optional | Clip end time. Written to `events.end_time`. |
| `duration_seconds`     | `number` | ✅ | Clip duration in seconds (may be fractional). Written to `events.duration_seconds`. |
| `prefilter_passed`     | `0 \| 1` | ⚠️ Optional | Whether the client-side prefilter (e.g. NPU YOLO) passed. **This single field directly decides `task.status`** (see §3.2). **Absent** = no prefilter configured on this monitor; task defaults to `pending`. |
| `prefilter_classes`    | `string` (JSON-encoded array) | ⚠️ Optional | Hit class list, **must be pre-serialized into a string by the client** (e.g. `"[\"person\"]"`). The MCP server does not parse it — stored as TEXT in `events.prefilter_classes`. |
| `prefilter_confidence` | `number` (0 – 1) | ⚠️ Optional | Maximum confidence among hit classes. Written to `events.prefilter_confidence`. |
| `trajectory_region`    | `string` (`"x1,y1,x2,y2"`) | ⚠️ Optional | Bounding-box trajectory region for downstream ROI re-crop. Written to `events.trajectory_region`. The production client does not currently emit this — reserved for extension. |

**Required fields** (any missing → `logger.warn`, **no** DB write, server responds `422 Unprocessable Entity` with `code="missing_required_fields"`):
`event_file_path`, `summary_clip_input`, `start_time`, `duration_seconds`

### 3.2 MCP-side handling

Two tables are written in this order:

1. **`INSERT INTO events`** (`motion_type=motion`) — always written.
2. **`INSERT INTO video_summary_tasks`** — `status` is decided by `prefilter_passed`:

| `prefilter_passed` value | `video_summary_tasks.status` | video-worker behavior |
|--------------------------|------------------------------|------------------------|
| Field absent (no prefilter configured) | `pending` | Normal poll → call Video Summary Service → write summary |
| `1` | `pending` | Normal poll → call Video Summary Service → write summary |
| `0` | `ignored` | **Video Summary Service call skipped**, row kept only for audit |

> Design intent: every motion clip lands in `events` (preserving the full motion timeline for `state_query` / `rule_eval`), but clips that prefilter rejects do not waste Video Summary Service compute.

### 3.3 Downstream chain

Tasks with `status=pending` are picked up by the [task-poller](../../packages/mcp-server/src/video-worker/task-poller.ts), which calls `multilevel-video-understanding` to obtain a `summary_text`, then runs rule-engine to decide whether to insert into `alerts` and push to subscribers.

---

## 4. `type=static`

A stable segment with no motion. Clients typically emit a `static` event to "close out" a quiet period after a motion clip.

### 4.1 Payload fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start_time`       | `string` (ISO 8601) | ✅ | Static-period start. Written to `events.start_time`. |
| `end_time`         | `string` (ISO 8601) | ⚠️ Optional | Static-period end. Written to `events.end_time`. |
| `duration_seconds` | `number` | ✅ | Static duration in seconds. Written to `events.duration_seconds`. |

**Required fields**: `start_time`, `duration_seconds`

### 4.2 MCP-side handling

1. **`INSERT INTO events`** (`motion_type=static`) — only this one table.
2. **Does not** create a `video_summary_tasks` row (no video to summarize).
3. **Does not** trigger rule-engine.

---

## 5. `type=recording`

A continuous recording segment (distinct from motion: not tied to motion detection, sliced on a fixed rolling cadence).

### 5.1 Payload fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `recording_path`   | `string` | ✅ | Absolute path of the recorded MP4. Written to `recordings.file_path`. |
| `recording_start`  | `string` (ISO 8601) | ✅ | Recording start. Written to `recordings.start_time`. |
| `recording_end`    | `string` (ISO 8601) | ✅ | Recording end. Written to `recordings.end_time`. |
| `duration_seconds` | `number` | ⚠️ Optional | Recording duration. Written to `recordings.duration_seconds`. |
| `file_size_bytes`  | `integer` | ⚠️ Optional | Recording file size in bytes. Written to `recordings.file_size_bytes`. |

**Required fields**: `recording_path`, `recording_start`, `recording_end`

### 5.2 MCP-side handling

1. **`INSERT INTO recordings`** — only this one table.
2. **Does not** write `events`, **does not** write `video_summary_tasks`.
3. **Does not** trigger rule-engine.
4. The MCP server's periodic cleanup job deletes expired `<data_dir>/recordings/<YYYY-MM-DD>/` directories according to `storage.retention_days`.

> Use: long-window video retrieval. `scene_query` and similar tools fall back to recordings when looking up a time window (durations are stable), while motion clips drive event-focused queries. `motion` and `recording` are **independent streams** — continuous recording rolls on its own cadence, motion detection slices on its own; the two do not interfere.

---

## 6. Validation summary

Validation runs in this order; the first check that fails determines the response.

| # | Check | Failure response | Retry? |
|---|-------|------------------|--------|
| 1 | HTTP method matches path (`POST /events` / `GET /health`) | `405 Method Not Allowed` (`Allow: …`) | ❌ fix client |
| 2 | `Content-Type: application/json` | `415 Unsupported Media Type` | ❌ fix client |
| 3 | Body size ≤ `events.max_body_bytes` (default 1 MiB) | `413 Payload Too Large` | ❌ shrink payload |
| 4 | Body parses as JSON | `400 Bad Request` (`{"error":"invalid JSON"}`) | ❌ fix client |
| 5 | Envelope shape: `sourceId:string`, `type:string`, `payload:object` all present and correctly typed | `400 Bad Request` (`{"error":"envelope.<field> …"}`) | ❌ fix client |
| 6 | `type ∈ {motion, static, recording}` | `422 Unprocessable Entity` + `{"code":"unknown_event_type","type":"…"}`, `logger.warn` | ❌ fix client |
| 7 | Required payload fields for the given `type` (see §3 / §4 / §5) | `422 Unprocessable Entity` + `{"code":"missing_required_fields","missing":[…]}`, `logger.warn` | ❌ fix client |
| 8 | DB INSERT succeeds | `500 Internal Server Error`, `logger.error` | ✅ may retry after backoff |
| 9 | All passed | `200 OK` with inserted row id(s) | — |

> Type-coercion caveat: once a payload reaches the DB layer, numeric fields are coerced via `Number(...)`. If the client sends `"duration_seconds": "abc"`, the server stores `NaN` rather than rejecting — **clients must send correctly-typed values**. (Strict schema enforcement is intentionally not used; the policy is to favor forward compatibility over rigid validation.)

---

## 7. Five canonical examples

The five examples below are paired as "what the client sends → what the MCP server does". All use `sourceId=cam_child` for illustration. The production sender is `videostream-analytics`, but identical requests from any HTTP client produce identical server-side behavior.

---

### 7.1 motion **w/o prefilter** (this monitor has no NPU prefilter configured)

**Request** `POST /events`:

```json
{
  "sourceId":  "cam_child",
  "type":      "motion",
  "timestamp": "2026-06-25T14:30:45",
  "payload": {
    "event_file_path":    "/data/cam_child/motion_events/2026-06-25/seg_00001.mp4",
    "summary_clip_input": "/data/cam_child/motion_events/2026-06-25/seg_00001.mp4",
    "start_time":         "2026-06-25T14:30:30",
    "end_time":           "2026-06-25T14:30:45",
    "duration_seconds":   15.2
  }
}
```

**MCP-side handling**:

1. Insert into `events`:
   ```sql
   INSERT INTO events
     (monitor_id, motion_type, start_time, end_time, duration_seconds,
      event_file_path,
      prefilter_passed, prefilter_classes, prefilter_confidence, trajectory_region)
   VALUES
     ('cam_child', 'motion', '2026-06-25T14:30:30', '2026-06-25T14:30:45', 15.2,
      '/data/cam_child/motion_events/2026-06-25/seg_00001.mp4',
      NULL, NULL, NULL, NULL);
   ```
2. Insert into `video_summary_tasks` with **`status='pending'`** (prefilter field absent ⇒ no prefilter configured):
   ```sql
   INSERT INTO video_summary_tasks
     (monitor_id, event_id, summary_clip_input, status)
   VALUES
     ('cam_child', <ev.id>, '/data/cam_child/motion_events/2026-06-25/seg_00001.mp4', 'pending');
   ```
3. Return `200 {"status":"ok","event_id":<ev.id>,"task_id":<task.id>}`.
4. On its next tick, task-poller picks up this task → calls the Video Summary Service → writes `summary_text` → forwards to rule-engine.

---

### 7.2 motion **with prefilter pass** (NPU detected a target class)

**Request** `POST /events`:

```json
{
  "sourceId":  "cam_child",
  "type":      "motion",
  "timestamp": "2026-06-25T14:30:45",
  "payload": {
    "event_file_path":      "/data/cam_child/motion_events/2026-06-25/seg_00002.mp4",
    "summary_clip_input":   "/data/cam_child/motion_events/2026-06-25/seg_00002_input.mp4",
    "start_time":           "2026-06-25T14:30:30",
    "end_time":             "2026-06-25T14:30:45",
    "duration_seconds":     15.2,
    "prefilter_passed":     1,
    "prefilter_classes":    "[\"person\"]",
    "prefilter_confidence": 0.92
  }
}
```

**MCP-side handling**:

1. Insert into `events`, all three prefilter columns populated (`prefilter_passed=1`, `prefilter_classes='["person"]'`, `prefilter_confidence=0.92`).
2. Insert into `video_summary_tasks` with **`status='pending'`** (prefilter passed → forward to Video Summary Service).
3. Note: `summary_clip_input` points to the bbox-cropped `_input.mp4` produced upstream — the Video Summary Service sees the cropped clip, not the full frame, saving tokens.
4. Return `200 {"status":"ok","event_id":<ev.id>,"task_id":<task.id>}`.
5. Task-poller picks up the task → Video Summary Service → rule-engine → may insert into `alerts`.

---

### 7.3 motion **with prefilter NOT passed** (NPU saw no target class)

**Request** `POST /events`:

```json
{
  "sourceId":  "cam_child",
  "type":      "motion",
  "timestamp": "2026-06-25T14:31:10",
  "payload": {
    "event_file_path":      "/data/cam_child/motion_events/2026-06-25/seg_00003.mp4",
    "summary_clip_input":   "/data/cam_child/motion_events/2026-06-25/seg_00003.mp4",
    "start_time":           "2026-06-25T14:30:55",
    "end_time":             "2026-06-25T14:31:10",
    "duration_seconds":     15.0,
    "prefilter_passed":     0,
    "prefilter_classes":    "[]",
    "prefilter_confidence": 0.0
  }
}
```

**MCP-side handling**:

1. Insert into `events` with `prefilter_passed=0` — kept for audit (useful for later analysis of prefilter accuracy).
2. Insert into `video_summary_tasks` with **`status='ignored'`**:
   ```sql
   INSERT INTO video_summary_tasks
     (monitor_id, event_id, summary_clip_input, status)
   VALUES
     ('cam_child', <ev.id>, '/data/cam_child/motion_events/2026-06-25/seg_00003.mp4', 'ignored');
   ```
3. Task-poller's `getPendingTasks` only selects rows with `status='pending'`. **This task is never polled**, so the Video Summary Service is never called.
4. Rule-engine is not triggered, no alert is generated.
5. Return `200 {"status":"ok","event_id":<ev.id>,"task_id":<task.id>}` — the row was inserted, just in a terminal state.

> This is the core value of prefilter: a cheap NPU YOLO drops "leaves moving / lighting change / wandering pets" false-motion clips before they reach the Video Summary Service.

---

### 7.4 static

**Request** `POST /events`:

```json
{
  "sourceId":  "cam_child",
  "type":      "static",
  "timestamp": "2026-06-25T14:31:25",
  "payload": {
    "start_time":       "2026-06-25T14:31:10",
    "end_time":         "2026-06-25T14:31:25",
    "duration_seconds": 15.0
  }
}
```

**MCP-side handling**:

1. Insert into `events`:
   ```sql
   INSERT INTO events
     (monitor_id, motion_type, start_time, end_time, duration_seconds,
      event_file_path, prefilter_passed, prefilter_classes, prefilter_confidence, trajectory_region)
   VALUES
     ('cam_child', 'static', '2026-06-25T14:31:10', '2026-06-25T14:31:25', 15.0,
      NULL, NULL, NULL, NULL, NULL);
   ```
2. **Does not** create a `video_summary_tasks` row.
3. **Does not** trigger rule-engine.
4. Returns `200 {"status":"ok","event_id":<ev.id>}` (no `task_id` because no task row was created).

> `state_query` reads `events` and sees the alternating `motion → static → motion → static …` sequence to infer "active / idle" timing of the room; elder-wakeup's "still in bed" detection depends on long `static` runs.

---

### 7.5 recording

**Request** `POST /events`:

```json
{
  "sourceId":  "cam_child",
  "type":      "recording",
  "timestamp": "2026-06-25T14:31:00",
  "payload": {
    "recording_path":   "/data/cam_child/recordings/2026-06-25/rec_20260625_143000.mp4",
    "recording_start":  "2026-06-25T14:30:00",
    "recording_end":    "2026-06-25T14:31:00",
    "duration_seconds": 60.0,
    "file_size_bytes":  8192000
  }
}
```

**MCP-side handling**:

1. Insert into `recordings`:
   ```sql
   INSERT INTO recordings
     (monitor_id, file_path, start_time, end_time, duration_seconds, file_size_bytes)
   VALUES
     ('cam_child',
      '/data/cam_child/recordings/2026-06-25/rec_20260625_143000.mp4',
      '2026-06-25T14:30:00', '2026-06-25T14:31:00',
      60.0, 8192000);
   ```
2. **Does not** write `events`, **does not** write `video_summary_tasks`.
3. **Does not** trigger rule-engine.
4. Returns `200 {"status":"ok","recording_id":<rec.id>}`.
5. The MCP server's periodic cleanup job deletes expired `<data_dir>/recordings/<YYYY-MM-DD>/` directories according to `storage.retention_days`.

> `recording` and `motion` are **two independent streams**: continuous recording rolls on its own cadence; motion detection slices on its own. They do not interact. `scene_query` etc. prefer recording segments for time-window playback (stable durations) and use motion clips for event-focused queries.

---

### 7.6 Error-path examples

These illustrate the 4xx / 5xx responses a client should be prepared to handle. Same `POST /events` URL.

**Missing required fields → `422 Unprocessable Entity` (semantic error, do not retry):**

Request:
```json
{
  "sourceId":  "cam_child",
  "type":      "motion",
  "timestamp": "2026-06-25T14:30:45",
  "payload": {
    "event_file_path":    "/data/cam_child/motion_events/2026-06-25/seg_00004.mp4",
    "summary_clip_input": "/data/cam_child/motion_events/2026-06-25/seg_00004.mp4"
  }
}
```

Response:
```
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"error":"missing required fields","code":"missing_required_fields","missing":["start_time","duration_seconds"]}
```

**Unknown `type` → `422 Unprocessable Entity` (semantic error, do not retry):**

Request:
```json
{ "sourceId": "cam_child", "type": "audio", "timestamp": "2026-06-25T14:30:45", "payload": {} }
```

Response:
```
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"error":"unknown event type","code":"unknown_event_type","type":"audio"}
```

**Malformed JSON → `400 Bad Request` (framing error, fix client):**

Request body: `not even { json`

Response:
```
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error":"invalid JSON: Unexpected token n in JSON at position 0","code":"invalid_json"}
```

**Bad envelope shape → `400 Bad Request` (framing error, fix client):**

Request:
```json
{ "sourceId": 12345, "type": "motion", "payload": {} }
```

Response:
```
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error":"envelope.sourceId must be a non-empty string","code":"invalid_envelope"}
```

**Body too large → `413 Payload Too Large`:**

```
HTTP/1.1 413 Payload Too Large
Content-Type: application/json

{"error":"payload too large","code":"body_too_large","limit_bytes":1048576}
```

**Wrong Content-Type → `415 Unsupported Media Type`:**

```
HTTP/1.1 415 Unsupported Media Type
Content-Type: application/json

{"error":"content-type must be application/json","code":"unsupported_media_type"}
```

**DB write threw → `500 Internal Server Error` (retry after backoff):**

```
HTTP/1.1 500 Internal Server Error
Content-Type: application/json

{"error":"SQLITE_BUSY: database is locked","code":"internal_error"}
```

---

## 8. DB-write quick reference

| Event type | `events` | `video_summary_tasks` | `recordings` | Triggers rule-engine |
|------------|----------|------------------------|--------------|----------------------|
| `motion` (w/o prefilter)         | ✅ motion | ✅ `pending` | — | ✅ |
| `motion` (prefilter `passed=1`)  | ✅ motion | ✅ `pending` | — | ✅ |
| `motion` (prefilter `passed=0`)  | ✅ motion | ✅ `ignored` | — | ❌ |
| `static`                         | ✅ static | — | — | ❌ |
| `recording`                      | — | — | ✅ | ❌ |

---

## 9. Related documents

- Monitor lifecycle / register flow / graceful shutdown: [docs/implements/monitor-ctl-analytics-integration.md](../implements/monitor-ctl-analytics-integration.md)
- Overall design (webhook's place in the architecture): [docs/smartbuilding-video-design-2026.2.md](../smartbuilding-video-design-2026.2.md)
- Analytics-side REST API: [docs/apis/videostream_analytics_api.md](./videostream_analytics_api.md)
- MCP server entry point: [packages/mcp-server/src/events-endpoint.ts](../../packages/mcp-server/src/events-endpoint.ts)
- Reference implementation (production upstream) — motion emit: [videostream-analytics/stream_monitor/rtsp_monitor.py](../../videostream-analytics/stream_monitor/rtsp_monitor.py)
- Reference implementation (production upstream) — recording emit: [videostream-analytics/stream_monitor/continuous_recorder.py](../../videostream-analytics/stream_monitor/continuous_recorder.py)
