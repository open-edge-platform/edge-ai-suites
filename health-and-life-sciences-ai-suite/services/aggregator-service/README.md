
# Aggregator Service (Python)

This service aggregates vitals and pose data from backend workloads and exposes
them to the web UI via Server‑Sent Events (SSE). It also proxies system
metrics from the metrics‑service.

Main responsibilities:

- Consume vital streams from DDS‑Bridge via gRPC.
- Consume 3D pose frames via gRPC.
- Poll the AI‑ECG backend over HTTP.
- Broadcast all events to UI clients over a single SSE endpoint.
- Proxy platform and utilization metrics from the metrics‑service.

---

## Running the service

### Option 1: Docker (recommended)

From this directory:

```bash
docker build -t hl-aggregator-service .

docker run --rm \
  --network host \
  -e WORKLOAD_TYPE=mdpnp \
  -e METRICS_SERVICE_URL=http://localhost:9000 \
  hl-aggregator-service
```

This starts:

- HTTP / SSE API on port `8001`.
- gRPC server on port `50051`.

### Option 2: docker-compose (suite integration)

From the top‑level suite directory, use the provided compose file which wires
aggregator‑service to dds‑bridge, mdpnp, ai‑ecg, and metrics‑service:

```bash
docker compose up aggregator-service
```

---

## Configuration

Environment variables:

- `WORKLOAD_TYPE` (default: `mdpnp`)
  - Label used in outgoing events for the MDPnP vital workload.
- `METRICS_SERVICE_URL` (default: `http://localhost:9000`)
  - Base URL of the metrics‑service that aggregator proxies to.

---

## HTTP / SSE API

### `GET /events` — Server‑Sent Events stream

Streams all real‑time events to the UI as SSE.

- Method: `GET`
- URL: `/events`
- Query parameters:
  - `workloads` (optional): comma‑separated list of workload types to
    subscribe to. Examples: `ai-ecg`, `mdpnp`, `3d-pose`. If omitted, all
    workloads are streamed.
- Response:
  - Content‑Type: `text/event-stream`
  - Each SSE message has a single `data:` line whose value is a JSON object.

Common envelope for all events:

```json
{
  "workload_type": "<ai-ecg|mdpnp|3d-pose|rppg>",
  "event_type": "<waveform|numeric|pose3d>",
  "timestamp": 1769354498005,   // milliseconds since epoch
  "payload": { ... }            // workload‑specific body
}
```

#### Example: Vital waveform (e.g., ECG lead II from MDPnP)

```json
{
  "workload_type": "mdpnp",
  "event_type": "waveform",
  "timestamp": 1769354498005,
  "payload": {
    "device_id": "LRnWdqwkmuZWcKcJR3tG71yZtRkpWNMgy6SV",
    "metric": "MDC_ECG_LEAD_II",
    "value": 0.0,
    "waveform": [0.12, 0.15, 0.10],
    "waveform_frequency_hz": 200
  }
}
```

#### Example: Vital numeric (e.g., heart rate from MDPnP)

```json
{
  "workload_type": "mdpnp",
  "event_type": "numeric",
  "timestamp": 1769354500456,
  "payload": {
    "device_id": "DwJR5TAbuoL48uiytUWFffIg972gkpzxpHza",
    "metric": "MDC_ECG_HEART_RATE",
    "value": 72.0
  }
}
```

#### Example: AI‑ECG waveform

```json
{
  "workload_type": "ai-ecg",
  "event_type": "waveform",
  "timestamp": 1769354498005,
  "payload": {
    "device_id": "ecg-device-1",
    "metric": "ECG_LEAD_II",
    "waveform": [0.01, 0.02, 0.03],
    "waveform_frequency_hz": 200,
    "inference": {
      "rhythm": "sinus",
      "confidence": 0.98
    }
  }
}
```

#### Example: 3D pose frame

```json
{
  "workload_type": "3d-pose",
  "event_type": "pose3d",
  "timestamp": 1769354500456,
  "payload": {
    "source_id": "camera-1",
    "people": [
      {
        "person_id": 1,
        "joints_2d": [{ "x": 0.5, "y": 0.3 }],
        "joints_3d": [{ "x": 0.1, "y": 0.2, "z": 0.3 }],
        "confidence": [0.9]
      }
    ]
  }
}
```

---

### `GET /metrics` — metrics summary (proxy)

Proxies to `GET /metrics` on the metrics‑service and returns time‑series
utilization data.

- Method: `GET`
- URL: `/metrics`
- Response (shape):

```json
{
  "cpu_utilization": [["2026-01-28T11:09:28.671", 12.3]],
  "gpu_utilization": [],
  "memory": [["2026-01-28T11:09:28.671", 32.0, 12.3, 19.7, 38.4]],
  "power": [["2026-01-28T11:09:28.671", 5.1, 2.2]],
  "npu_utilization": [["2026-01-28T11:09:28.671", 23.4]]
}
```

Notes:

- `cpu_utilization`: `[timestamp_iso, usage_percent]` samples.
- `gpu_utilization`: reserved for GPU/SPU metrics (may be empty).
- `memory`: `[timestamp_iso, total_gb, used_gb, free_gb, usage_percent]`.
- `power`: `[timestamp_iso, package0_watts, package1_watts, ...]`.
- `npu_utilization`: `[timestamp_iso, usage_percent]` from NPU logs.

### `GET /platform-info` — platform configuration (proxy)

- Method: `GET`
- URL: `/platform-info`
- Response (shape):

```json
{
  "Processor": "Intel(R) Core(TM) Ultra 7 155H",
  "NPU": "Intel AI Boost",
  "iGPU": "Intel Arc Graphics",
  "Memory": "32 GB",
  "Storage": "1 TB"
}
```

### `GET /memory` — latest memory snapshot (proxy)

- Method: `GET`
- URL: `/memory`
- Response (shape, when available):

```json
{
  "total_kib": 32859780.0,
  "used_kib": 12345678.0,
  "usage_percent": 37.5,
  "raw": "Mem:  32859780 12345678 ..."
}
```

If no memory data is available from metrics‑service, this endpoint returns
HTTP 404.

---

## gRPC services

Aggregator exposes the following gRPC services on port `50051` for internal
use by DDS‑Bridge, MDPnP, and pose workloads (see proto files under `proto/`).

### `VitalService.StreamVitals` (bi‑directional streaming)

- Service: `VitalService` (from `vital.proto`)
- Method: `rpc StreamVitals (stream Vital) returns (google.protobuf.Empty)`
- Used by DDS‑Bridge / MDPnP to push vital data into the aggregator.
- For each `Vital` message, aggregator:
  - Distinguishes waveform vs numeric metrics.
  - Optionally aggregates numeric values over a time window.
  - Broadcasts the result on the `/events` SSE stream.

### `PoseService.PublishPose`

- Service: `PoseService` (from `pose.proto`)
- Method: `rpc PublishPose (PoseFrame) returns (Ack)`
- Used by 3D pose workloads to send pose frames to the aggregator.
- Aggregator converts each `PoseFrame` into a JSON payload and broadcasts it
  on the `/events` SSE stream with `workload_type = "3d-pose"`.

