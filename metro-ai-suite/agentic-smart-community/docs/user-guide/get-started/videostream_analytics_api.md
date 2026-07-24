# videostream-analytics HTTP API Reference

The videostream-analytics microservice (VSA) is the standalone RTSP-processing service that pulls camera streams, runs motion detection and optional NPU-based YOLO prefiltering, cuts qualifying segments into MP4 clips, and pushes the resulting events to a configured webhook consumer (typically the MCP server). 

---

## 1. Service Overview

| Item | Value |
|------|-------|
| Service name | `videostream-analytics` |
| Framework | FastAPI (served by uvicorn) |
| Default bind | `0.0.0.0:8999` (`server.host` / `server.port` in `config.yaml`) |
| Default webhook target | `http://localhost:18800/events`, overridable by the `WEBHOOK_URL` environment variable or by the `webhook_url` field in each `register_source` request |
| Content-Type | `application/json` for all requests and responses |
| Character encoding | UTF-8 |
| Auth | None. VSA is expected to run in a trusted network segment (loopback / private LAN / reverse proxy). |

The service is a long-running single process. Each registered source spawns background threads for the motion pipeline, an optional continuous recorder, and a shared keepalive watchdog. Multiple sources coexist in a single VSA instance.

---

## 2. Endpoint Summary

| Method | Path | Purpose | See |
|--------|------|---------|-----|
| `GET`    | `/health` | Liveness probe. | §3.1 |
| `GET`    | `/sources` | List all registered sources (bare array). | §3.2 |
| `GET`    | `/sources/{source_id}` | Get source status. | §3.3 |
| `GET`    | `/sources/{source_id}/status` | Alias of `/sources/{source_id}`; the MCP server calls this to check for existence. | §3.3 |
| `POST`   | `/register_source` | Register and start a new source. | §3.4 |
| `DELETE` | `/unregister_source` | Unregister a source (body form). | §3.5 |
| `DELETE` | `/sources/{source_id}` | Unregister a source (path form; equivalent to `/unregister_source`). | §3.5 |
| `POST`   | `/sources/{source_id}/stop` | Stop and unregister (equivalent to `DELETE`). | §3.5 |
| `POST`   | `/sources/{source_id}/restart` | Stop and start the pipeline while preserving the bundle. | §3.6 |
| `POST`   | `/sources/{source_id}/pause` | Pause the pipeline; keep the source registered. | §3.7 |
| `POST`   | `/sources/{source_id}/resume` | Resume a paused pipeline. | §3.7 |
| `POST`   | `/sources/{source_id}/keepalive` | Refresh the keepalive timestamp (Phase 8). | §3.8 |
| `PUT`    | `/sources/{source_id}/pipeline` | Hot-update pipeline configuration. | §3.9 |

---

## 3. Control Plane

All responses are JSON. The service follows a small, uniform status-code convention:

| Status | Meaning |
|--------|---------|
| `200 OK` | The requested state change succeeded, or the idempotent no-op response (`already_running`, `not_running`) is returned. |
| `404 Not Found` | The referenced `source_id` is not registered. |
| `422 Unprocessable Entity` | The request body failed schema validation (missing required fields, unknown fields due to `extra="forbid"`, or wrong types). See §5.2. |
| `500 Internal Server Error` | An unexpected server-side exception occurred. Retryable once the underlying condition is resolved. |

### 3.1 `GET /health`

Liveness probe.

**Request**: no body.

**Response 200**:

```json
{ "status": "ok", "service": "videostream-analytics" }
```

### 3.2 `GET /sources`

List all registered sources.

**Request**: no body.

**Response 200**: a bare JSON array of `SourceStatus` objects (see §3.3). The array is `[]` when no sources are registered.

```json
[
  {
    "source_id": "cam_demo",
    "source_url": "rtsp://localhost:8554/live/child",
    "data_dir": "/data/cam_demo",
    "status": "online",
    "running": true,
    "recording_enabled": true,
    "health": { "...": "..." },
    "keepalive_enabled": false,
    "last_keepalive_at": null
  }
]
```

> The `/sources` response is intentionally a **bare array**, not `{"sources": [...]}`. This is a Phase 7 contract.

### 3.3 `GET /sources/{source_id}` and `GET /sources/{source_id}/status`

Return the status of a single source. Both paths dispatch to the same handler and return identical bodies. The MCP server's `analyticsSourceExists` probe calls the `/status` variant.

**Path parameter**: `source_id` — the id used at registration.

**Response 200** (`SourceStatus`):

| Field | Type | Description |
|-------|------|-------------|
| `source_id` | `string` | Same as the path parameter. |
| `source_url` | `string` | The RTSP URL supplied at registration. |
| `data_dir` | `string` | Absolute path of the per-source output directory. |
| `status` | `string` | Pipeline lifecycle state. See §3.7.1 for the full state machine. |
| `running` | `boolean` | Whether the pipeline background thread is alive. |
| `recording_enabled` | `boolean` | Whether the continuous recorder is enabled for this source. |
| `health` | `object` | Health sub-object; see below. |
| `keepalive_enabled` | `boolean` | Whether keepalive watchdog is enabled for this source (Phase 8). |
| `last_keepalive_at` | `string \| null` | ISO 8601 UTC timestamp of the most recent keepalive; `null` when keepalive is disabled. |

**`health` sub-object**:

| Field | Type | Description |
|-------|------|-------------|
| `failure_count` | `int` | Consecutive RTSP read failures; reset to `0` upon a successful reconnect. |
| `last_failure_time` | `string \| null` | ISO 8601 timestamp of the most recent failure. |
| `reconnect_count` | `int` | Cumulative successful reconnect attempts. |
| `recovery_strategy` | `"retry" \| "pause" \| "remove"` | Health-recovery strategy taken from `pipeline.health.recovery_strategy`. |
| `max_failures` | `int` | Failure threshold that triggers the recovery strategy. |
| `start_time` | `string \| null` | ISO 8601 timestamp of pipeline startup. |

**Response 404**:

```json
{ "detail": "Source not found: cam_xxx" }
```

### 3.4 `POST /register_source`

Register a new source and start its pipeline. Idempotent: re-registering an id that is already running returns `{"status": "already_running"}` without changes.

#### Request body (`RegisterSourceRequest`, `extra="forbid"`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_id` | `string` | ✅ | Unique identifier. |
| `source_url` | `string` | ✅ | RTSP URL from which VSA pulls the stream. |
| `webhook_url` | `string \| null` | Optional | Overrides the destination for this source's events. Falls back to the global `webhook.url` when omitted. |
| `data_dir` | `string \| null` | Optional | Absolute path for this source's outputs. Falls back to `<config.data_dir>/<source_id>/` when omitted. |
| `pipeline` | `PipelineConfig` | Optional | Nested pipeline configuration; see below. |

Unknown top-level fields (including the legacy `rtsp_url`, top-level `motion`, and `use_case` that pre-date Phase 7) are rejected with `422` and their names appear in the `unknown_fields` array of the error body.

#### `PipelineConfig`

The nested pipeline object (`extra="forbid"`). Every sub-block is optional; when a sub-block is omitted it is filled by the corresponding `defaults.<sub_block>`. Fall-back is **whole-block replacement**, not field-level merge — supply a full sub-block whenever a single field needs to differ from the defaults.

| Sub-block | Model | Purpose |
|-----------|-------|---------|
| `motion` | `MotionConfig` | Frame-difference motion detector parameters. |
| `segment` | `SegmentConfig` | Motion-clip segmentation parameters. |
| `prefilter` | `PrefilterConfig` | Optional NPU / OpenVINO YOLO prefilter. |
| `roi` | `RoiConfig` | Phase 9 ROI crop and trajectory-region emission. |
| `recording` | `RecordingConfig` | Fixed-cadence continuous recording branch. |
| `health` | `HealthConfig` | RTSP failure-handling policy. |
| `keepalive` | `KeepaliveConfig` | Phase 8 keepalive protocol. |

##### `MotionConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | When `false`, the motion detection path is skipped entirely. |
| `diff_threshold` | `int` | `25` | Per-pixel frame-difference threshold. |
| `area_ratio` | `float` | `0.015` | Minimum fraction of frame area required to declare motion. |
| `stable_frames` | `int` | `30` | Consecutive static frames required to end a motion event. |

##### `SegmentConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_duration` | `float` | `10.0` | Hard ceiling on segment length, in seconds. |
| `min_duration` | `float` | `1.0` | Minimum clip duration; shorter clips are discarded. |

##### `PrefilterConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `false` | Enable OpenVINO YOLO prefilter on motion clips. |
| `model_path` | `string` | `""` | Absolute path to the OpenVINO `.xml` model. |
| `target_classes` | `array<string>` | `["person"]` | Class labels that count as a hit. |
| `min_confidence` | `float` | `0.4` | Minimum detection confidence. |
| `min_frames_hit` | `int` | `2` | Number of hits within a clip required for PASS. |
| `detect_fps` | `float` | `2.0` | YOLO inference rate; inference does not run on every frame. |
| `device` | `string` | `"CPU"` | OpenVINO device (`CPU`, `GPU`, `NPU`). |

##### `RoiConfig` (Phase 9)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `false` | When enabled, prefilter PASS produces a `<clip>_input.mp4` next to the original clip, and motion payloads include `trajectory_region`. |
| `mode` | `string` | `"crop"` | `crop` (zoom into the union bbox), `highlight` (full frame with box + dim overlay), or `crop_and_concat` (original + per-frame person crop side-by-side; requires YOLO). |
| `expand` | `float` | `0.25` | Fractional outward expansion of the union bbox. |
| `auto_split_area` | `float` | `0.0` | When the union bbox covers more than this fraction of the frame, the current motion segment is cut early to prevent oversize ROIs. `0` disables early-split. |

##### `RecordingConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | Enable the continuous recorder branch (independent of motion). |
| `interval_seconds` (alias `interval`) | `int` | `60` | Duration of each recording segment. |
| `fps` | `int` | `15` | Recording output frame rate. |
| `retention_days` | `int` | `5` | Days to retain old recordings on disk. |

##### `HealthConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_failures` | `int` | `30` | Consecutive failure threshold that triggers the recovery strategy. |
| `recovery_strategy` | `string` | `"retry"` | `retry` (exponential backoff reconnect), `pause` (auto-pause), or `remove` (auto-unregister). |
| `backoff_base` | `float` | `2.0` | Base of the exponential backoff sequence, in seconds. |
| `backoff_max` | `float` | `120.0` | Upper bound on backoff delay. |

##### `KeepaliveConfig` (Phase 8)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `false` | Enable keepalive watchdog for this source. |
| `timeout_seconds` | `float` | `90.0` | Auto-pause when no keepalive arrives within this window. |
| `check_interval_seconds` | `float` | `10.0` | Watchdog polling interval. |

#### Example request body

```json
{
  "source_id":   "cam_child",
  "source_url":  "rtsp://localhost:8554/live/child",
  "webhook_url": "http://localhost:3101/events",
  "data_dir":    "/data/cam_child",
  "pipeline": {
    "motion":    { "diff_threshold": 15, "area_ratio": 0.005, "stable_frames": 45 },
    "segment":   { "max_duration": 10, "min_duration": 1.0 },
    "prefilter": {
      "enabled": true,
      "model_path": "/models/yolo11s.xml",
      "target_classes": ["person"],
      "detect_fps": 2.0,
      "device": "NPU"
    },
    "roi":       { "enabled": true, "mode": "crop", "expand": 0.25, "auto_split_area": 0.35 },
    "recording": { "enabled": true, "interval_seconds": 60, "retention_days": 5 },
    "health":    { "max_failures": 30, "recovery_strategy": "retry" },
    "keepalive": { "enabled": true, "timeout_seconds": 90.0, "check_interval_seconds": 10.0 }
  }
}
```

#### Response

| Case | Response 200 body |
|------|-------------------|
| Fresh registration | `{"status": "started", "source_id": "...", "source_url": "...", "data_dir": "..."}` |
| Same id already running (idempotent) | `{"status": "already_running", "source_id": "..."}` |
| Same id previously registered but not running | Fresh `started` response; the old bundle is torn down and rebuilt. |

Validation failures return `422` with the shape described in §5.2.

### 3.5 `DELETE /unregister_source`, `DELETE /sources/{source_id}`, `POST /sources/{source_id}/stop`

The three endpoints are semantically equivalent: stop the pipeline and the recorder, close the per-source webhook sink, and remove the bundle from the in-memory registry. **The source's `data_dir` is not deleted** — file retention is the MCP server's responsibility.

- `DELETE /unregister_source` — body form, `{"source_id": "..."}`.
- `DELETE /sources/{source_id}` — RESTful path form; used by the MCP server's startup reconciliation.
- `POST /sources/{source_id}/stop` — convenience form for clients that cannot issue `DELETE`.

**Response 200**:

```json
{ "status": "stopped", "source_id": "cam_child" }
```

**Response 404** when the source is not registered.

### 3.6 `POST /sources/{source_id}/restart`

Stop and start the pipeline (and the recorder, if present) while preserving the registration entry. The source bundle and the webhook sink are reused.

**Response 200**:

```json
{ "status": "restarted", "source_id": "cam_child" }
```

**Response 404** when the source is not registered.

### 3.7 `POST /sources/{source_id}/pause` and `/resume`

`/pause` transitions the pipeline to `paused`: frame capture continues in order to keep the RTSP connection alive, but motion detection and webhook emission are suspended. `/resume` returns the pipeline to `online`.

The response is idempotent: pausing a source that is `not_running` returns `{"status": "not_running"}` with HTTP 200.

**Response 200**:

```json
// pause
{ "status": "paused", "source_id": "cam_child" }

// resume
{ "status": "online", "source_id": "cam_child" }
```

**Response 404** when the source is not registered.

Both endpoints emit a `type="status"` webhook event with payload `{"status": "paused"}` or `{"status": "online"}`; see §4.4.

#### 3.7.1 Source Lifecycle State Machine

The `status` field returned by §3.3 evolves according to the following state machine, driven by the `StreamPipeline._run()` loop and the external control endpoints.

| status | Trigger | Terminal | Exit condition |
|--------|---------|----------|----------------|
| `connecting` | `_connect()` is attempting to open RTSP. | No (transient) | Success → `online`; failure → `error`. |
| `online` | RTSP connected and frames are flowing. | No (event-driven) | RTSP failure → `error` / `reconnecting`; `/pause` → `paused`. |
| `error` | A single RTSP read failed. | No (transient) | Enters the `reconnecting` backoff path. |
| `reconnecting` | Failure with `failure_count < max_failures`; backoff retry in progress. | No | Successful reconnect → `online`; failures reach `max_failures` → `unhealthy` → `recovery_strategy` branch. |
| `unhealthy` | Cumulative failures ≥ `max_failures`. | No (transient) | Depending on `recovery_strategy`: `retry` (continue backoff), `pause` → `paused`, `remove` → `removed`. |
| `paused` | `POST /pause`, `recovery_strategy=pause` triggered, or Phase 8 keepalive watchdog timeout. | **Yes** | Only `POST /resume` returns to `online`; the watchdog and health machinery do not auto-resume. |
| `removed` | `recovery_strategy=remove` triggered, or the source was unregistered. | Yes | The source is no longer in the registry; a fresh `POST /register_source` is required. |
| `stopped` | Graceful shutdown / `/stop`. | Yes | Same as `removed`. |

**Invariants**:

1. **`reconnecting` is not terminal.** `recovery_strategy=pause` does not pause the source on the first failure; VSA accumulates `failure_count` failures with exponential backoff, and only when `failure_count` reaches `max_failures` does the strategy fire. With defaults `max_failures=30, backoff_base=2.0, backoff_max=120.0` the backoff schedule is:

   ```
   failure_count   delay (s)   cumulative (s)
   1               2           2
   2               4           6
   3               8           14
   4               16          30
   5               32          62
   6               64          126
   7 …             120 (cap)   246, 366, 486, …
   30              120         → unhealthy → recovery_strategy
   ```

2. **`paused` is terminal.** The state persists across RTSP idle-disconnect and silent reconnects. If a source appears to leave `paused` on its own, an external `/resume` call is the cause (a lingering test script, another orchestrator, or a re-`register_source` teardown-and-rebuild).

3. **`failure_count` resets to zero on a successful reconnect** ([rtsp_monitor.py:231](../../videostream-analytics/stream_monitor/rtsp_monitor.py#L231)). Recovery from a transient RTSP glitch therefore restarts the failure budget from scratch.

To shorten the reproduction window for the `paused` transition during verification, hot-update the health block via §3.9:

```bash
curl -X PUT http://localhost:8999/sources/cam_demo/pipeline \
  -H "Content-Type: application/json" \
  -d '{"pipeline": {"health": {"max_failures": 3, "recovery_strategy": "pause", "backoff_base": 1.0, "backoff_max": 5.0}}}'
```

Kill the upstream RTSP producer afterwards; the source transitions to `paused` within roughly seven seconds and remains there.

State-machine source: [rtsp_monitor.py:222-259 `_run()`](../../videostream-analytics/stream_monitor/rtsp_monitor.py#L222-L259) and [rtsp_monitor.py:194-220 `_handle_unhealthy()`](../../videostream-analytics/stream_monitor/rtsp_monitor.py#L194-L220).

### 3.8 `POST /sources/{source_id}/keepalive` (Phase 8)

The MCP server calls this endpoint at a regular cadence (typically every 30 seconds) to prove liveness. VSA refreshes `last_keepalive_at` on the source; a background watchdog polls every `check_interval_seconds` and auto-pauses the source when the timestamp is older than `timeout_seconds`. Keepalive is disabled by default; the MCP server must set `pipeline.keepalive.enabled=true` at registration to activate it.

**Request**: body is ignored (`{}`, empty body, and arbitrary JSON are all accepted).

**Response 200**:

```json
{
  "status": "ok",
  "source_id": "cam_child",
  "last_keepalive_at": "2026-06-30T12:34:56.789012+00:00"
}
```

**Response 404** when the source is not registered.

Watchdog behaviour:

- The watchdog reuses the standard `pause_source()` path, which emits a `type=status, payload={status:paused}` webhook event.
- Watchdog-triggered pauses are terminal for the same reason `/pause` is; the MCP server must explicitly `/resume` the source. See §3.7.1.
- At registration, if `keepalive.enabled=true`, `last_keepalive_at` is initialised to the current time, granting a `timeout_seconds` grace period before the first heartbeat is required.

### 3.9 `PUT /sources/{source_id}/pipeline`

Hot-update pipeline configuration without unregistering the source.

The request body wraps a `PipelineConfig` object (§3.4):

```json
{
  "pipeline": {
    "motion": { "diff_threshold": 10 },
    "recording": { "enabled": false }
  }
}
```

Semantics are whole-sub-block replacement: any sub-block supplied is applied verbatim; omitted sub-blocks retain their current values. A change to `recording.enabled` creates or destroys the `ContinuousRecorder`; other changes are applied by stopping and restarting the pipeline.

**Response 200**:

```json
{ "status": "updated", "source_id": "cam_child" }
```

**Response 404** when the source is not registered; **response 422** on schema validation failure (§5.2).

---

## 4. Event Plane — VSA → Downstream Webhook

Every event produced by a running source is delivered as an HTTP POST to the configured webhook URL. The envelope shape has been aligned with the MCP `events-endpoint` since Phase 7 (see [mcp_webhook_event_api.md](./mcp_webhook_event_api.md) for the receiving contract).

### 4.1 Envelope

```json
{
  "sourceId":  "cam_child",
  "type":      "motion | recording | status",
  "timestamp": "2026-06-30T14:30:15",
  "payload":   { ... }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `sourceId` | `string` | The `source_id` used at registration (camelCase in the envelope). |
| `type` | `"motion" \| "recording" \| "status"` | Event category; determines the payload schema. |
| `timestamp` | `string` (ISO 8601, second precision, local timezone) | Time the event was emitted on VSA. |
| `payload` | `object` | Body specific to the `type`. |

> The system design (§9.2) references a `static` event type. The current VSA implementation does not emit it; motion / recording / status are the three types produced. `status` events are informational — MCP currently ignores unrecognized types.

### 4.2 `type=motion` payload

Emitted by [`_emit_segment`](../../videostream-analytics/stream_monitor/rtsp_monitor.py#L429-L488). A motion segment is only emitted after the underlying MP4 has been written; when prefilter is enabled, only clips with `prefilter_passed=1` are emitted (the file for a SKIP clip is deleted, no event is produced).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_file_path` | `string` | ✅ | Absolute path of the original motion clip, under `<data_dir>/motion_events/<YYYY-MM-DD>/`. |
| `summary_clip_input` | `string` | ✅ | Path of the clip to feed into the video-summary service. When prefilter passes and `pipeline.roi.enabled=true`, this points to `<stem>_input.mp4`; otherwise it equals `event_file_path`. |
| `start_time` | `string` (ISO 8601) | ✅ | Clip start time. |
| `end_time` | `string` (ISO 8601) | Optional | Clip end time. |
| `duration_seconds` | `float` | ✅ | Clip duration in seconds. |
| `prefilter_passed` | `0` or `1` | Optional | Present only when prefilter is enabled on this source. `0` clips are never emitted; see above. |
| `prefilter_classes` | `string` (JSON-encoded array) | Optional | Hit class names as a JSON string. |
| `prefilter_confidence` | `float` | Optional | Maximum detection confidence within the clip. |
| `trajectory_region` | `string` (`"[x0,y0,x1,y1]"`, normalized to [0,1]) | Optional | Phase 9. The union bbox accumulated by prefilter, serialised as a JSON string of four floats. |

### 4.3 `type=recording` payload

Emitted by [`ContinuousRecorder._record_loop`](../../videostream-analytics/stream_monitor/continuous_recorder.py#L157-L169) after each fixed-cadence recording segment is written to disk.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `recording_path` | `string` | ✅ | Absolute path of the recording, under `<data_dir>/recordings/<YYYY-MM-DD>/`. |
| `recording_start` | `string` (ISO 8601) | ✅ | Segment start time. |
| `recording_end` | `string` (ISO 8601) | ✅ | Segment end time. |
| `duration_seconds` | `float` | Optional | Actual segment duration; may differ slightly from `interval_seconds`. |
| `file_size_bytes` | `int` | Optional | File size in bytes. |

### 4.4 `type=status` payload

Emitted by [`_emit_status`](../../videostream-analytics/stream_monitor/rtsp_monitor.py#L490-L492) and various inline `_emit_envelope("status", ...)` call sites. The `payload.status` field takes one of the following values:

| Value | Emitted when | Additional fields |
|-------|--------------|-------------------|
| `paused` | `/pause`, watchdog auto-pause, or `recovery_strategy=pause`. | — |
| `online` | `/resume`, or successful reconnect. | — |
| `unhealthy` | Consecutive failures reach `max_failures`. | `reason`, e.g. `"rtsp_timeout"`. |
| `reconnecting` | Backoff retry between failures. | — |
| `stopped` | Source unregistered / shutdown. | — |

Example:

```json
{
  "sourceId":  "cam_child",
  "type":      "status",
  "timestamp": "2026-06-30T14:31:00",
  "payload":   { "status": "unhealthy", "reason": "rtsp_timeout" }
}
```

---

## 5. Error Responses

### 5.1 `404 Not Found`

Standard FastAPI `HTTPException(404)` used whenever the referenced source is not registered:

```json
{ "detail": "Source not found: cam_xxx" }
```

### 5.2 `422 Unprocessable Entity`

The custom [`RequestValidationError` handler](../../videostream-analytics/service.py#L107-L128) translates pydantic errors into a machine-readable form. `extra="forbid"` rejects unknown fields on all request models; the offending field names are collected into an `unknown_fields` array to help clients pinpoint the drift.

```json
{
  "detail": [
    { "type": "extra_forbidden", "loc": ["body", "rtsp_url"], "...": "..." },
    { "type": "extra_forbidden", "loc": ["body", "motion"], "...": "..." }
  ],
  "unknown_fields": ["rtsp_url", "motion"],
  "hint": "request body must match the nested-pipeline schema (source_id/source_url/webhook_url/data_dir/pipeline.{motion,segment,prefilter,recording,health})"
}
```

`unknown_fields` is populated only for `extra_forbidden` errors. Other `422` causes (missing required fields, type mismatches) populate `detail` but leave `unknown_fields` empty.

---

## 6. Data Directory Layout

VSA writes all per-source outputs under the resolved `data_dir`. The layout is stable and forms an implicit contract with the MCP server's cleanup job.

```
<data_dir>/
├── latest.jpg                          # Periodically overwritten snapshot; read by the MCP latest-frame resource.
├── motion_events/<YYYY-MM-DD>/
│   ├── <source_id>_HHMMSS.mp4          # Original motion clip (payload.event_file_path).
│   └── <source_id>_HHMMSS_input.mp4    # ROI-cropped clip (Phase 9; payload.summary_clip_input).
└── recordings/<YYYY-MM-DD>/
    └── <source_id>_HHMMSS.mp4          # Fixed-cadence recording segment (payload.recording_path).
```

Retention responsibilities:

- Old date directories under `motion_events/` and `recordings/` are pruned by the MCP server according to `storage.retention_days`.
- `latest.jpg` is atomically overwritten by VSA and does not require cleanup.
- Unregistering a source stops the pipeline but does not delete the `data_dir`.

---

## 7. Ports and Environment

| Env / Config | Default | Purpose |
|--------------|---------|---------|
| `server.host` / `server.port` | `0.0.0.0:8999` | HTTP bind address. |
| `webhook.url` (or env `WEBHOOK_URL`) | `http://localhost:18800/events` | Default webhook target; the per-source `webhook_url` field takes precedence. |
| `data_dir` (or env `RECORDINGS_DIR`) | `~/.smartbuilding/data` | Global root; the `data_dir` field in the register request takes precedence. |
| `VIDEOSTREAM_CONFIG` | `config/config.yaml` | Alternate configuration file path. |
| `OV_CACHE_DIR` | `/tmp/ov_cache` | OpenVINO model cache used by the YOLO prefilter. |

Ports used by the integration test harness and local verification recipes (see [vsa-gsg.md](../vsa-gsg.md)):

- `:8554` — MediaMTX RTSP server (upstream).
- `:8999` — VSA service (this document).
- `:9999` — Mock webhook receiver used by integration tests.
- `:3101` — Production MCP `events-endpoint` (replaces the mock in end-to-end scenarios).

---

## 8. Version History

| Phase | Highlights | Introduced |
|-------|------------|------------|
| Phase 7 | Nested `pipeline` request schema; renamed `rtsp_url` → `source_url`; dropped `use_case`; `/sources` returns a bare array; added `/sources/{id}/status`; nested webhook envelope. | §3.3, §3.4, §4 |
| Phase 8 | Keepalive endpoint and watchdog; `SourceStatus` gains `keepalive_enabled` and `last_keepalive_at`. | §3.8 |
| Phase 9 | `pipeline.roi` sub-block; `trajectory_region` in the motion payload; automatic `<clip>_input.mp4` production; `summary_clip_input` retargeting; `auto_split_area` early-split. | §3.4 (RoiConfig), §4.2 |

---

## 9. Verification

End-to-end verification recipes, including manual `V1`–`V12` `curl` walkthroughs, unit-test invocation, and integration-test invocation, live in [vsa-gsg.md](../vsa-gsg.md). Summary:

- Unit tests: `pytest tests/unit/ --timeout=60` — expected `185 passed`.
- Integration tests: `pytest tests/integration/ -m integration --timeout=300` — expected `27 passed` (requires MediaMTX, mock webhook, and ffmpeg producer).
- Manual verification (`V1`–`V12`) covers the `/health` probe, source registration, lifecycle transitions, motion / recording event delivery, health strategies, CLI, real MCP integration, keepalive, and trajectory + ROI crop.

---

## Appendix A: MCP Interoperability

Contract-level correspondence between the MCP server's outbound calls and the VSA endpoints defined here.

| MCP call | VSA endpoint | Status |
|----------|--------------|--------|
| `analyticsRegister` | `POST /register_source` | Aligned. |
| `analyticsSourceExists` | `GET /sources/{id}/status` | Aligned. |
| `analyticsDelete` | `DELETE /sources/{id}` | Aligned. |
| `analyticsPause` | `POST /sources/{id}/pause` | Aligned. |
| `analyticsResume` | `POST /sources/{id}/resume` | Aligned. |
| `analyticsListSources` | `GET /sources` | Aligned (bare array). |
| Keepalive sender loop | `POST /sources/{id}/keepalive` | VSA endpoint ready; the MCP-side `setInterval` producer is not yet wired. |
| Webhook receiver (`motion` / `recording` / `status`) | VSA `POST <webhook_url>` | Aligned envelope. |
| `latest-frame` resource | VSA writes `<data_dir>/latest.jpg` | VSA producer ready; the MCP-side resource handler still returns a stub. |
