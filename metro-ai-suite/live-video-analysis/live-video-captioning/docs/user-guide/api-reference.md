# API Reference

The backend is a FastAPI application that serves REST APIs and an SSE stream for captions/metadata (via MQTT). System metrics (CPU, GPU, NPU, memory, power) are served separately by the bundled `metrics-manager` (`intel/metrics-manager`) over its own SSE stream.

## Interactive API docs

When the stack is running, FastAPI provides OpenAPI/Swagger UI at:

- `http://localhost:4173/docs`

(If you run the backend on a different host/port, adjust accordingly.)

## REST Endpoints

### Health & Capabilities

- `GET /api/health` - Liveness check (`{"status": "healthy"}`)
- `GET /api/capabilities` - Report host acceleration capability flags used by the UI (`has_gpu`, `has_npu`)

### Models

- `GET /api/vlm-models` - List available VLM models discovered under `ov_models/`
- `GET /api/detection-models` - List available object detection models discovered under `ov_detection_models/`

#### VLM Models Response Schema

```json
{
  "models": [
    {
      "name": "InternVL2-1B",
      "device": "cpu"
    }
  ]
}
```

#### Detection Models Response Schema

```json
{
  "models": ["yolov8s"]
}
```

### Cameras

- `GET /api/cameras` - List local capture-capable camera devices (`/dev/videoX`) and supported formats

#### Cameras Response Schema

```json
{
  "cameras": [
    {
      "device_path": "/dev/video0",
      "device_name": "Integrated Camera",
      "pixel_formats": ["MJPG", "YUYV"],
      "usable_formats": ["MJPG"],
      "has_usable_format": true
    }
  ]
}
```

### Captions & Alerts

- `POST /api/generate_captions_alerts` - Start a caption generation run for an RTSP stream or camera device
- `GET /api/generate_captions_alerts` - List all active caption generation runs
- `GET /api/generate_captions_alerts/{run_id}` - Get details of a specific caption generation run
- `GET /api/generate_captions_alerts/{run_id}/stream-ready` - Check whether the run's WebRTC stream is ready to display
- `DELETE /api/generate_captions_alerts/{run_id}` - Stop caption generation for a run

#### Start Run Request Schema (`POST /api/generate_captions_alerts`)

```json
{
  "rtspUrl": "rtsp://example.com/stream",
  "streamSourceType": "rtsp",
  "pipelineType": "non-detection",
  "prompt": "Describe what you see in one sentence.",
  "detectionModelName": "yolov8s",
  "detectionThreshold": 0.5,
  "modelName": "InternVL2-1B",
  "maxNewTokens": 70,
  "runName": "Lobby Camera",
  "frameRate": 5,
  "chunkSize": 1,
  "frameWidth": 1280,
  "frameHeight": 720,
  "vlmDevice": "cpu",
  "detectionDevice": "cpu",
  "includeRoiBoundingBox": false
}
```

Notes:
- `rtspUrl` accepts either an RTSP URL (`rtsp://`/`rtsps://`) or a Linux camera device path such as `/dev/video0`.
- `streamSourceType` accepts `rtsp` or `camera`.
- `pipelineType` accepts `detection` or `non-detection`.
- `maxNewTokens` is the request field; the run response uses `maxTokens`.

#### Run Response Schema

```json
{
  "runId": "string",
  "pipelineId": "string",
  "peerId": "string",
  "mqttTopic": "live-video-captioning",
  "status": "running",
  "modelName": "string",
  "vlmDevice": "cpu",
  "detectionDevice": "cpu",
  "pipelineName": "string",
  "runName": "string",
  "prompt": "string",
  "maxTokens": 100,
  "rtspUrl": "string",
  "frameRate": 5,
  "chunkSize": 1,
  "frameWidth": 1280,
  "frameHeight": 720
}
```

#### Stream Ready Response Schema (`GET /api/generate_captions_alerts/{run_id}/stream-ready`)

```json
{
  "runId": "string",
  "peerId": "string",
  "ready": false,
  "state": "queued",
  "error": false
}
```

Notes:
- `state` can be `queued`, `running`, another backend pipeline state string, or `null` when pipeline status is temporarily unreachable.
- `error` is `true` when the run is no longer in a healthy state and the stream will not become ready.

#### Stop Run Response Schema (`DELETE /api/generate_captions_alerts/{run_id}`)

```json
{
  "status": "stopped",
  "runId": "string"
}
```

## Streaming Endpoints

### Server-Sent Events (SSE)

- `GET /api/generate_captions_alerts/metadata-stream` - Multiplexed SSE stream for all active runs

The SSE stream provides real-time metadata received from MQTT for all active runs.

Inference metadata event envelope:

```json
{
  "runId": "string",
  "data": { /* pipeline inference result */ },
  "received_at": 1705432800.123
}
```

Heartbeat/status event (sent when no metadata arrives during the interval):

```json
{
  "type": "status",
  "runs": {
    "run-id-1": "running",
    "run-id-2": "error"
  }
}
```

The backend forwards only MQTT payloads containing inference `result` data in metadata events.

## Related docs

- [Get Started](./get-started.md)
- [Known Issues](./known-issues.md)
