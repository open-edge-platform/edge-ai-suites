#!/usr/bin/env python3
"""Test: Events Webhook — POST /events protocol validation.

Exercises the **real** EventsEndpoint class from packages/mcp-server/dist
against a real SmartBuildingDB. The status-code contract under test is the
one documented in docs/apis/mcp_webhook_event_api.md:

  200 — DB write succeeded; body carries inserted row ids
  400 — body not JSON, or envelope shape invalid
  404 — unknown path
  405 — wrong method on a known path; sets Allow header
  413 — body exceeds maxBodyBytes
  415 — Content-Type is not application/json
  422 — envelope OK but unprocessable (unknown type / missing required fields)
  500 — DB INSERT threw
"""

import json
import sys
import time
import sqlite3
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import get_temp_dir, cleanup_dir, TestResult, REPO_ROOT

EVENTS_PORT = 13201
MAX_BODY_BYTES = 4096  # small ceiling so the 413 test stays cheap

DIST = REPO_ROOT / "packages" / "mcp-server" / "dist"
DB_DIST = REPO_ROOT / "packages" / "db" / "dist"

NODE_SCRIPT_TEMPLATE = f"""\
import {{ SmartBuildingDB }} from "{DB_DIST}/database.js";
import {{ EventsEndpoint }} from "{DIST}/events-endpoint.js";

// Named flags only — positional ordering bugs once wrote the port literal as a DB filename
// in repo root, leaving stale SQLite files like "13201" / "13201-wal" behind.
const args = process.argv.slice(2);
function flag(name) {{
  const i = args.indexOf(name);
  if (i < 0 || i + 1 >= args.length) throw new Error(`missing required flag: ${{name}}`);
  return args[i + 1];
}}
const dbPath = flag("--db");
const port = Number(flag("--port"));
if (!Number.isInteger(port)) throw new Error(`--port must be an integer, got: ${{flag("--port")}}`);

const db = new SmartBuildingDB(dbPath);
db.initialize();
const endpoint = new EventsEndpoint(db, undefined, {{ maxBodyBytes: {MAX_BODY_BYTES} }});
await endpoint.start(port);
console.log("READY");
"""


def start_server(db_path: str, port: int, workdir: Path) -> subprocess.Popen:
    # Write the script as a .mjs file so Node loads it in ESM mode without --input-type quirks.
    script_path = workdir / "boot.mjs"
    script_path.write_text(NODE_SCRIPT_TEMPLATE)
    proc = subprocess.Popen(
        ["node", str(script_path), "--db", db_path, "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(REPO_ROOT),
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                err = proc.stderr.read().decode()
                raise RuntimeError(f"node server exited before READY:\n{err}")
            continue
        if b"READY" in line:
            return proc
    raise RuntimeError("node server did not become READY in time")


def http_post_json(url: str, body: dict, *, content_type: str = "application/json"):
    raw = json.dumps(body).encode()
    return http_post_raw(url, raw, content_type=content_type)


def http_post_raw(url: str, raw: bytes, *, content_type: str | None = "application/json"):
    headers: dict[str, str] = {}
    if content_type is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=raw, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode()
            return resp.status, dict(resp.getheaders()), (json.loads(content) if content else {})
    except urllib.error.HTTPError as e:
        content = e.read().decode()
        try:
            return e.code, dict(e.headers), json.loads(content)
        except Exception:
            return e.code, dict(e.headers), content


def http_get(url: str):
    try:
        with urllib.request.urlopen(url) as resp:
            content = resp.read().decode()
            return resp.status, dict(resp.getheaders()), (json.loads(content) if content else {})
    except urllib.error.HTTPError as e:
        content = e.read().decode()
        try:
            return e.code, dict(e.headers), json.loads(content)
        except Exception:
            return e.code, dict(e.headers), content


def main():
    print("\n=== Test: Events Webhook (target contract) ===\n")
    t = TestResult("Events Webhook")

    tmp = get_temp_dir("events")
    db_path = str(tmp / "test.db")

    # Ensure dist builds exist before we try to import them.
    if not (DIST / "events-endpoint.js").exists() or not (DB_DIST / "database.js").exists():
        print("  ! dist/ missing — run `npm run build --workspaces` first")
        sys.exit(2)

    proc = start_server(db_path, EVENTS_PORT, tmp)
    base = f"http://localhost:{EVENTS_PORT}"

    try:
        time.sleep(0.2)
        conn = sqlite3.connect(db_path)

        # --- GET /health ---
        status, _, body = http_get(f"{base}/health")
        t.check_equal(status, 200, "GET /health returns 200")
        t.check_equal(body.get("status"), "healthy", "Health body correct")

        # --- POST /health → 405 with Allow: GET ---
        status, headers, _ = http_post_json(f"{base}/health", {})
        t.check_equal(status, 405, "POST /health returns 405")
        t.check_equal(headers.get("Allow"), "GET", "Allow header on /health 405")

        # --- GET /events → 405 with Allow: POST ---
        status, headers, _ = http_get(f"{base}/events")
        t.check_equal(status, 405, "GET /events returns 405")
        t.check_equal(headers.get("Allow"), "POST", "Allow header on /events 405")

        # --- Unknown path → 404 ---
        status, _, _ = http_get(f"{base}/unknown")
        t.check_equal(status, 404, "Unknown path returns 404")

        # --- 200: motion event with prefilter pass → status=pending, body has event_id+task_id ---
        status, _, body = http_post_json(f"{base}/events", {
            "sourceId": "cam_child", "type": "motion", "timestamp": "2026-06-25T10:00:00Z",
            "payload": {
                "event_file_path": "/data/seg_001.mp4",
                "summary_clip_input": "/data/seg_001_input.mp4",
                "start_time": "2026-06-25T10:00:00Z", "end_time": "2026-06-25T10:00:15Z",
                "duration_seconds": 15.0,
                "prefilter_passed": 1, "prefilter_classes": '["person"]', "prefilter_confidence": 0.9,
            },
        })
        t.check_equal(status, 200, "motion event returns 200")
        t.check(isinstance(body.get("event_id"), int), "200 body has event_id")
        t.check(isinstance(body.get("task_id"), int), "200 body has task_id")

        ev_row = conn.execute("SELECT motion_type, event_file_path FROM events WHERE id=?", (body["event_id"],)).fetchone()
        t.check_equal(ev_row[0], "motion", "events.motion_type=motion")
        t.check_equal(ev_row[1], "/data/seg_001.mp4", "event_file_path stored correctly")
        task_row = conn.execute("SELECT status, summary_clip_input FROM video_summary_tasks WHERE id=?", (body["task_id"],)).fetchone()
        t.check_equal(task_row[0], "pending", "prefilter_passed=1 → status=pending")
        t.check_equal(task_row[1], "/data/seg_001_input.mp4", "summary_clip_input stored correctly")

        # --- 200: motion event with prefilter NOT passed → status=ignored ---
        _, _, body = http_post_json(f"{base}/events", {
            "sourceId": "cam_child", "type": "motion", "timestamp": "2026-06-25T10:01:00Z",
            "payload": {
                "event_file_path": "/data/seg_002.mp4",
                "summary_clip_input": "/data/seg_002.mp4",
                "start_time": "2026-06-25T10:01:00Z",
                "duration_seconds": 10.0,
                "prefilter_passed": 0,
            },
        })
        task_status = conn.execute("SELECT status FROM video_summary_tasks WHERE id=?", (body["task_id"],)).fetchone()[0]
        t.check_equal(task_status, "ignored", "prefilter_passed=0 → status=ignored")

        # --- 200: motion w/o prefilter → status=pending ---
        _, _, body = http_post_json(f"{base}/events", {
            "sourceId": "cam_fridge", "type": "motion", "timestamp": "2026-06-25T10:02:00Z",
            "payload": {
                "event_file_path": "/data/fridge_001.mp4",
                "summary_clip_input": "/data/fridge_001.mp4",
                "start_time": "2026-06-25T10:02:00Z",
                "duration_seconds": 20.0,
            },
        })
        task_status = conn.execute("SELECT status FROM video_summary_tasks WHERE id=?", (body["task_id"],)).fetchone()[0]
        t.check_equal(task_status, "pending", "no prefilter → status=pending")

        # --- 200: static → events only, no task; body has event_id but no task_id ---
        status, _, body = http_post_json(f"{base}/events", {
            "sourceId": "cam_child", "type": "static", "timestamp": "2026-06-25T10:03:00Z",
            "payload": {"start_time": "2026-06-25T10:03:00Z", "duration_seconds": 30.0},
        })
        t.check_equal(status, 200, "static event returns 200")
        t.check("event_id" in body, "static 200 body has event_id")
        t.check("task_id" not in body, "static 200 body has no task_id")
        motion_type = conn.execute("SELECT motion_type FROM events WHERE id=?", (body["event_id"],)).fetchone()[0]
        t.check_equal(motion_type, "static", "events.motion_type=static")

        # --- 200: recording → recordings only; body has recording_id ---
        status, _, body = http_post_json(f"{base}/events", {
            "sourceId": "cam_child", "type": "recording", "timestamp": "2026-06-25T10:04:00Z",
            "payload": {
                "recording_path": "/data/rec_001.mp4",
                "recording_start": "2026-06-25T10:00:00Z",
                "recording_end": "2026-06-25T10:01:00Z",
                "duration_seconds": 60.0, "file_size_bytes": 8192000,
            },
        })
        t.check_equal(status, 200, "recording event returns 200")
        t.check(isinstance(body.get("recording_id"), int), "recording 200 body has recording_id")
        rec_path = conn.execute("SELECT file_path FROM recordings WHERE id=?", (body["recording_id"],)).fetchone()[0]
        t.check_equal(rec_path, "/data/rec_001.mp4", "recording file_path stored correctly")

        # --- 422: motion missing required field ---
        events_before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        status, _, body = http_post_json(f"{base}/events", {
            "sourceId": "cam_child", "type": "motion", "timestamp": "2026-06-25T10:05:00Z",
            "payload": {"event_file_path": "/data/seg_x.mp4"},
        })
        t.check_equal(status, 422, "missing required fields returns 422")
        t.check_equal(body.get("code"), "missing_required_fields", "422 body code")
        t.check("summary_clip_input" in body.get("missing", []), "422 lists summary_clip_input as missing")
        events_after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        t.check_equal(events_after, events_before, "422 missing fields → no DB write")

        # --- 422: unknown event type ---
        status, _, body = http_post_json(f"{base}/events", {
            "sourceId": "cam_child", "type": "audio", "timestamp": "2026-06-25T10:05:00Z",
            "payload": {},
        })
        t.check_equal(status, 422, "unknown type returns 422")
        t.check_equal(body.get("code"), "unknown_event_type", "422 body code unknown_event_type")
        t.check_equal(body.get("type"), "audio", "422 echoes the offending type")

        # --- 400: malformed JSON ---
        status, _, body = http_post_raw(f"{base}/events", b"not even { json")
        t.check_equal(status, 400, "malformed JSON returns 400")
        t.check_equal(body.get("code"), "invalid_json", "400 body code invalid_json")

        # --- 400: envelope sourceId wrong type ---
        status, _, body = http_post_json(f"{base}/events", {
            "sourceId": 12345, "type": "motion", "timestamp": "x", "payload": {},
        })
        t.check_equal(status, 400, "bad envelope returns 400")
        t.check_equal(body.get("code"), "invalid_envelope", "400 body code invalid_envelope")

        # --- 415: wrong Content-Type ---
        status, _, body = http_post_raw(
            f"{base}/events", b'{"sourceId":"x","type":"motion","payload":{}}',
            content_type="text/plain",
        )
        t.check_equal(status, 415, "wrong content-type returns 415")
        t.check_equal(body.get("code"), "unsupported_media_type", "415 body code")

        # --- 413: body too large ---
        oversized = b'{"sourceId":"x","type":"motion","payload":{"pad":"' + b"A" * (MAX_BODY_BYTES + 1024) + b'"}}'
        status, _, body = http_post_raw(f"{base}/events", oversized)
        t.check_equal(status, 413, "oversized body returns 413")
        t.check_equal(body.get("code"), "body_too_large", "413 body code")
        t.check_equal(body.get("limit_bytes"), MAX_BODY_BYTES, "413 reports limit_bytes")

        conn.close()

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
