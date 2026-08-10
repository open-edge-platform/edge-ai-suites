<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Tests

The default API suite validates the HTTP contracts documented under `docs/user-guide/get-started/`. It uses mocks for external model serving, RTSP streams, video workers, and filesystem-heavy processing, so no camera, VLM, or running Docker service is required.

## Environment setup

Create and activate the project-local Python environment from the `metro-ai-suite/agentic-smart-community` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r tests/requirements-api.txt
```

The MCP tests execute the compiled TypeScript server. Install the Node.js dependencies and build the workspaces before running the suite:

```bash
npm install
npm run build
```

## API test coverage

| Test module | API document | Test boundary |
|---|---|---|
| `test_api/test_mcp_api.py` | [api-reference-mcp.md](../docs/user-guide/get-started/api-reference-mcp.md) | Real MCP Streamable HTTP server and temporary SQLite database; external VSA, VLM, and summary services are mocked. |
| `test_api/test_mcp_subscription_api.py` | [api-reference-mcp-subscription.md](../docs/user-guide/get-started/api-reference-mcp-subscription.md) | Real MCP sessions, subscriptions, cursor reads, unsubscribe requests, and SSE connection setup. |
| `test_api/test_webhook_api.py` | [api-reference-mcp-webhook-event.md](../docs/user-guide/get-started/api-reference-mcp-webhook-event.md) | Real webhook endpoint and temporary SQLite database; validates motion, static, recording, and error requests. |
| `test_api/test_videostream_analytics_api.py` | [api-reference-videostream-analytics.md](../docs/user-guide/get-started/api-reference-videostream-analytics.md) | Real FastAPI routes with a mocked `SourceManager`; no RTSP, OpenCV, recorder, or worker threads. |
| `test_api/test_dashboard_api.py` | [api-reference-dashboard.md](../docs/user-guide/get-started/api-reference-dashboard.md) | Real dashboard HTTP routes with temporary SQLite/media data; validates monitor redaction, contained media access, full-clip preview, and OpenClaw configuration. |

Tests use free local ports and temporary directories. They do not connect to the default service ports or write to `~/.mcp-smartbuilding`.

## Run tests

Run the mock-based API suite:

```bash
source .venv/bin/activate
pytest -q tests/test_api
```

Run one API document's tests while developing:

```bash
pytest -q tests/test_api/test_mcp_api.py
pytest -q tests/test_api/test_mcp_subscription_api.py
pytest -q tests/test_api/test_webhook_api.py
pytest -q tests/test_api/test_videostream_analytics_api.py
pytest -q tests/test_api/test_dashboard_api.py
```

The API suite is intentionally separate from video-pipeline integration tests. Add tests that require real RTSP input, model serving, or Docker services to an opt-in integration suite rather than introducing those dependencies here.