# API Reference

The backend is a FastAPI application that serves REST APIs, an SSE stream for captions/metadata (via MQTT), and WebSocket endpoints for metrics.

## Interactive API docs

When the stack is running, FastAPI provides OpenAPI/Swagger UI at:

- `http://localhost:4173/docs`

(If you run the backend on a different host/port, adjust accordingly.)

## REST Endpoints

### Models

- `GET /api/vlm-models` — List available VLM models discovered under `ov_models/`
- `GET /api/detection-models` - List available object detection models discovered under `ov_detection_models/`

### Pipelines

- `GET /api/pipelines` — List available pipeline configurations

### Runs

- `POST /api/runs` — Start a new captioning pipeline (publishes to MQTT)
- `GET /api/runs` — List active runs
- `GET /api/runs/{run_id}` — Get run details (includes `mqttTopic` field)
- `DELETE /api/runs/{run_id}` — Stop a pipeline

#### Run Response Schema

```json
{
  "runId": "string",
  "pipelineId": "string",
  "peerId": "string",
  "mqttTopic": "live-video-captioning/{runId}",
  "modelName": "string",
  "pipelineName": "string",
  "runName": "string",
  "prompt": "string",
  "maxTokens": 100,
  "rtspUrl": "string"
}
```

## Streaming Endpoints

### Server-Sent Events (SSE)

- `GET /api/runs/metadata-stream` — Multiplexed SSE stream for all active runs

The SSE stream provides real-time metadata received from the MQTT broker. Each message is an envelope containing:

```json
{
  "runId": "string",
  "data": { /* pipeline inference result */ },
  "received_at": 1705432800.123
}
```

### WebSockets

- `ws://localhost:4173/ws/collector` — Metrics collector connection (single connection)
- `ws://localhost:4173/ws/clients` — Metrics broadcast to dashboard clients (multiple connections)

## Related docs

- [Get Started](./get-started.md)
- [Known Issues](./known-issues.md)
