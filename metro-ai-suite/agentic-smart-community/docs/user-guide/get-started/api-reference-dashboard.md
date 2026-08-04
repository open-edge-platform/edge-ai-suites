<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Dashboard API Reference

The MCP server hosts the dashboard and its same-origin API on port 3100. The browser never receives Router/OpenClaw credentials or monitor `sourceUrl` values.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/dashboard/config` | Return sanitized Router, chat, and media capability states. |
| `GET` | `/api/monitors` | List runtime monitors without source URLs. |
| `GET` | `/api/tasks?monitor_id=&date=&limit=` | Return task activity with optional event and alert details. |
| `GET` | `/api/reports?monitor_id=&date=` | Return reports overlapping the selected date. |
| `POST` | `/api/reports/generate` | Generate a configured report for a monitor. |
| `GET` | `/api/stats?monitor_id=&date=` | Return task/report token totals and activity counts. |
| `GET` | `/api/router/stats` | Return `not_configured`, `unavailable`, or configured Router data. |
| `POST` | `/api/router/stats/reset` | Reset configured Router statistics. |
| `GET` | `/api/monitors/:id/live-stream` | Stream server-generated H.264 fragmented MP4 from an RTSP monitor. |
| `GET` | `/api/monitors/:id/snapshot` | Return `latest.jpg` with no-store caching. |
| `GET` | `/api/tasks/:id/clip?monitor_id=` | Return an owned MP4 clip with HTTP Range support. |
| WebSocket | `/api/chat` | Proxy the OpenClaw control protocol when configured. |

IDs are limited to letters, numbers, underscores, and hyphens. Dates use `YYYY-MM-DD`; task limits are bounded. Invalid input returns `400`, missing monitor-owned media returns `404`, unsupported non-RTSP live sources return `422`, and capacity limits return `429` or `503`.

## Media security and resources

The server resolves media paths canonically beneath `segments/<monitor_id>` and rejects directory traversal, symbolic-link escapes, missing files, and cross-monitor task access. RTSP URLs are read only from the database. The ffmpeg process uses an argument array without a shell.

One ffmpeg session is shared per monitor. Client count, session count, initialization data, stderr, browser append queues, and buffered playback duration are bounded. The final disconnect starts an idle shutdown; server shutdown terminates all sessions. Slow clients are disconnected instead of accumulating an unbounded queue.

## Optional integrations

Set `SMARTBUILDING_ROUTER_URL` for Router statistics. Set both `SMARTBUILDING_OPENCLAW_GATEWAY_URL` and `SMARTBUILDING_OPENCLAW_GATEWAY_TOKEN` for chat. These values are server-side environment variables and do not belong in `config.yaml`.

The API has no end-user authentication. Bind it to loopback or a trusted network, or place it behind an authenticated reverse proxy for shared deployments.