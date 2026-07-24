#!/usr/bin/env python3
"""Tests for smartbuilding_monitor_ctl — register_source state matrix.

Requires:
  - MCP server running: node packages/mcp-server/dist/index.js --config demo/config.demo.yaml --http
  - Mock analytics server: python tests/mock/videostream-analytics/mock_server.py --port 8999

Run:
  python tests/mcp-tools/monitor-ctl/test_monitor_ctl.py

Each test case resets state (DB rows, analytics registry, MCP server worker) between runs
via the unregister action and direct DB manipulation.
"""

import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tests" / "dev-mcp-server"))
from conftest import TestResult  # type: ignore

MCP_URL = os.environ.get("MCP_URL", "http://localhost:3100/mcp")
ANALYTICS_URL = os.environ.get("ANALYTICS_URL", "http://localhost:8999")
DATA_DIR = os.environ.get("SMARTBUILDING_DATA_DIR", str(Path.home() / ".mcp-smartbuilding"))
DB_PATH = os.path.join(DATA_DIR, "smartbuilding.db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mcp_call(tool: str, params: dict) -> dict:
    """Call an MCP tool via HTTP and return the result content as parsed JSON."""
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool, "arguments": params},
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(MCP_URL, data=data, method="POST",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if "error" in body:
        raise RuntimeError(f"MCP error: {body['error']}")
    content = body.get("result", {}).get("content", [{}])
    text = content[0].get("text", "{}") if content else "{}"
    return json.loads(text)


def analytics_get(path: str) -> dict | None:
    try:
        with urllib.request.urlopen(f"{ANALYTICS_URL}{path}", timeout=5) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def analytics_source_exists(monitor_id: str) -> bool:
    return analytics_get(f"/sources/{monitor_id}/status") is not None


def db_get_monitor(monitor_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, name, source_url, status, use_case_id FROM monitors WHERE id=?", (monitor_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return dict(zip(["id", "name", "source_url", "status", "use_case_id"], row))


def db_delete_monitor(monitor_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM monitors WHERE id=?", (monitor_id,))
    conn.commit()
    conn.close()


def cleanup(monitor_id: str) -> None:
    """Best-effort cleanup: unregister via MCP (stops worker + analytics + DB)."""
    try:
        mcp_call("smartbuilding_monitor_ctl", {"action": "unregister", "monitor_id": monitor_id})
    except Exception:
        pass
    # Fallback: direct DB delete in case MCP server is not running
    try:
        db_delete_monitor(monitor_id)
    except Exception:
        pass


def check_mcp_reachable(t: TestResult) -> bool:
    try:
        mcp_call("smartbuilding_monitor_ctl", {"action": "list"})
        return True
    except Exception as e:
        t.check(False, f"MCP server reachable at {MCP_URL}: {e}")
        return False


def check_analytics_reachable(t: TestResult) -> bool:
    try:
        analytics_get("/health")
        return True
    except Exception as e:
        t.check(False, f"Mock analytics reachable at {ANALYTICS_URL}: {e}")
        return False


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

BASE_PARAMS = {
    "action": "register_source",
    "source_url": "rtsp://localhost:8554/live/test",
    "use_case_id": "child_safety",
    "video_summary_task": "child_safety_monitor",
    "webhook_url": "http://localhost:3101/events",
}


def test_fresh_register(t: TestResult, monitor_id: str = "test_fresh") -> None:
    """❌/❌/❌ — fresh DB + fresh analytics → full register."""
    cleanup(monitor_id)
    result = mcp_call("smartbuilding_monitor_ctl", {**BASE_PARAMS, "monitor_id": monitor_id})
    t.check(result.get("success") is True, f"[❌/❌/❌] register_source returns success")
    t.check(db_get_monitor(monitor_id) is not None, f"[❌/❌/❌] DB record created")
    t.check(analytics_source_exists(monitor_id), f"[❌/❌/❌] analytics source registered")
    cleanup(monitor_id)


def test_already_running(t: TestResult, monitor_id: str = "test_already") -> None:
    """✅/✅/✅ — everything running → already_running, no change."""
    cleanup(monitor_id)
    mcp_call("smartbuilding_monitor_ctl", {**BASE_PARAMS, "monitor_id": monitor_id})
    time.sleep(0.5)  # give worker time to start
    result = mcp_call("smartbuilding_monitor_ctl", {**BASE_PARAMS, "monitor_id": monitor_id})
    t.check_equal(result.get("status"), "already_running",
                  "[✅/✅/✅] repeat register returns already_running")
    cleanup(monitor_id)


def test_analytics_cleared(t: TestResult, monitor_id: str = "test_cleared") -> None:
    """✅/❌/❌ — DB exists, analytics cleared (stop then delete analytics manually)."""
    cleanup(monitor_id)
    # Register then stop (stops worker + pauses analytics)
    mcp_call("smartbuilding_monitor_ctl", {**BASE_PARAMS, "monitor_id": monitor_id})
    mcp_call("smartbuilding_monitor_ctl", {"action": "stop", "monitor_id": monitor_id})
    # Manually delete from analytics to simulate analytics restart/timeout
    urllib.request.urlopen(urllib.request.Request(
        f"{ANALYTICS_URL}/sources/{monitor_id}", method="DELETE"
    ))
    t.check(not analytics_source_exists(monitor_id), f"[✅/❌/❌] analytics cleared")
    t.check(db_get_monitor(monitor_id) is not None, f"[✅/❌/❌] DB still exists")
    # Re-register
    result = mcp_call("smartbuilding_monitor_ctl", {**BASE_PARAMS, "monitor_id": monitor_id})
    t.check(result.get("success") is True, f"[✅/❌/❌] re-register succeeds")
    t.check(analytics_source_exists(monitor_id), f"[✅/❌/❌] analytics re-registered")
    cleanup(monitor_id)


def test_db_lost(t: TestResult, monitor_id: str = "test_dblost") -> None:
    """❌/✅/❌ — DB lost, analytics exists → DELETE + INSERT + register."""
    cleanup(monitor_id)
    # Register so analytics has it
    mcp_call("smartbuilding_monitor_ctl", {**BASE_PARAMS, "monitor_id": monitor_id})
    mcp_call("smartbuilding_monitor_ctl", {"action": "stop", "monitor_id": monitor_id})
    # Simulate DB loss: delete DB record directly
    db_delete_monitor(monitor_id)
    t.check(db_get_monitor(monitor_id) is None, f"[❌/✅/❌] DB record deleted")
    t.check(analytics_source_exists(monitor_id), f"[❌/✅/❌] analytics still has source")
    # Re-register
    result = mcp_call("smartbuilding_monitor_ctl", {**BASE_PARAMS, "monitor_id": monitor_id})
    t.check(result.get("success") is True, f"[❌/✅/❌] register succeeds")
    t.check(db_get_monitor(monitor_id) is not None, f"[❌/✅/❌] DB record recreated")
    cleanup(monitor_id)


def test_use_case_mismatch(t: TestResult, monitor_id: str = "test_mismatch") -> None:
    """use_case_id mismatch → error, DB unchanged."""
    cleanup(monitor_id)
    mcp_call("smartbuilding_monitor_ctl", {**BASE_PARAMS, "monitor_id": monitor_id})
    mcp_call("smartbuilding_monitor_ctl", {"action": "stop", "monitor_id": monitor_id})
    db_before = db_get_monitor(monitor_id)
    try:
        mcp_call("smartbuilding_monitor_ctl", {
            **BASE_PARAMS, "monitor_id": monitor_id, "use_case_id": "elder_wakeup"
        })
        t.check(False, "use_case mismatch should raise error")
    except Exception as e:
        t.check("use_case_id mismatch" in str(e) or "Error" in str(e),
                "use_case mismatch raises error")
    db_after = db_get_monitor(monitor_id)
    t.check_equal(db_after["use_case_id"] if db_after else None,
                  db_before["use_case_id"] if db_before else None,
                  "DB use_case_id unchanged after mismatch error")
    cleanup(monitor_id)


def test_analytics_unreachable(t: TestResult, monitor_id: str = "test_unreachable") -> None:
    """analytics unreachable → register fails with clear error."""
    cleanup(monitor_id)
    try:
        mcp_call("smartbuilding_monitor_ctl", {
            **BASE_PARAMS,
            "monitor_id": monitor_id,
            "analytics_url": "http://localhost:19999",  # nothing listening
        })
        t.check(False, "analytics unreachable should fail")
    except Exception as e:
        t.check(True, f"analytics unreachable raises error: {str(e)[:80]}")
    # DB should NOT have been created (analytics check happens first)
    # (actually DB is written before analytics register, but if analytics is unreachable
    # the error propagates — DB record may exist but source stays offline)
    cleanup(monitor_id)


def test_unregister(t: TestResult, monitor_id: str = "test_unreg") -> None:
    """unregister removes from analytics + DB."""
    cleanup(monitor_id)
    mcp_call("smartbuilding_monitor_ctl", {**BASE_PARAMS, "monitor_id": monitor_id})
    result = mcp_call("smartbuilding_monitor_ctl", {"action": "unregister", "monitor_id": monitor_id})
    t.check(result.get("success") is True, "unregister returns success")
    t.check(db_get_monitor(monitor_id) is None, "DB record deleted after unregister")
    t.check(not analytics_source_exists(monitor_id), "analytics source deleted after unregister")


def test_list(t: TestResult, monitor_id: str = "test_list") -> None:
    """list returns monitors with analyticsReachable field."""
    cleanup(monitor_id)
    mcp_call("smartbuilding_monitor_ctl", {**BASE_PARAMS, "monitor_id": monitor_id})
    result = mcp_call("smartbuilding_monitor_ctl", {"action": "list"})
    monitors = result if isinstance(result, list) else []
    found = next((m for m in monitors if m["id"] == monitor_id), None)
    t.check(found is not None, "list returns registered monitor")
    t.check("analyticsReachable" in (found or {}), "list result has analyticsReachable field")
    cleanup(monitor_id)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n=== Test: smartbuilding_monitor_ctl ===\n")
    t = TestResult("monitor_ctl")

    if not check_mcp_reachable(t):
        print(f"\nERROR: MCP server not reachable at {MCP_URL}")
        print("Start with: node packages/mcp-server/dist/index.js --config demo/config.demo.yaml --http")
        sys.exit(1)

    if not check_analytics_reachable(t):
        print(f"\nERROR: Mock analytics not reachable at {ANALYTICS_URL}")
        print("Start with: python tests/mock/videostream-analytics/mock_server.py --port 8999")
        sys.exit(1)

    print()
    test_fresh_register(t)
    test_already_running(t)
    test_analytics_cleared(t)
    test_db_lost(t)
    test_use_case_mismatch(t)
    test_analytics_unreachable(t)
    test_unregister(t)
    test_list(t)

    passed = t.summary()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
