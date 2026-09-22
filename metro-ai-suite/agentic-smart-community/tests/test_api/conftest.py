# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures for the documented HTTP API contract tests."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import types
import urllib.error
import urllib.request
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
    category=Warning,
)

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
VSA_ROOT = REPO_ROOT / "videostream-analytics"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _decode_response(response: Any) -> Any:
    raw = response.read().decode("utf-8")
    if not raw:
        return None
    if "text/event-stream" in response.headers.get("Content-Type", ""):
        data_lines = [line[6:] for line in raw.splitlines() if line.startswith("data: ")]
        return json.loads(data_lines[-1]) if data_lines else None
    return json.loads(raw)


def http_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], Any]:
    request_headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, dict(response.headers), _decode_response(response)
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), _decode_response(error)


class McpApiClient:
    """Small curl-equivalent client for MCP Streamable HTTP requests."""

    def __init__(self, url: str):
        self.url = url
        self.session_id: str | None = None
        self.request_id = 0

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json, text/event-stream"}
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        return headers

    def initialize(self) -> dict[str, Any]:
        status, headers, body = http_json(
            self.url,
            method="POST",
            headers=self.headers,
            body={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest-api", "version": "1.0"},
                },
            },
        )
        assert status == 200
        self.session_id = headers.get("mcp-session-id")
        assert self.session_id
        notify_status, _, _ = http_json(
            self.url,
            method="POST",
            headers=self.headers,
            body={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        assert notify_status in {200, 202}
        return body

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.request_id += 1
        status, _, body = http_json(
            self.url,
            method="POST",
            headers=self.headers,
            body={
                "jsonrpc": "2.0",
                "id": self.request_id + 1,
                "method": method,
                "params": params or {},
            },
        )
        assert status == 200
        assert isinstance(body, dict)
        return body

    def read_resource(self, uri: str) -> dict[str, Any]:
        response = self.request("resources/read", {"uri": uri})
        return json.loads(response["result"]["contents"][0]["text"])


class _MockExternalService(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        body: Any = [] if self.path == "/sources" else {"status": "ok"}
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


@pytest.fixture
def vsa_api() -> tuple[TestClient, MagicMock]:
    sys.path.insert(0, str(VSA_ROOT))
    original_source_worker = sys.modules.get("source_worker")
    source_worker = types.ModuleType("source_worker")
    source_worker.SourceManager = MagicMock  # type: ignore[attr-defined]
    sys.modules["source_worker"] = source_worker
    try:
        import service
        from shared.config import AppConfig

        manager = MagicMock()
        service._manager = manager
        # A real AppConfig: the register path reads `config.security` to
        # allowlist source_url schemes, so a MagicMock here would make every
        # scheme evaluate to "not allowed".
        client = TestClient(service.create_app(AppConfig()))
        yield client, manager
    finally:
        service._manager = None
        if original_source_worker is None:
            sys.modules.pop("source_worker", None)
        else:
            sys.modules["source_worker"] = original_source_worker
        sys.path.remove(str(VSA_ROOT))


@pytest.fixture(scope="session")
def mcp_api(tmp_path_factory: pytest.TempPathFactory) -> McpApiClient:
    dist_entry = REPO_ROOT / "packages" / "mcp-server" / "dist" / "index.js"
    if not dist_entry.exists():
        pytest.fail("MCP build output is missing; run `npm run build` before API tests")

    workdir = tmp_path_factory.mktemp("mcp-api")
    mcp_port = _free_port()
    events_port = _free_port()
    mock_server = ThreadingHTTPServer(("127.0.0.1", 0), _MockExternalService)
    mock_thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
    mock_thread.start()
    mock_url = f"http://127.0.0.1:{mock_server.server_port}"

    config_path = workdir / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                f"summary_service:\n  url: {mock_url}",
                f"vlm_service:\n  url: {mock_url}\n  model: mock-model",
                f"videostream_analytics:\n  url: {mock_url}",
                "keepalive:\n  enabled: false",
                "poll_interval_ms: 60000",
                f"mcp:\n  port: {mcp_port}",
                f"events_webhook:\n  port: {events_port}",
                "use_case_dict: {}",
            ]
        ),
        encoding="utf-8",
    )

    log_path = workdir / "mcp-server.log"
    log_file = log_path.open("w", encoding="utf-8")
    env = os.environ.copy()
    env.pop("SMART_COMMUNITY_ROUTER_URL", None)
    env.pop("SMART_COMMUNITY_OPENCLAW_GATEWAY_URL", None)
    env.pop("SMART_COMMUNITY_OPENCLAW_GATEWAY_TOKEN", None)
    env["SMART_COMMUNITY_DATA_DIR"] = str(workdir / "data")
    process = subprocess.Popen(
        ["node", str(dist_entry), "--http", "--config", str(config_path)],
        cwd=REPO_ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    health_url = f"http://127.0.0.1:{events_port}/health"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_file.flush()
            pytest.fail(f"MCP server exited during startup:\n{log_path.read_text()}")
        try:
            status, _, _ = http_json(health_url)
            if status == 200:
                break
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    else:
        process.terminate()
        pytest.fail("MCP server did not become ready within 15 seconds")

    client = McpApiClient(f"http://127.0.0.1:{mcp_port}/mcp")
    client.events_url = f"http://127.0.0.1:{events_port}"  # type: ignore[attr-defined]
    client.data_dir = workdir / "data"  # type: ignore[attr-defined]
    yield client

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    log_file.close()
    mock_server.shutdown()
    mock_server.server_close()
    mock_thread.join(timeout=5)