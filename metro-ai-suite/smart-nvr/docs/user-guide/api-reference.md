# API Reference

**Version:** 1.0.0 | **Prerequisites:** stack must be running (`source setup.sh start`)

Interactive Swagger UI: `http://<HOST_IP>:8000/docs`

## Endpoints

### Cameras & Events

| Method | Path | Parameters | Description |
|--------|------|-----------|-------------|
| `GET` | `/cameras` | — | List all configured cameras and their tracked object types |
| `GET` | `/events` | query: `camera`\* | List events for a specific camera from Frigate |

### Summary & Search

| Method | Path | Parameters | Description |
|--------|------|-----------|-------------|
| `GET` | `/summary/{camera_name}` | path: `camera_name`; query: `start_time`\*, `end_time`\*, `download` (bool, default `false`) | Request an AI-generated summary for a clip; routes to VSS (Video Search Service) |
| `GET` | `/summary-status/{summary_id}` | path: `summary_id` | Poll summary job status or retrieve result |
| `GET` | `/search-embeddings/{camera_name}` | path: `camera_name`; query: `start_time`\*, `end_time`\*, `download` (bool, default `false`) | Generate search embeddings for semantic video search |

### Rules

Rules map object detection labels to actions per camera.

| Method | Path | Parameters | Description |
|--------|------|-----------|-------------|
| `GET` | `/rules/` | — | List all configured rules |
| `POST` | `/rules/` | body: [Rule](#rule) | Add a new rule — `400` if rule ID already exists |
| `GET` | `/rules/{rule_id}` | path: `rule_id` | Get a specific rule — `404` if not found |
| `DELETE` | `/rules/{rule_id}` | path: `rule_id` | Delete a rule — `404` if not found |
| `GET` | `/rules/responses/` | — | Get summary results for all non-search rules |
| `GET` | `/rules/search-responses/` | — | Get search results for all rules with action `add to search` |

### Watchers

Per-camera directory watchers that detect new Frigate events. State persists in Redis across restarts; in-memory overrides reflect runtime changes.

| Method | Path | Parameters | Description |
|--------|------|-----------|-------------|
| `POST` | `/watchers/enable` | body: [CameraWatcherRequest](#camerawatcherrequest) | Enable/disable directory watchers for one or more cameras — `503` if VSS Search service is unreachable |
| `GET` | `/watchers/enable` | — | Alias for `GET /watchers/mapping` |
| `GET` | `/watchers/mapping` | — | Get current watcher enable/disable state (merged Redis + runtime) |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service health check |
| `GET` | `/health` | Detailed health status |

\* _Required parameter_

Endpoints that accept path, query, or body parameters return `422 Unprocessable Entity` on invalid input — see [HTTPValidationError](#httpvalidationerror).

---

## Schemas

### Rule

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique rule ID |
| `label` | string | Yes | Detection label (e.g. `person`, `car`) |
| `action` | string | Yes | Action to trigger (e.g. `add to search`) |
| `camera` | string \| null | No | Camera scope; `null` = all cameras |
| `source` | string \| null | No | Optional source identifier |
| `count` | int \| null | No | Internal field; read-only |

### CameraWatcherRequest

```json
{ "cameras": [{ "<camera_name>": true }, { "<other_camera>": false }] }
```

`cameras` — array of objects, each mapping one camera name → `true` (enable) or `false` (disable).

### CameraWatcherUpdateResponse

| Field | Type | Description |
|-------|------|-------------|
| `mapping` | object | Persisted map of camera name → enabled flag |
| `enabled` | string[] | Currently enabled cameras |
| `disabled` | string[] | Currently disabled cameras |

### CameraWatcherMappingResponse

| Field | Type | Description |
|-------|------|-------------|
| `mapping` | object | Current map of camera name → enabled flag (Redis + runtime) |
| `warning` | string (optional) | Set if Redis lookup failed |

### HTTPValidationError

```json
{ "detail": [{ "loc": ["body", "field"], "msg": "string", "type": "string" }] }
```

---

## OpenAPI Spec

```bash
# Live (requires running stack)
curl http://<HOST_IP>:8000/openapi.json

# From repo
cat docs/user-guide/api-docs/smart-nvr.yaml
```

Import into [Swagger Editor](https://editor.swagger.io/), [Bruno](https://www.usebruno.com/), or [Insomnia](https://insomnia.rest/) for offline exploration.

---

## Related Docs

- [Get Started](./get-started.md)
- [Troubleshooting](./troubleshooting.md)
