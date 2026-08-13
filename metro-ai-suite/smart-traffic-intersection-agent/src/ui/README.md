# Smart Traffic Intersection Agent — UI

A real-time dashboard for a traffic intersection. It streams live
intersection data from the agent backend over a WebSocket and renders camera feeds, traffic density,
weather, alerts, and system telemetry.

## How It Runs

The UI is packaged inside the `traffic-agent` container and started automatically alongside the backend
(see `../docker-entrypoint.sh`). For normal usage, deploy the whole agent via Docker Compose from the
project root — the dashboard is then served on port `7860`.

Run it standalone only for development. It requires the agent backend to be reachable so the WebSocket
has data to stream.

## Quick Start (standalone)

```bash
# From this directory (src/ui). Python 3.13 is used by the container image.
pip install -r requirements.txt

# Point the UI at a running backend WebSocket, then launch.
export AGENT_API_URL="ws://localhost:8081/api/v1/traffic/current/ws"
python app.py
```

Open http://localhost:7860 in a browser.

## Minimum Configuration

All settings are read from environment variables (see `config.py`). Defaults work when the backend and
Metrics Manager run on `localhost`.

| Variable              | Default                                              | Purpose                                  |
| --------------------- | ---------------------------------------------------- | ---------------------------------------- |
| `AGENT_API_URL`       | `ws://localhost:8081/api/v1/traffic/current/ws`      | Backend WebSocket for live intersection data |
| `METRICS_MANAGER_URL` | `http://localhost:9090`                              | Metrics Manager base URL (system telemetry) |
| `AGENT_UI_HOST`       | `0.0.0.0`                                             | Bind host                                |
| `AGENT_UI_HOSTPORT`   | `7860`                                               | Bind port                                |
| `UI_THEME`            | `light`                                              | `light` or `dark`                        |
| `APP_TITLE`           | `Smart Traffic Intersection Agent`                   | Browser/page title                       |

## Dashboard Panels

- **Camera Feeds** — live images from the intersection cameras.
- **Traffic Summary** — per-direction and total vehicle density.
- **Environmental** — temperature, humidity, wind, and precipitation.
- **Alerts** — VLM analysis output and severity-tagged alerts.
- **System Info** — intersection location, ID, and last-update time.
- **System Telemetry** — CPU/RAM/GPU charts streamed from Metrics Manager over SSE.
