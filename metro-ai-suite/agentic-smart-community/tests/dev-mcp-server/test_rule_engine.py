#!/usr/bin/env python3
"""Test Case 6: Rule Engine — 默认规则 + Python override。

直接用 Python 测试规则引擎逻辑（无需 Node.js）。
"""

import json
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import get_temp_dir, cleanup_dir, TestResult

SEVERITY_LEVELS = {"info": 0, "warn": 1, "critical": 2}
THRESHOLD = SEVERITY_LEVELS["warn"]


def outcome_to_rule_result(use_case: str, outcome: dict | None) -> dict:
    if not outcome:
        return {"should_alert": False, "alert_message": None}
    return {
        "should_alert": True,
        "alert_message": f"[{use_case}] {outcome.get('alertType', 'alert')}: {outcome.get('severity', 'warn')} — {outcome.get('description', '')}",
    }


def default_rule_evaluate(context: dict) -> dict:
    """Python implementation of the default rule evaluator (mirrors TS logic)."""
    fields = (context.get("payload") or {}).get("fields") or {}
    severity = fields.get("severity", "").lower()
    level = SEVERITY_LEVELS.get(severity)
    if level is None:
        return {"should_alert": False, "alert_message": None}
    should_alert = level >= THRESHOLD
    event = fields.get("event", "alert")
    desc = fields.get("desc") or fields.get("description", "")
    return {
        "should_alert": should_alert,
        "alert_message": f"[{context['useCase']}] {event}: {severity} — {desc}" if should_alert else None,
    }


def evaluate_with_override(context: dict, use_cases_dir: Path) -> dict:
    """Attempt Python override, fallback to default."""
    override_path = use_cases_dir / context["useCase"] / "evaluate_rules.py"

    if not override_path.exists():
        return default_rule_evaluate(context)

    fields = context["payload"]["fields"]
    result = subprocess.run(
        [sys.executable, str(override_path), json.dumps(fields)],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return outcome_to_rule_result(context["useCase"], json.loads(result.stdout.strip()))


def make_context(use_case: str, fields: dict) -> dict:
    return {
        "monitorId": "cam-01",
        "useCase": use_case,
        "taskId": 1,
        "summaryText": "\n".join(f"{k.upper()}: {v}" for k, v in fields.items()),
        "payload": {"fields": fields},
    }


def main():
    print("\n=== Test: Rule Engine ===\n")
    t = TestResult("Rule Engine")

    # --- Default rule: severity >= warn → alert ---
    warn_result = default_rule_evaluate(make_context(
        "child_safety",
        {"event": "child_jumping", "severity": "warn", "desc": "jumping on sofa"},
    ))
    t.check_equal(warn_result["should_alert"], True, "Default rule: warn severity → alert")
    t.check("child_jumping" in (warn_result["alert_message"] or ""), "Alert message contains event name")

    critical_result = default_rule_evaluate(make_context(
        "child_safety",
        {"event": "fire_detected", "severity": "critical", "desc": "fire play detected"},
    ))
    t.check_equal(critical_result["should_alert"], True, "Default rule: critical → alert")

    info_result = default_rule_evaluate(make_context(
        "child_safety",
        {"event": "normal_activity", "severity": "info", "desc": "walking"},
    ))
    t.check_equal(info_result["should_alert"], False, "Default rule: info severity → no alert")
    t.check_equal(info_result["alert_message"], None, "Info severity: no alert message")

    # --- Python override: success case ---
    tmp = get_temp_dir("rule-engine")
    use_cases_dir = tmp / "use-cases"
    child_safety_dir = use_cases_dir / "child_safety"
    child_safety_dir.mkdir(parents=True)

    override_script = '''
import json, sys
fields = json.loads(sys.argv[1])
# Custom rule: only alert for "child_jumping" event, regardless of severity
should_alert = fields["event"] == "child_jumping"
result = {"alertType": fields["event"], "severity": "warn", "description": "Custom"} if should_alert else None
print(json.dumps(result))
'''
    (child_safety_dir / "evaluate_rules.py").write_text(override_script)

    override_result = evaluate_with_override(make_context(
        "child_safety",
        {"event": "child_jumping", "severity": "info"},
    ), use_cases_dir)
    t.check_equal(override_result["should_alert"], True, "Python override: custom rule triggers for child_jumping")
    t.check("Custom" in (override_result["alert_message"] or ""), "Python override: custom message")

    override_no_alert = evaluate_with_override(make_context(
        "child_safety",
        {"event": "child_walking", "severity": "critical"},
    ), use_cases_dir)
    t.check_equal(override_no_alert["should_alert"], False, "Python override: custom rule skips non-jumping events")

    # --- Missing override file → falls back to default ---
    fallback_result = evaluate_with_override(make_context(
        "nonexistent_case",
        {"event": "something", "severity": "critical"},
    ), use_cases_dir)
    t.check_equal(fallback_result["should_alert"], True, "Missing override: falls back to default rule")

    # --- Broken script → raises instead of hiding the generated-script error ---
    broken_dir = use_cases_dir / "broken_case"
    broken_dir.mkdir(parents=True)
    (broken_dir / "evaluate_rules.py").write_text('raise Exception("intentional error")')

    try:
        evaluate_with_override(make_context(
            "broken_case",
            {"event": "test", "severity": "critical"},
        ), use_cases_dir)
        t.check(False, "Broken script: raises instead of falling back")
    except RuntimeError:
        t.check(True, "Broken script: raises instead of falling back")

    cleanup_dir(tmp)
    passed = t.summary()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
