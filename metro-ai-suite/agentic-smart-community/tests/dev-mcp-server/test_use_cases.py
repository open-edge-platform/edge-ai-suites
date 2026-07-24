#!/usr/bin/env python3
"""Test Case 7: Use Case Adapter — elder_wakeup evaluate_rules.py.

Invokes each adapter via `subprocess.run(python3, [script, json_ctx])`, using
the exact protocol implemented by `packages/rule-engine/src/index.ts`
(`evaluateWithOverride`). Verifies the smart-community contract:

    argv[1]  = parsed fields JSON
    stdout   = AlertOutcome JSON or null

Only elder_wakeup ships a Python override. child_safety and fridge intentionally
fall back to defaultRuleEvaluator.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import REPO_ROOT, TestResult

USE_CASES_DIR = REPO_ROOT / "use-cases"
CHILD_SAFETY = USE_CASES_DIR / "child_safety" / "evaluate_rules.py"
ELDER_WAKEUP = USE_CASES_DIR / "elder_wakeup" / "evaluate_rules.py"
FRIDGE = USE_CASES_DIR / "fridge" / "evaluate_rules.py"


def run_override(script: Path, fields: dict, env: dict | None = None) -> dict | None:
    """Invoke a Python override the same way task-poller does; parse stdout."""
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    result = subprocess.run(
        [sys.executable, str(script), json.dumps(fields)],
        capture_output=True, text=True, timeout=10, env=proc_env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"override exited {result.returncode}: stderr={result.stderr!r}"
        )
    return json.loads(result.stdout.strip())


def test_elder_wakeup(t: TestResult) -> None:
    """late_wakeup fires only when event=get_up AND local time > expected+grace."""
    # Freeze `datetime.now()` inside the subprocess by patching the module.
    # Simpler approach: pass a "late" scenario by picking expected=00:00, grace=0,
    # which any real time-of-day exceeds. And a "not late" scenario with
    # expected=23:59, grace=59 which no real clock exceeds.

    # get_up + wide-open trigger window → fires
    r = run_override(ELDER_WAKEUP,
        {"severity": "info", "event": "get_up", "desc": "got out of bed",
         "wakeup_time": "25.5"},
        {"ELDER_WAKEUP_EXPECTED_WAKEUP_LOCAL": "00:00", "ELDER_WAKEUP_GRACE_MINUTES": "0"})
    t.check_equal(r["alertType"], "late_wakeup", "elder_wakeup get_up past expected+grace → alert")
    t.check_equal(r["severity"], "warn", "elder_wakeup alert severity=warn")
    t.check_equal(r["wakeupTime"], 25.5, "elder_wakeup includes wakeupTime extra")

    # get_up but within tolerance → skip
    r = run_override(ELDER_WAKEUP,
        {"severity": "info", "event": "get_up", "desc": ""},
        {"ELDER_WAKEUP_EXPECTED_WAKEUP_LOCAL": "23:59", "ELDER_WAKEUP_GRACE_MINUTES": "59"})
    t.check_equal(r, None, "elder_wakeup get_up within tolerance → skip")

    # event != get_up → skip regardless of clock
    r = run_override(ELDER_WAKEUP,
        {"severity": "info", "event": "still_in_bed", "desc": ""},
        {"ELDER_WAKEUP_EXPECTED_WAKEUP_LOCAL": "00:00", "ELDER_WAKEUP_GRACE_MINUTES": "0"})
    t.check_equal(r, None, "elder_wakeup non-get_up event → skip")


def test_override_files_exist(t: TestResult) -> None:
    """Sanity: only elder_wakeup ships an override in the default config."""
    t.check(not CHILD_SAFETY.exists(),
        f"child_safety/evaluate_rules.py intentionally absent at {CHILD_SAFETY}")
    t.check(ELDER_WAKEUP.exists(),
            f"elder_wakeup/evaluate_rules.py exists at {ELDER_WAKEUP}")
    t.check(not FRIDGE.exists(),
        f"fridge/evaluate_rules.py intentionally absent at {FRIDGE}")


def main() -> bool:
    print("\n=== Test: Use Case Adapters ===\n")
    t = TestResult("Use Case Adapters")

    test_override_files_exist(t)
    test_elder_wakeup(t)

    return t.summary()


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
