# API Reference

**Version: 1.0.0**

The VMS Adapter Plugin exposes REST API at `http://localhost:8085/v1`. Interactive API
documentation (Swagger UI) is available at `http://localhost:8085/docs` when the backend
is running.

## Health

| **Method** | **Path**            | **Description**                          |
|------------|---------------------|------------------------------------------|
| `GET`      | `/v1/health`        | Liveness probe                           |
| `GET`      | `/v1/ready`         | Readiness (DB + VMS + Analytics App checks) |
| `GET`      | `/v1/config/status` | Loaded config and uptime                 |

## Cameras

| **Method** | **Path**                              | **Description**                      |
|------------|---------------------------------------|--------------------------------------|
| `GET`      | `/v1/cameras`                         | List all persisted cameras           |
| `GET`      | `/v1/cameras/{camera_id}`             | Get a single camera                  |
| `POST`     | `/v1/cameras/discover`                | Sync cameras from all VMS shims      |
| `POST`     | `/v1/cameras/enable`                  | Enable or disable a camera           |
| `GET`      | `/v1/cameras/{camera_id}/live-stream` | Get live RTSP stream URL             |
| `GET`      | `/v1/cameras/{camera_id}/clip`        | Get clip URL for a time range        |

## Analytics Apps

The generic Analytics App API handles all AI analytics integrations with a consistent
lifecycle: discover, start, list, stop, and stream results.

| **Method** | **Path**                                              | **Description**                                 |
|------------|-------------------------------------------------------|-------------------------------------------------|
| `GET`      | `/v1/analytics-apps/discover`                         | List all registered Analytics Apps with schema  |
| `GET`      | `/v1/analytics-apps/{app_id}/schema`                  | Get live JSON Schema for start parameters       |
| `POST`     | `/v1/analytics-apps/{app_id}/runs`                    | Start a pipeline run                            |
| `GET`      | `/v1/analytics-apps/{app_id}/runs`                    | List active runs                                |
| `GET`      | `/v1/analytics-apps/{app_id}/runs/{run_id}`           | Get run status                                  |
| `DELETE`   | `/v1/analytics-apps/{app_id}/runs/{run_id}`           | Stop a run                                      |
| `GET`      | `/v1/analytics-apps/{app_id}/results/stream`          | SSE proxy of live results                       |
| `GET`      | `/v1/analytics-apps/{app_id}/options/{option_type}`   | Dropdown options (models, pipelines)            |

Currently registered `app_id` values: `live_captioning`, `dls_vision`.

## Events and Sessions

| **Method** | **Path**                        | **Description**                          |
|------------|---------------------------------|------------------------------------------|
| `GET`      | `/v1/events/timeline`           | Paginated metadata-event timeline        |
| `POST`     | `/v1/analysis/results`          | Async result callback from Analytics App |
| `GET`      | `/v1/sessions`                  | List analytics sessions                  |
| `GET`      | `/v1/sessions/{session_id}`     | Get session details                      |
| `POST`     | `/v1/vms/{name}/register`       | Register a VMS with the plugin           |
