# API Reference

The backend is a FastAPI application that serves REST APIs under the `/api` prefix for stream lifecycle management, alert retrieval, frame-registry inspection, and runtime UI configuration.

## Interactive API docs

When the stack is running, FastAPI provides OpenAPI/Swagger UI at:

- `http://localhost:9100/docs`

If the backend is exposed on a different host or port, adjust accordingly.

## REST Endpoints

### Health Check

- `GET /api/health` - Liveness and basic runtime status

#### Health Response Schema

```json
{
	"status": "healthy",
	"streams_active": 0,
	"uptime_seconds": 12.4,
	"timestamp": "2026-09-07T10:20:30.123456+00:00"
}
```

### Runtime Config

- `GET /api/runtime-config.js` - Browser runtime configuration as JavaScript (`window.RUNTIME_CONFIG = {...};`)

This endpoint is consumed by the UI to resolve WebRTC signaling and metrics service URLs.

### Streams

- `GET /api/streams` - List all active streams and live processing state
- `POST /api/streams` - Create/start a new stream pipeline
- `DELETE /api/streams/{stream_id}` - Stop and remove a stream pipeline

#### Create Stream Request Schema (`POST /api/streams`)

```json
{
	"stream_id": "camera-lobby",
	"url": "rtsp://example.com/stream",
	"alert_prompt": "Look for visible fire and describe its location.",
	"deep_analyzer_prompt": "Review the clip for evidence of fire and summarize what happens."
}
```

Notes:

- `url` is required.
- `alert_prompt` and `deep_analyzer_prompt` are required.
- `stream_id` defaults to `default` if omitted/empty.
- `url` must use `rtsp://` or `rtsps://`. HTTP and HTTPS URLs are not supported.
- `stream_id`, when provided, must contain 1-64 letters, digits, underscores, or hyphens.
- Each prompt is limited to 4096 characters.

#### Create Stream Response Schema

```json
{
	"status": "added",
	"stream_id": "camera-lobby"
}
```

#### List Streams Response Schema (`GET /api/streams`)

```json
{
	"streams": [
		{
			"stream_id": "camera-lobby",
			"url": "rtsp://example.com/stream",
			"alert_prompt": "Look for visible fire and describe its location.",
			"deep_analyzer_prompt": "Review the clip for evidence of fire and summarize what happens.",
			"publishing": true,
			"codec": "h264",
			"resolution": "576x320",
			"reconnect_count": 0,
			"whep_path": "/camera-lobby/whep",
			"caption": "Yes",
			"caption_ts": 1757240432.117,
			"ttft_ms": 73.2,
			"tpot_ms": 18.7,
			"throughput_tps": 54.1,
			"alert_count": 3
		}
	]
}
```

#### Delete Stream Response Schema (`DELETE /api/streams/{stream_id}`)

```json
{
	"status": "removed",
	"stream_id": "camera-lobby"
}
```

### Alerts

- `GET /api/streams/{stream_id}/alerts` - Paginated alert listing (`limit`, `offset` query params)
- `GET /api/streams/{stream_id}/alerts/{frame_id}` - Alert detail record
- `GET /api/streams/{stream_id}/alerts/{frame_id}/thumbnail` - Alert thumbnail image (`image/jpeg`)
- `GET /api/streams/{stream_id}/alerts/{frame_id}/video` - Alert video clip (`video/mp4`)

#### List Alerts Response Schema (`GET /api/streams/{stream_id}/alerts`)

```json
{
	"total": 2,
	"alerts": [
		{
			"frame_id": "9dd96a2f-17b9-41a0-a1c5-e3f8f76b07a7",
			"trigger_caption": "Yes",
			"confirmed": true,
			"thumbnail_url": "/api/streams/camera-lobby/alerts/9dd96a2f-17b9-41a0-a1c5-e3f8f76b07a7/thumbnail",
			"uploaded_at": "2026-09-07T10:17:40.100000+00:00"
		}
	]
}
```

#### Alert Detail Response Schema (`GET /api/streams/{stream_id}/alerts/{frame_id}`)

```json
{
	"stream_id": "camera-lobby",
	"frame_id": "9dd96a2f-17b9-41a0-a1c5-e3f8f76b07a7",
	"trigger_caption": "Yes",
	"confirmed": true,
	"thumbnail_url": "/api/streams/camera-lobby/alerts/9dd96a2f-17b9-41a0-a1c5-e3f8f76b07a7/thumbnail",
	"description": "Short multi-frame analysis summary.",
	"metrics": {
		"ttft_ms": 70.2,
		"throughput_tps": 50.4
	},
	"model": "Qwen3-VL-8B-Instruct",
	"device": "GPU",
	"uploaded_at": "2026-09-07T10:17:40.100000+00:00",
	"video_url": "/api/streams/camera-lobby/alerts/9dd96a2f-17b9-41a0-a1c5-e3f8f76b07a7/video"
}
```

#### Alerts Query Parameters

- `limit` (default `20`, min `1`, max `100`)
- `offset` (default `0`, min `0`)

### Frame Registry

- `GET /api/registry/stats` - Registry totals and per-stream counts
- `GET /api/registry/stream/{stream_id}` - Latest frame records for one stream (`limit` query param)
- `GET /api/registry/frame/{frame_id}` - Lookup a specific frame record by UUID

#### Registry Stats Response Schema (`GET /api/registry/stats`)

```json
{
	"total": 134,
	"per_stream_capacity": 500,
	"per_stream": {
		"camera-lobby": 84,
		"camera-parking": 50
	}
}
```

#### Registry Records Response Schema

Returned by `GET /api/registry/stream/{stream_id}` (`limit` defaults to `50`).

```json
{
	"records": [
		{
			"frame_id": "9dd96a2f-17b9-41a0-a1c5-e3f8f76b07a7",
			"stream_id": "camera-lobby",
			"segment_path": "segments/camera-lobby_segment_0012.mp4",
			"pts_seconds": 173.2,
			"created_ts": 1757240432.117
		}
	]
}
```

#### Registry Frame Detail Response Schema (`GET /api/registry/frame/{frame_id}`)

```json
{
	"frame_id": "9dd96a2f-17b9-41a0-a1c5-e3f8f76b07a7",
	"stream_id": "camera-lobby",
	"rtsp_url": "rtsp://example.com/stream",
	"segment_path": "segments/camera-lobby_segment_0012.mp4",
	"pts_seconds": 173.2,
	"created_ts": 1757240432.117
}
```

## Streaming Endpoints

The stack also includes two related streaming surfaces outside of FastAPI:

- WebRTC playback signaling and media via MediaMTX WHEP (`/{stream_id}/whep`)
- System metrics via the bundled `metrics-manager` (`intel/metrics-manager`) SSE endpoint (`/metrics/stream`)

### WebRTC Playback (MediaMTX WHEP)

- `POST /{stream_id}/whep`

This endpoint is served by MediaMTX, not FastAPI. The backend returns `whep_path` from `GET /api/streams`, and the UI completes SDP offer/answer negotiation against this WHEP path.

### System Metrics SSE (metrics-manager)

- `GET /metrics/stream`

This endpoint is served by the `metrics-manager` sidecar service (default port `9090`), not by the FastAPI backend. The UI subscribes with `EventSource` for live CPU/GPU/NPU/memory/power telemetry.

Example URL:

- `http://localhost:9090/metrics/stream`

Related metrics capability endpoint:

- `GET /api/v1/capabilities?profile=minimal`

## Error Behavior

Typical API error codes:

- `400` - invalid request payload or malformed path/query values
- `422` - request body violates schema limits (for example, a prompt exceeds 4096 characters)
- `404` - stream, alert, thumbnail, video, or frame record not found
- `409` - stream conflict (for example, duplicate `stream_id`)

## Related docs

- [Get Started](./get-started.md)
- [Known Issues](./known-issues.md)
