#!/usr/bin/env python3
"""Test: use_case_register consistency HARD GATE (schema ↔ LOCAL_PROMPT ↔ evaluate_rules).

Drives smartbuilding_use_case_register over MCP stdio and asserts the pre-flight
consistency gate:
  - rejects a schema↔prompt mismatch / JSON-output prompt with ZERO side effects
    (no ALTER, no VLM POST),
    - normalizes caller-provided schema_extensions as extra fields by adding severity/event/desc,
  - passes the custom-rule, default-rule, and report-only (empty-schema) shapes.

No VLM/VSA service is needed: rejected registers return before any network call,
and passing registers get past the gate (steps.consistency.consistent == true)
before the (expected) VLM POST failure to the unreachable stub URL.
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
    """Minimal MCP stdio client using newline-delimited JSON."""

    def __init__(self, proc: subprocess.Popen):
        self.proc = proc
        self._id = 0

    def send(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        request = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            request["params"] = params
        self.proc.stdin.write((json.dumps(request) + "\n").encode())
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("Server closed stdout")
        return json.loads(line.decode().strip())

    def notify(self, method: str, params: dict | None = None):
        request = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            request["params"] = params
        self.proc.stdin.write((json.dumps(request) + "\n").encode())
        self.proc.stdin.flush()

    def register(self, args: dict) -> dict:
        """Call smartbuilding_use_case_register and return the parsed result object."""
        resp = self.send("tools/call", {"name": "smartbuilding_use_case_register", "arguments": args})
        content = resp.get("result", {}).get("content", [])
        text = content[0].get("text", "") if content else ""
        return json.loads(text)


# ── prompt / rules fixtures ────────────────────────────────────────────────

BROKEN_JSON_PROMPT = """## LOCAL_PROMPT
分析监控画面中的宠物行为和安全状态。
返回 JSON 格式结果，包含：
- motion_direction: string
- pet_confined: boolean
- aggressive_behavior: boolean
"""

GOOD_PET_PROMPT = """## LOCAL_PROMPT
分析这段片段中的宠物行为。
##禁止事项:
- 不要输出 JSON 格式。
##输出格式:
SEVERITY: critical 或 warn 或 info
EVENT: pet_escape / pet_trapped / pet_aggression / pet_normal / no_incident
DESC: 一句话描述宠物动作
PET_ZONE: 区域（可选）
"""

GOOD_PET_RULES = """import sys, json

def evaluate_rules(parsed):
    event = parsed.get("event", "")
    severity = parsed.get("severity", "info").lower()
    desc = parsed.get("desc") or parsed.get("description", "")
    zone = parsed.get("pet_zone", "unknown")
    if event in {"no_incident", "pet_normal"}:
        return None
    if severity not in {"warn", "critical"}:
        return None
    return {"alertType": event, "severity": severity, "description": f"{desc} (zone={zone})"}

def main():
    print(json.dumps(evaluate_rules(json.loads(sys.argv[1]))))

if __name__ == "__main__":
    main()
"""

DEFAULT_PASS_PROMPT = """## LOCAL_PROMPT
分析这段片段中的儿童行为。
##输出格式:
SEVERITY: critical 或 warn 或 info
EVENT: fall / climb / normal
DESC: 一句话描述
"""

DEFAULT_MISSING_SEV_PROMPT = """## LOCAL_PROMPT
##输出格式:
EVENT: something
DESC: 一句话描述
"""

REPORT_ONLY_PROMPT = """## LOCAL_PROMPT
用自由文本描述冰箱的门状态与取放物品，不输出任何结构化字段。
"""


def ext(*specs):
    return [{"name": n, "type": "text", "required": r} for (n, r) in specs]


def main():
    print("\n=== Test: use_case_register consistency gate ===\n")
    t = TestResult("use_case_register consistency gate")

    if not MCP_SERVER_ENTRY.exists():
        print(f"  ⚠ MCP Server not built at {MCP_SERVER_ENTRY}")
        print("  Run 'npm run build' first.")
        sys.exit(1)

    tmp = get_temp_dir("uc-register")
    db_path = str(tmp / "test.db")
    init_test_db(db_path).close()

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

    proc = subprocess.Popen(
        ["node", str(MCP_SERVER_ENTRY), "--config", str(config_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    time.sleep(1)
    if proc.poll() is not None:
        print(f"  ⚠ Server exited early. stderr:\n{proc.stderr.read().decode()}")
        cleanup_dir(tmp)
        sys.exit(1)

    client = MCPClient(proc)

    try:
        client.send("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        })
        client.notify("notifications/initialized")
        time.sleep(0.2)

        # ── T1: JSON prompt + schema↔prompt mismatch → REJECT, zero side effects ──
        r1 = client.register({
            "action": "register", "use_case": "pet_broken",
            "prompt_text": BROKEN_JSON_PROMPT,
            "schema_extensions": ext(("motion_direction", False), ("pet_confined", False), ("aggressive_behavior", False)),
            "evaluate_rules_text": GOOD_PET_RULES,
        })
        c1 = r1.get("steps", {}).get("consistency", {})
        t.check(r1.get("ok") is False, "T1 broken(JSON+mismatch): ok == false")
        t.check(c1.get("consistent") is False, "T1: consistency.consistent == false")
        t.check("motion_direction" in c1.get("missing_in_prompt", []), "T1: schema field reported missing_in_prompt")
        t.check(len(c1.get("format_violations", [])) > 0, "T1: JSON-output format violation reported")
        t.check("schema" not in r1.get("steps", {}), "T1: ZERO side effect — no ALTER (steps.schema absent)")
        t.check("vlm_task" not in r1.get("steps", {}), "T1: ZERO side effect — no VLM POST (steps.vlm_task absent)")

        # ── T2: caller passes event/desc only; tool adds severity, prompt lacks it → REJECT ──
        r2 = client.register({
            "action": "register", "use_case": "def_missing_sev",
            "prompt_text": DEFAULT_MISSING_SEV_PROMPT,
            "schema_extensions": ext(("event", True), ("desc", True)),
        })
        c2 = r2.get("steps", {}).get("consistency", {})
        t.check(r2.get("ok") is False, "T2 normalized-default-missing-severity: ok == false")
        t.check(c2.get("consistent") is False, "T2: consistency.consistent == false")
        t.check("severity" in c2.get("missing_in_prompt", []), "T2: normalized severity reported missing_in_prompt")

        # ── T3: custom-rule path passes with only the customer extension in schema_extensions ──
        r3 = client.register({
            "action": "register", "use_case": "pet_ok",
            "prompt_text": GOOD_PET_PROMPT,
            "schema_extensions": ext(("pet_zone", False)),
            "evaluate_rules_text": GOOD_PET_RULES,
        })
        c3 = r3.get("steps", {}).get("consistency", {})
        t.check(c3.get("consistent") is True, "T3 custom-rule normalized extras: consistency.consistent == true (gate passed)")
        t.check(c3.get("schema_fields") == ["severity", "event", "desc", "pet_zone"], "T3: final schema is base + pet_zone")

        # ── T4: default-rule path (severity/event/desc, no rules) → gate PASSES ──
        r4 = client.register({
            "action": "register", "use_case": "child_ok",
            "prompt_text": DEFAULT_PASS_PROMPT,
            "schema_extensions": ext(("severity", False), ("event", True), ("desc", True)),
        })
        c4 = r4.get("steps", {}).get("consistency", {})
        t.check(c4.get("consistent") is True, "T4 default-rule aligned: consistency.consistent == true (gate passed)")

        # ── T5: report-only (empty schema, free-form prompt) → gate PASSES ──
        r5 = client.register({
            "action": "register", "use_case": "report_only",
            "prompt_text": REPORT_ONLY_PROMPT,
            "schema_extensions": [],
        })
        c5 = r5.get("steps", {}).get("consistency", {})
        t.check(c5.get("consistent") is True, "T5 report-only empty schema: consistency.consistent == true (gate passed)")

        # ── T6: register_task passes the gate, then fails at the (unreachable) VLM POST ──
        # 落盘 must NOT happen when the VLM task registration fails ("注册成功后落盘").
        r6 = client.register({
            "action": "register_task", "use_case": "pet_task_ok",
            "prompt_text": GOOD_PET_PROMPT,
            "schema_extensions": ext(("pet_zone", False)),
            "evaluate_rules_text": GOOD_PET_RULES,
        })
        c6 = r6.get("steps", {}).get("consistency", {})
        t.check(c6.get("consistent") is True, "T6 register_task: consistency gate passed")
        t.check(c6.get("schema_fields") == ["severity", "event", "desc", "pet_zone"], "T6: final schema is base + pet_zone")
        t.check(r6.get("ok") is False, "T6: ok == false (stub VLM unreachable)")
        t.check("vlm_task" not in r6.get("steps", {}), "T6: VLM POST failed — steps.vlm_task absent")
        t.check("artifacts" not in r6.get("steps", {}), "T6: no 落盘 before VLM success — steps.artifacts absent")
        t.check(any("VLM task registration failed" in e for e in r6.get("errors", [])), "T6: error names VLM POST failure")

        # ── T7: register_task with a JSON prompt → gate REJECTS, zero side effects ──
        r7 = client.register({
            "action": "register_task", "use_case": "pet_task_broken",
            "prompt_text": BROKEN_JSON_PROMPT,
            "schema_extensions": ext(("motion_direction", False), ("pet_confined", False), ("aggressive_behavior", False)),
            "evaluate_rules_text": GOOD_PET_RULES,
        })
        c7 = r7.get("steps", {}).get("consistency", {})
        t.check(r7.get("ok") is False, "T7 register_task broken(JSON+mismatch): ok == false")
        t.check(c7.get("consistent") is False, "T7: consistency.consistent == false")
        t.check(len(c7.get("format_violations", [])) > 0, "T7: JSON-output format violation reported")
        t.check("vlm_task" not in r7.get("steps", {}), "T7: ZERO side effect — no VLM POST (steps.vlm_task absent)")
        t.check("artifacts" not in r7.get("steps", {}), "T7: ZERO side effect — no 落盘 (steps.artifacts absent)")

        # ── T8: register_task requires prompt_text — terminal error, never auto-reads ──
        r8 = client.register({
            "action": "register_task", "use_case": "pet_task_noprompt",
            "schema_extensions": ext(("pet_zone", False)),
        })
        t.check(r8.get("ok") is False, "T8 register_task missing prompt_text: ok == false")
        t.check(any("requires prompt_text" in e for e in r8.get("errors", [])), "T8: error tells caller to pass prompt_text")

        # ── T9: register WITHOUT schema_extensions → schema inferred from prompt KEY: lines ──
        # (custom path) The final schema must be derived from GOOD_PET_PROMPT's ## 输出格式.
        r9 = client.register({
            "action": "register", "use_case": "pet_infer",
            "prompt_text": GOOD_PET_PROMPT,
            "evaluate_rules_text": GOOD_PET_RULES,
            # no schema_extensions
        })
        c9 = r9.get("steps", {}).get("consistency", {})
        t.check(c9.get("consistent") is True, "T9 no schema_extensions: gate passed (schema inferred)")
        t.check(c9.get("schema_fields") == ["severity", "event", "desc", "pet_zone"],
                "T9: schema inferred from prompt == severity/event/desc/pet_zone")
        t.check(any("auto-derived" in w for w in r9.get("warnings", [])), "T9: warning notes schema auto-derived from prompt")

        # ── T10: default path, no schema_extensions, no rules → infers severity/event/desc ──
        r10 = client.register({
            "action": "register", "use_case": "child_infer",
            "prompt_text": DEFAULT_PASS_PROMPT,
            # no schema_extensions, no evaluate_rules_text
        })
        c10 = r10.get("steps", {}).get("consistency", {})
        t.check(c10.get("consistent") is True, "T10 default-path no schema_extensions: gate passed (inferred)")
        t.check(c10.get("schema_fields") == ["severity", "event", "desc"],
                "T10: inferred default schema == severity/event/desc")

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
