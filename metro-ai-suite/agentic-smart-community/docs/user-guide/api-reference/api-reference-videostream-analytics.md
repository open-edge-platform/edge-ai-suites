# Videostream Analytics HTTP API Reference

The Videostream Analytics microservice (VSA) is the standalone RTSP-processing service that pulls camera streams, runs motion detection and optional NPU-based YOLO prefiltering, cuts qualifying segments into MP4 clips, and pushes the resulting events to a configured webhook consumer (typically the MCP server).

---

## 1. Service Overview

| Item | Value |
|------|-------|
| Service name | `videostream-analytics` |
| Framework | FastAPI (served by uvicorn with the strict `h11` HTTP parser — malformed request lines are rejected with a single `400` and a closed connection, never reaching routing) |
| Default bind | `127.0.0.1:8999` (`server.host` / `server.port` in `config.yaml`) |
| Default webhook target | `http://localhost:3101/events`, overridable by the `WEBHOOK_URL` environment variable or by the `webhook_url` field in each `register_source` request |
| Content-Type | `application/json` for normal API requests and responses; protocol-level parser errors may be returned directly by uvicorn |
| Character encoding | UTF-8 |
| Auth | None. Because every endpoint (register/delete a source, rewrite `webhook_url`, change the pipeline) is unauthenticated, the default bind is loopback so the kernel refuses connections from other hosts. A cross-host deployment must set `server.host` explicitly **and** put its own authentication in front of the service. |

The service is a long-running single process. Each registered source spawns background threads for the motion pipeline, an optional continuous recorder, and a shared keepalive watchdog. Multiple sources coexist in a single VSA instance.

---

## 2. Endpoint Summary

| Method | Path | Purpose | See |
|--------|------|---------|-----|
| `GET`    | `/health` | Liveness probe. | §3.1 |
| `GET`    | `/capabilities/prefilter` | Report the deployed prefilter model and available devices. | §3.2 |
| `GET`    | `/sources` | List all registered sources (bare array). | §3.3 |
| `GET`    | `/sources/{source_id}` | Get source status. | §3.4 |
| `GET`    | `/sources/{source_id}/status` | Alias of `/sources/{source_id}`; the MCP server calls this to check for existence. | §3.4 |
| `POST`   | `/register_source` | Register and start a new source. | §3.5 |
| `DELETE` | `/sources/{source_id}` | Unregister a source. | §3.6 |
| `POST`   | `/sources/{source_id}/stop` | Stop and unregister (equivalent to `DELETE`). | §3.6 |
| `POST`   | `/sources/{source_id}/restart` | Stop and start the pipeline while preserving the bundle. | §3.7 |
| `POST`   | `/sources/{source_id}/pause` | Pause the pipeline; keep the source registered. | §3.8 |
| `POST`   | `/sources/{source_id}/resume` | Resume a paused pipeline. | §3.8 |
| `POST`   | `/sources/{source_id}/keepalive` | Refresh the keepalive timestamp. | §3.9 |
| `PUT`    | `/sources/{source_id}/pipeline` | Hot-update supported pipeline configuration. | §3.10 |

---

## 3. Control Plane

All responses are JSON. The service follows a small, uniform status-code convention:

| Status | Meaning |
|--------|---------|
| `200 OK` | The requested state change succeeded, or the idempotent no-op response (`already_running`, `not_running`) is returned. |
| `400 Bad Request` | The request is schema-valid but cannot be honoured — a `data_dir` outside the permitted roots, a disallowed `source_url` scheme, inverted effective segment durations. See §5.3. |
| `404 Not Found` | The referenced `source_id` is not registered. |
| `409 Conflict` | Another request is mid-registration for the same `source_id`. Retry after that registration completes. See §5.4. |
| `422 Unprocessable Entity` | The request body failed schema validation (missing required fields, unknown fields due to `extra="forbid"`, or wrong types). See §5.2. |
| `503 Service Unavailable` | A server-side dependency is missing (currently: ffmpeg absent from `PATH`). See §5.5. |
| `500 Internal Server Error` | Reserved for genuine defects; any request reaching this is a bug. See §5.6. |

### 3.1 `GET /health`

Liveness probe.

**Request**: no body.

**Response 200**:

```json
{ "status": "ok", "service": "videostream-analytics" }
```

### 3.2 `GET /capabilities/prefilter`

Report the prefilter capabilities of the deployed model.

**Request**: no body.

**Response 200**:

```json
{
  "enabled": true,
  "model_path": "/models/yolo11s.xml",
  "class_names": ["person", "car"],
  "labels_source": "embedded",
  "available_devices": ["CPU", "GPU"]
}
```

`labels_source` is `embedded` when the model exposes authoritative labels. It
may be `fallback_coco` or `unavailable`; clients must not treat those values as
an authoritative model class list. When the configured model is unavailable,
`class_names` is an empty array.

### 3.3 `GET /sources`

List all registered sources.

**Request**: no body.

**Response 200**: a bare JSON array of `SourceStatus` objects (see §3.4). The array is `[]` when no sources are registered.

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

> **Note:** The `/sources` response is intentionally a **bare array**, not `{"sources": [...]}`.

### 3.4 `GET /sources/{source_id}` and `GET /sources/{source_id}/status`

Return the status of a single source. Both paths dispatch to the same handler and return identical bodies. The MCP server's `analyticsSourceExists` probe calls the `/status` variant.

**Path parameter**: `source_id` — the id used at registration.

**Response 200** (`SourceStatus`):

| Field | Type | Description |
|-------|------|-------------|
| `source_id` | `string` | Same as the path parameter. |
| `source_url` | `string` | The stream URL supplied at registration. |
| `data_dir` | `string` | Absolute path of the per-source output directory. |
| `status` | `string` | Pipeline lifecycle state. See §3.8.1 for the full state machine. |
| `running` | `boolean` | Whether the pipeline background thread is alive. |
| `recording_enabled` | `boolean` | Whether the continuous recorder is enabled for this source. |
| `health` | `object` | Health sub-object; see below. |
| `keepalive_enabled` | `boolean` | Whether keepalive watchdog is enabled for this source. |
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

### 3.5 `POST /register_source`

Register a new source and start its pipeline. Idempotent: re-registering an id that is already running returns `{"status": "already_running"}` without changes.

#### Request body (`RegisterSourceRequest`, `extra="forbid"`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_id` | `string` | ✅ | Unique identifier. Must match `^[A-Za-z0-9_-]{1,128}$` — the same pattern the dashboard applies to `monitor_id` — because it becomes a directory name under `data_dir`. |
| `source_url` | `string` | ✅ | Stream URL from which VSA pulls. Non-empty, at most 2048 characters, no control characters. The scheme must be in `security.allowed_source_schemes` (default `rtsp`/`rtsps`/`http`/`https`; `file` only when `security.allow_file_source` is enabled) — the URL is handed to `ffmpeg -i` verbatim, and ffmpeg can otherwise be pointed at local files (`file:`/`concat:`/`subfile:`). Out-of-allowlist schemes are rejected with 400. |
| `webhook_url` | `string \| null` | Optional | Overrides the destination for this source's events. Must be an `http`/`https` URL with a host and no embedded credentials. The current API does not restrict the host or resolved IP, so this server-side callback must only be accepted from trusted callers. Falls back to the global `webhook.url` when omitted. |
| `data_dir` | `string \| null` | Optional | Absolute path for this source's outputs, which must resolve inside `config.data_dir` or one of `config.allowed_data_roots` (400 otherwise, including via symlink). Falls back to `<config.data_dir>/<source_id>/` when omitted. |
| `pipeline` | `PipelineConfig` | Optional | Nested pipeline configuration; see below. |

The schema is `extra="forbid"`: any field not listed above is rejected with `422`, and its name appears in the `unknown_fields` array of the error body (see §5.2).

#### `PipelineConfig`

The nested pipeline object (`extra="forbid"`). Every sub-block is optional. Explicit fields in a
supplied sub-block are merged onto the corresponding `defaults.<sub_block>`; omitted fields retain
their defaults, so a request may override only the values that need to differ.

The values below are the defaults in the shipped `videostream-analytics/config/config.yaml` used
by `setup_docker.sh`. A deployment that loads a different `VIDEOSTREAM_CONFIG` inherits the
`defaults` blocks from that file instead.

| Sub-block | Model | Purpose |
|-----------|-------|---------|
| `motion` | `MotionConfig` | Frame-difference motion detector parameters. |
| `segment` | `SegmentConfig` | Motion-clip segmentation parameters. |
| `static` | `StaticConfig` | Quiet-period close-out event parameters. |
| `prefilter` | `PrefilterConfig` | Optional NPU / OpenVINO™ YOLO prefilter. |
| `roi` | `RoiConfig` | ROI crop and trajectory-region emission. |
| `recording` | `RecordingConfig` | Fixed-cadence continuous recording branch. |
| `health` | `HealthConfig` | RTSP failure-handling policy. |
| `keepalive` | `KeepaliveConfig` | Keepalive protocol. |

##### `MotionConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | When `false`, the motion detection path is skipped entirely. |
| `diff_threshold` | `int` | `15` | Per-pixel frame-difference threshold. |
| `area_ratio` | `float` | `0.005` | Minimum fraction of frame area required to declare motion. |
| `stable_frames` | `int` | `45` | Consecutive static frames required to end a motion event. |

##### `SegmentConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_duration` | `float` | `10.0` | Hard ceiling on segment length, in seconds. Must be > 0. |
| `min_duration` | `float` | `1.0` | Cut-frequency guard: forced cuts (ROI early-split) are rejected while the running segment is younger than this. Finished segments are always emitted — short motion-end tails are never discarded. Must be ≥ 0, and must not exceed the *effective* `max_duration` after merging with the per-source defaults (otherwise 400). |

##### `StaticConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | Emit a `static` event when a qualifying quiet period closes. |
| `min_duration` | `float` | `3.0` | Suppress quiet periods shorter than this many seconds. |

##### `PrefilterConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | Enable OpenVINO™ YOLO prefilter on motion clips. |
| `model_path` | `string` | Generated from `PREFILTER_MODEL` | Absolute path to the OpenVINO™ `.xml` model. When supplied in a request it must resolve (after symlinks) inside a permitted model root — the directory of `defaults.prefilter.model_path`, plus anything in `security.allowed_model_roots` — otherwise the request is rejected with 400. Omit it to inherit the deployment default, which is what the MCP server does; the stored value is the resolved path. |
| `target_classes` | `array<string>` | `["person"]` | Class labels that count as a hit. |
| `min_confidence` | `float` | `0.4` | Minimum detection confidence. Must be within 0–1. |
| `min_frames_hit` | `int` | `1` | Number of hits within a clip required for PASS. Must be ≥ 1. |
| `detect_fps` | `float` | `2.0` | YOLO inference rate; inference does not run on every frame. Must be > 0. |
| `device` | `string` | `"NPU"` | OpenVINO™ device (`CPU`, `GPU`, `NPU`). |
| `long_side` | `int` | `0` | Resize the frame's longest side before inference; `0` disables resizing. Must be ≥ 0. |

##### `RoiConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `false` | When enabled, prefilter PASS produces a `<clip>_input.mp4` next to the original clip, and motion payloads include `trajectory_region`. |
| `mode` | `"crop" \| "highlight" \| "crop_and_concat"` | `"crop"` | `crop` (zoom into the union bbox), `highlight` (full frame with box + dim overlay), or `crop_and_concat` (original + per-frame person crop side-by-side; requires YOLO). Any other value is rejected with 422. |
| `expand` | `float` | `0.25` | Fractional outward expansion of the union bbox. Must be ≥ 0. |
| `auto_split_area` | `float` | `0.0` | When the union bbox covers more than this fraction of the frame, the current motion segment is cut early to prevent oversize ROIs. `0` disables early-split. Must be within 0–1. |

##### `RecordingConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | Enable the continuous recorder branch (independent of motion). |
| `interval_seconds` (alias `interval`) | `int` | `60` | Duration of each recording segment. Must be within 1–3600. |
| `fps` | `int` | `15` | Recording output frame rate. Must be within 1–120. |

##### `HealthConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_failures` | `int` | `30` | Consecutive failure threshold that triggers the recovery strategy. Must be ≥ 1. |
| `recovery_strategy` | `"retry" \| "pause" \| "remove"` | `"retry"` | `retry` (exponential backoff reconnect), `pause` (auto-pause), or `remove` (auto-unregister). Any other value is rejected with 422. |
| `backoff_base` | `float` | `2.0` | Base of the exponential backoff sequence, in seconds. Must be ≥ 1. |
| `backoff_max` | `float` | `120.0` | Upper bound on backoff delay. Must be > 0. |

##### `KeepaliveConfig`

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
    "recording": { "enabled": true, "interval_seconds": 60 },
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

Concurrent registrations for the same id are refused rather than queued: while one registration is in flight, others receive `409` (§5.4). Re-registering a stopped source is not affected — that is a sequential operation.

Validation failures return `422` with the shape described in §5.2.

### 3.6 `DELETE /sources/{source_id}`, `POST /sources/{source_id}/stop`

The two endpoints are semantically equivalent: stop the pipeline and the recorder, close the per-source webhook sink, and remove the bundle from the in-memory registry. **The source's `data_dir` is not deleted** — file retention is the MCP server's responsibility.

- `DELETE /sources/{source_id}` — RESTful path form; used by the MCP server's startup reconciliation.
- `POST /sources/{source_id}/stop` — convenience form for clients that cannot issue `DELETE`.

**Response 200**:

```json
{ "status": "stopped", "source_id": "cam_child" }
```

**Response 404** when the source is not registered.

### 3.7 `POST /sources/{source_id}/restart`

Stop and start the pipeline (and the recorder, if present) while preserving the registration entry. The source bundle and the webhook sink are reused.

**Response 200**:

```json
{ "status": "restarted", "source_id": "cam_child" }
```

**Response 404** when the source is not registered.

### 3.8 `POST /sources/{source_id}/pause` and `/resume`

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

#### 3.8.1 Source Lifecycle State Machine

The `status` field returned by §3.4 evolves according to the following state machine, driven by the `StreamPipeline._run()` loop and the external control endpoints.

| status | Trigger | Terminal | Exit condition |
|--------|---------|----------|----------------|
| `connecting` | `_connect()` is attempting to open RTSP. | No (transient) | Success → `online`; failure → `error`. |
| `online` | RTSP connected and frames are flowing. | No (event-driven) | RTSP failure → `error` / `reconnecting`; `/pause` → `paused`. |
| `error` | A single RTSP read failed. | No (transient) | Enters the `reconnecting` backoff path. |
| `reconnecting` | Failure with `failure_count < max_failures`; backoff retry in progress. | No | Successful reconnect → `online`; failures reach `max_failures` → `unhealthy` → `recovery_strategy` branch. |
| `unhealthy` | Cumulative failures ≥ `max_failures`. | No (transient) | Depending on `recovery_strategy`: `retry` (continue backoff), `pause` → `paused`, `remove` → `removed`. |
| `paused` | `POST /pause`, `recovery_strategy=pause` triggered, or keepalive watchdog timeout. | **Yes** | Only `POST /resume` returns to `online`; the watchdog and health machinery do not auto-resume. |
| `removed` | `recovery_strategy=remove` triggered, or the source was unregistered. | Yes | The source is no longer in the registry; a fresh `POST /register_source` is required. |
| `stopped` | Graceful shutdown / `/stop`. | Yes | Same as `removed`. |

**Invariants**:

1. **`reconnecting` is not terminal.** `recovery_strategy=pause` does not pause the source on the first failure; VSA accumulates `failure_count` failures with exponential backoff, and only when `failure_count` reaches `max_failures` does the strategy fire. With defaults `max_failures=30, backoff_base=2.0, backoff_max=120.0` the backoff schedule is:

   ```text
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

3. **`failure_count` resets to zero on a successful reconnect.** Recovery from a transient RTSP glitch therefore restarts the failure budget from scratch.

To shorten the reproduction window for the `paused` transition during verification, hot-update the health block via §3.10:

```bash
curl -X PUT http://localhost:8999/sources/cam_demo/pipeline \
  -H "Content-Type: application/json" \
  -d '{"pipeline": {"health": {"max_failures": 3, "recovery_strategy": "pause", "backoff_base": 1.0, "backoff_max": 5.0}}}'
```

Kill the upstream RTSP producer afterwards; the source transitions to `paused` within roughly seven seconds and remains there.

### 3.9 `POST /sources/{source_id}/keepalive`

This endpoint is intended for an MCP keepalive sender to call at a regular cadence (typically every 30 seconds) to prove liveness. VSA refreshes `last_keepalive_at` on the source; a background watchdog polls every `check_interval_seconds` and auto-pauses the source when the timestamp is older than `timeout_seconds`. Keepalive is disabled by default. The current MCP-side keepalive sender is not wired, so an external caller must send these requests and the source must have `pipeline.keepalive.enabled=true` at registration to activate the watchdog.

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

- The watchdog reuses the standard `pause_source()` path. The source becomes `paused` in the VSA control plane and is visible through `GET /sources/{source_id}/status`; VSA does not emit status webhook events.
- Watchdog-triggered pauses are terminal for the same reason `/pause` is; the MCP server must explicitly `/resume` the source. See §3.8.1.
- At registration, if `keepalive.enabled=true`, `last_keepalive_at` is initialised to the current time, granting a `timeout_seconds` grace period before the first heartbeat is required.

### 3.10 `PUT /sources/{source_id}/pipeline`

Hot-update pipeline configuration without unregistering the source.

The request body wraps a `PipelineConfig` object (§3.5):

```json
{
  "pipeline": {
    "motion": { "diff_threshold": 10 },
    "recording": { "enabled": false }
  }
}
```

Explicit fields in the supported supplied sub-blocks are merged onto the source's current
configuration; omitted fields and sub-blocks retain their current values. The endpoint currently
supports `motion`, `segment`, `prefilter`, `roi`, `recording`, and `health`. Although `static` and
`keepalive` are accepted by the shared `PipelineConfig` schema, this endpoint does not apply those
two blocks; configure them when registering the source instead. A change to `recording.enabled`
creates or destroys the `ContinuousRecorder`; other supported changes are applied by stopping and
restarting the pipeline.

**Response 200**:

```json
{ "status": "updated", "source_id": "cam_child" }
```

**Response 404** when the source is not registered; **response 422** on schema validation failure (§5.2).

---

## 4. Event Plane — VSA → Downstream Webhook

Every event produced by a running source is delivered as an HTTP POST to the configured webhook URL. The envelope shape is aligned with the MCP `events-endpoint` (see [MCP Webhook Event API Reference](./api-reference-mcp-webhook-event.md) for the receiving contract).

### 4.1 Envelope

```
{
  "sourceId":  "cam_child",
  "type":      "motion | static | recording",
  "timestamp": "2026-06-30T14:30:15",
  "payload":   { ... }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `sourceId` | `string` | The `source_id` used at registration (camelCase in the envelope). |
| `type` | `"motion" \| "static" \| "recording"` | Event category; determines the payload schema. |
| `timestamp` | `string` (ISO 8601, second precision, local timezone) | Time the event was emitted on VSA. |
| `payload` | `object` | Body specific to the `type`. |

### 4.2 `type=motion` payload

A motion segment is emitted only after the underlying MP4 has been written. When prefilter is enabled, only clips with `prefilter_passed=1` are emitted; the file for a skipped clip is deleted and no event is produced.

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
| `trajectory_region` | `string` (`"[x0,y0,x1,y1]"`, normalized to [0,1]) | Optional | The union bbox accumulated by prefilter, serialised as a JSON string of four floats. |

### 4.3 `type=static` payload

A static event is emitted when a quiet period closes and its duration meets `pipeline.static.min_duration`. Static events record activity timing but do not create a video-summary task.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start_time` | `string` (ISO 8601) | ✅ | Quiet-period start time. |
| `end_time` | `string` (ISO 8601) | Optional | Quiet-period end time. |
| `duration_seconds` | `float` | ✅ | Quiet-period duration in seconds. |

### 4.4 `type=recording` payload

A recording event is emitted after each fixed-cadence recording segment is written to disk.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `recording_path` | `string` | ✅ | Absolute path of the recording, under `<data_dir>/recordings/<YYYY-MM-DD>/`. |
| `recording_start` | `string` (ISO 8601) | ✅ | Segment start time. |
| `recording_end` | `string` (ISO 8601) | ✅ | Segment end time. |
| `duration_seconds` | `float` | Optional | Actual segment duration; may differ slightly from `interval_seconds`. |
| `file_size_bytes` | `int` | Optional | File size in bytes. |

---

## 5. Error Responses

### 5.1 `404 Not Found`

Standard FastAPI `HTTPException(404)` used whenever the referenced source is not registered:

```json
{ "detail": "Source not found: cam_xxx" }
```

### 5.2 `422 Unprocessable Entity`

Validation errors use a machine-readable response format. Unknown fields are rejected on all request models and collected into an `unknown_fields` array to help clients pinpoint the drift.

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

`unknown_fields` is populated only for `extra_forbidden` errors. Other `422` causes (missing required fields, type mismatches, out-of-range numbers, values outside a closed set, a `source_id` that does not match `^[A-Za-z0-9_-]{1,128}$`, a relative `data_dir`, a non-HTTP `webhook_url`) populate `detail` but leave `unknown_fields` empty.

### 5.3 `400 Bad Request`

Returned when the request is schema-valid but the business layer cannot honour it — a `data_dir` outside the permitted roots, an unwritable output directory, or segment durations that are inverted once merged with the per-source defaults.

```json
{
  "detail": {
    "error": "invalid_request",
    "reason": "PermissionError",
    "operation": "register_source"
  }
}
```

`reason` is the exception class name only. The underlying message is written to the service log rather than the response, because it routinely contains absolute server paths and this API is unauthenticated.

### 5.4 `409 Conflict`

Returned only by `POST /register_source`: another request is already mid-registration for the same `source_id`. Refusing is deliberate — the alternative is queueing, which would park the caller through a potential 10–20 second teardown of the previous bundle. The client should wait for the in-flight registration to settle and retry.

```json
{ "detail": { "error": "registration_in_progress", "source_id": "cam_child" } }
```

### 5.5 `503 Service Unavailable`

Returned when a server-side dependency is missing — currently only `ffmpeg` absent from `PATH`, which the `copy` recording backend requires. This is an environment defect, not a client error, so it is deliberately distinguished from `400`.

```json
{ "detail": { "error": "dependency_unavailable", "operation": "register_source" } }
```

### 5.6 `500 Internal Server Error`

Reserved for genuine defects. Any request that produces a `500` is a bug: user input reaches either a deliberate `4xx` or a successful response. The body carries no server-side detail; the traceback goes to the log.

```json
{ "error": "internal_error" }
```

---

## 6. Data Directory Layout

VSA writes all per-source outputs under the resolved `data_dir`. The layout is stable and forms an implicit contract with the MCP server's cleanup job.

```text
<data_dir>/
├── latest.jpg                          # Periodically overwritten snapshot; read by smart_community_scene_query.
├── motion_events/<YYYY-MM-DD>/
│   ├── <source_id>_HHMMSS.mp4          # Original motion clip (payload.event_file_path).
│   └── <source_id>_HHMMSS_input.mp4    # ROI-cropped clip (payload.summary_clip_input).
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
| `server.host` / `server.port` | `127.0.0.1:8999` | HTTP bind address. Loopback by default because the service is unauthenticated; widen only for a cross-host deployment that adds its own authentication. |
| `webhook.url` (or env `WEBHOOK_URL`) | `http://localhost:3101/events` | Default webhook target; the per-source `webhook_url` field takes precedence. |
| `data_dir` | `~/.mcp-smart-community/segments` | Global segment root; the `data_dir` field in the register request takes precedence, but only if it resolves inside this root (or `allowed_data_roots`) — otherwise the request is rejected with 400. |
| `allowed_data_roots` | `[]` (empty) | Additional roots a request-supplied `data_dir` may live under. Empty means `data_dir` is the only permitted root, which is what the standard deployment needs since MCP sends `<SMART_COMMUNITY_DATA_DIR>/segments/<monitor_id>` and `data_dir` is derived from the same variable. Set this only when the segment tree is mounted elsewhere. |
| `security.allowed_source_schemes` | `["rtsp", "rtsps", "http", "https"]` | Schemes accepted in a register `source_url`. The URL is handed to `ffmpeg -i` verbatim, and ffmpeg can open local files and exotic inputs without this gate. |
| `security.allow_file_source` | `false` | Also allow `file://` sources. Enable only for offline evaluation against sample clips on disk; in any shared deployment it is an arbitrary-file-read. |
| `security.ffmpeg_protocol_whitelist` | `[file, crypto, rtp, udp, tcp, tls, rtsp, rtsps, http, https]` | Passed to ffmpeg as `-protocol_whitelist` — a second gate inside ffmpeg itself, so an input that slips past the scheme check still cannot be opened. `file` and `crypto` are required by the segment muxer's own output handling. |
| `security.allowed_model_roots` | `[]` (empty) | Additional roots a request-supplied `prefilter.model_path` may live under, on top of the directory holding `defaults.prefilter.model_path`. Empty means that one directory is the only permitted root — enough for the standard deployment, since neither the MCP server nor the API test suite ever sends `model_path`. A request-supplied path reaches `read_model()` both during validation and in the running pipeline, so leaving it unconfined on an unauthenticated API is a file-existence oracle plus an arbitrary-file-parse primitive. Set this only for a deployment that genuinely switches models over the API. |
| `SMART_COMMUNITY_DATA_DIR` | `~/.mcp-smart-community` | Overrides the platform data root; VSA writes under its `segments/` subdirectory. |
| `VIDEOSTREAM_CONFIG` | `config/config.yaml` | Alternate configuration file path. |
| `PREFILTER_MODEL` | `~/models/openvino/yolo11s/FP16/yolo11s.xml` | OpenVINO™ prefilter XML. `setup_docker.sh` validates the XML/BIN pair before startup and prepares the static YOLO11s IR automatically when it is missing. The model must be under `MODEL_DIR`, which is mounted read-only into the container. |
| `VIDEOSTREAM_CONFIG_FILE` | Generated by `setup_docker.sh` | Host-side runtime configuration mounted at `/app/config/config.yaml` by Docker Compose. It is generated from the tracked default with `defaults.prefilter.model_path` set to the absolute `PREFILTER_MODEL` path. |
| `OV_CACHE_DIR` | `/tmp/ov_cache` | OpenVINO™ model cache used by the YOLO prefilter. |

Ports used by the service and local verification recipes:

- `:8554` — MediaMTX RTSP server (upstream).
- `:8999` — VSA service (this document).
- `:9999` — Mock webhook receiver used by integration tests.
- `:3101` — Production MCP `events-endpoint` (replaces the mock in end-to-end scenarios).

---

## 8. Verification

Use the following test suites for unit and integration verification:

- Unit tests: `pytest tests/unit/ --timeout=60` — expected `210 passed`.
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
