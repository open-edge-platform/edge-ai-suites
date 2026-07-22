#!/usr/bin/env python3
"""Test Case 3: Tools (MCP call) — 通过 MCP stdio 协议启动 server，发送 tool calls，验证响应.

Uses JSON-RPC over stdin/stdout (newline-delimited JSON) to interact with the MCP server.
"""

import json
import sys
import subprocess
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import get_temp_dir, cleanup_dir, init_test_db, TestResult, REPO_ROOT

MCP_SERVER_ENTRY = REPO_ROOT / "packages" / "mcp-server" / "dist" / "index.js"


class MCPClient:
    """MCP stdio client using newline-delimited JSON."""

    def __init__(self, proc: subprocess.Popen):
        self.proc = proc
        self._id = 0

    def send(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        request = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            request["params"] = params
        msg = json.dumps(request) + "\n"
        self.proc.stdin.write(msg.encode())
        self.proc.stdin.flush()
        return self._read_response()

    def notify(self, method: str, params: dict | None = None):
        request = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            request["params"] = params
        msg = json.dumps(request) + "\n"
        self.proc.stdin.write(msg.encode())
        self.proc.stdin.flush()

    def _read_response(self) -> dict:
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("Server closed stdout")
        return json.loads(line.decode().strip())


def main():
    print("\n=== Test: Tools (MCP Protocol) ===\n")
    t = TestResult("Tools (MCP Protocol)")

    if not MCP_SERVER_ENTRY.exists():
        print(f"  ⚠ MCP Server not built at {MCP_SERVER_ENTRY}")
        print("  Run 'npm run build' first.")
        sys.exit(1)

    tmp = get_temp_dir("tools-mcp")
    db_path = str(tmp / "test.db")

    # Pre-populate DB
    conn = init_test_db(db_path)
    conn.execute(
        "INSERT INTO monitors (id, name, source_url, status, use_case_id) VALUES (?, ?, ?, ?, ?)",
        ("cam-01", "Test Cam", "rtsp://test", "online", "child_safety"),
    )
    conn.execute(
        "INSERT INTO alerts (source_id, event, severity, description, acked) VALUES (?, ?, ?, ?, ?)",
        ("cam-01", "child_jumping", "high", "Child jumped", 0),
    )
    conn.commit()
    conn.close()

    # Write temp config
    config_path = tmp / "config.yaml"
    config_path.write_text(f"""
db:
  path: {db_path}
summary_service:
  url: http://localhost:19999
videostream_analytics:
  url: http://localhost:19998
segments_dir: {tmp}/segments
poll_interval_ms: 60000
video_summary_max_concurrent: 1
""")

    # Start MCP server
    proc = subprocess.Popen(
        ["node", str(MCP_SERVER_ENTRY), "--config", str(config_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(1)

    if proc.poll() is not None:
        stderr = proc.stderr.read().decode()
        print(f"  ⚠ Server exited early. stderr:\n{stderr}")
        cleanup_dir(tmp)
        sys.exit(1)

    client = MCPClient(proc)

    try:
        # Initialize MCP session
        init_resp = client.send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        })
        t.check("result" in init_resp, "MCP initialize: returns result")
        t.check("serverInfo" in init_resp.get("result", {}), "MCP initialize: has serverInfo")

        server_info = init_resp.get("result", {}).get("serverInfo", {})
        t.check_equal(server_info.get("name"), "smartbuilding-video", "Server name correct")

        # Send initialized notification
        client.notify("notifications/initialized")
        time.sleep(0.2)

        # List tools
        tools_resp = client.send("tools/list", {})
        tools = tools_resp.get("result", {}).get("tools", [])
        tool_names = [tool["name"] for tool in tools]
        t.check(len(tools) >= 8, f"tools/list: returns {len(tools)} tools (expected ≥8)")
        t.check("smartbuilding_alert_query" in tool_names, "Has smartbuilding_alert_query tool")
        t.check("smartbuilding_monitor_ctl" in tool_names, "Has smartbuilding_monitor_ctl tool")
        t.check("smartbuilding_video_db" in tool_names, "Has smartbuilding_video_db tool")
        t.check("smartbuilding_use_case_validate" in tool_names, "Has smartbuilding_use_case_validate tool")

        # List resources
        resources_resp = client.send("resources/list", {})
        result = resources_resp.get("result", {})
        resources = result.get("resources", [])
        resource_templates = result.get("resourceTemplates", [])
        total = len(resources) + len(resource_templates)
        t.check(total >= 1, f"resources/list: returns {total} resources/templates")

        # Call tool: smartbuilding_alert_query
        alert_resp = client.send("tools/call", {
            "name": "smartbuilding_alert_query",
            "arguments": {"monitor_id": "cam-01", "status": "unacked"},
        })
        alert_content = alert_resp.get("result", {}).get("content", [])
        t.check(len(alert_content) > 0, "alert_query: returns content")
        alert_text = alert_content[0].get("text", "") if alert_content else ""
        t.check("child_jumping" in alert_text, "alert_query: contains expected alert event")

        # Call tool: smartbuilding_monitor_ctl list
        ctl_resp = client.send("tools/call", {
            "name": "smartbuilding_monitor_ctl",
            "arguments": {"action": "list"},
        })
        ctl_content = ctl_resp.get("result", {}).get("content", [])
        ctl_text = ctl_content[0].get("text", "") if ctl_content else ""
        t.check("cam-01" in ctl_text, "monitor_ctl list: contains cam-01")

        # Call tool: smartbuilding_video_db
        db_resp = client.send("tools/call", {
            "name": "smartbuilding_video_db",
            "arguments": {"query": "SELECT COUNT(*) as count FROM monitors"},
        })
        db_content = db_resp.get("result", {}).get("content", [])
        db_text = db_content[0].get("text", "") if db_content else ""
        t.check("count" in db_text, "video_db: raw query returns count")

        # Call tool: smartbuilding_use_case_validate (pass)
        validate_resp = client.send("tools/call", {
            "name": "smartbuilding_use_case_validate",
            "arguments": {
                "use_case_name": "child_safety",
                "prompt": "Output EVENT, SEVERITY, DESC for the video",
                "required_fields": ["event", "severity", "desc"],
            },
        })
        validate_content = validate_resp.get("result", {}).get("content", [])
        validate_text = validate_content[0].get("text", "") if validate_content else ""
        t.check("passed" in validate_text.lower(), "use_case_validate: valid prompt passes")

        # Call tool: smartbuilding_use_case_validate (fail)
        validate_fail_resp = client.send("tools/call", {
            "name": "smartbuilding_use_case_validate",
            "arguments": {
                "use_case_name": "child_safety",
                "prompt": "Tell me what you see",
                "required_fields": ["event", "severity", "desc"],
            },
        })
        validate_fail_content = validate_fail_resp.get("result", {}).get("content", [])
        validate_fail_text = validate_fail_content[0].get("text", "") if validate_fail_content else ""
        t.check("failed" in validate_fail_text.lower() or "Missing" in validate_fail_text, "use_case_validate: missing fields reported")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    cleanup_dir(tmp)
    passed = t.summary()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
