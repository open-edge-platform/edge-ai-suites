#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Generate and validate complete machine-readable Jira bug scrub results."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RULES_FILE = SKILL_DIR / "references" / "bug-scrub-rules.md"
RULE_RE = re.compile(r"^\|\s*((?:BKM|SCRUB)-\d{2})\s*\|")
ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")
PLACEHOLDER_RE = re.compile(r"<[^>]+>")

VALID_MODES = {"dry-run", "apply"}
VALID_READINESS = {"READY", "READY WITH FOLLOW-UP", "NEEDS INFO", "BLOCKED"}
VALID_VERDICTS = {"PASS", "NEEDS INFO", "ACTION", "N/A", "BLOCKED"}
VALID_SEVERITIES = {"-", "Blocking", "Non-blocking"}
VALID_RISKS = {"Low", "Medium", "High"}
VALID_ACTION_RESULTS = {"APPLIED", "SKIPPED", "BLOCKED", "FAILED"}
VALID_ERROR_CATEGORIES = {
    "none",
    "PERMISSION",
    "VALIDATION",
    "CONFLICT",
    "RATE_LIMIT",
    "CONNECTIVITY",
    "UNKNOWN",
}


class ResultError(ValueError):
    """Raised when rule extraction or result loading cannot continue."""


def load_rule_ids(path: Path) -> list[str]:
    rule_ids = [
        match.group(1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if (match := RULE_RE.match(line))
    ]
    if not rule_ids:
        raise ResultError(f"No rule IDs found in {path}")

    duplicates = sorted(rule_id for rule_id, count in Counter(rule_ids).items() if count > 1)
    if duplicates:
        raise ResultError(f"Duplicate rule IDs in {path}: {', '.join(duplicates)}")
    return rule_ids


def build_skeleton(issue_keys: list[str], rule_ids: list[str]) -> dict[str, Any]:
    if not issue_keys:
        raise ResultError("At least one --issue is required with --emit-skeleton")
    invalid_keys = [key for key in issue_keys if not ISSUE_KEY_RE.fullmatch(key)]
    if invalid_keys:
        raise ResultError(f"Invalid issue key(s): {', '.join(invalid_keys)}")
    duplicate_keys = sorted(key for key, count in Counter(issue_keys).items() if count > 1)
    if duplicate_keys:
        raise ResultError(f"Duplicate issue key(s): {', '.join(duplicate_keys)}")

    evaluations = [
        {
            "rule_id": rule_id,
            "verdict": "BLOCKED",
            "severity": "Blocking",
            "evidence": "<replace with observed evidence>",
            "required_action": "<replace with required action or null>",
        }
        for rule_id in rule_ids
    ]
    return {
        "schema_version": "1.0",
        "timestamp": "<ISO-8601 with timezone>",
        "target": "<issue key/URL or exact JQL>",
        "mode": "dry-run",
        "jira_modified": False,
        "issues": [
            {
                "key": key,
                "snapshot_updated": "<ISO-8601 with timezone>",
                "final_updated": None,
                "readiness": "BLOCKED",
                "rule_evaluations": copy.deepcopy(evaluations),
                "draft_comment": None,
                "proposed_actions": [],
                "applied_actions": [],
            }
            for key in issue_keys
        ],
    }


def has_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return bool(PLACEHOLDER_RE.search(value))
    if isinstance(value, list):
        return any(has_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(has_placeholder(item) for item in value.values())
    return False


def is_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def is_nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def expected_readiness(evaluations: list[dict[str, Any]]) -> str:
    if any(item.get("verdict") == "BLOCKED" for item in evaluations):
        return "BLOCKED"
    if any(
        item.get("verdict") in {"NEEDS INFO", "ACTION"}
        and item.get("severity") == "Blocking"
        for item in evaluations
    ):
        return "NEEDS INFO"
    if any(item.get("verdict") in {"NEEDS INFO", "ACTION"} for item in evaluations):
        return "READY WITH FOLLOW-UP"
    return "READY"


def validate_action_fields(
    issue_label: str,
    actions: Any,
    action_type: str,
    errors: list[str],
) -> None:
    if not isinstance(actions, list):
        errors.append(f"{issue_label}: {action_type} must be an array")
        return

    if action_type == "proposed_actions":
        fields = {"risk", "action", "old_value", "new_value", "evidence", "authorization"}
    else:
        fields = {"action", "result", "verification", "error_category"}

    for index, action in enumerate(actions, start=1):
        label = f"{issue_label}: {action_type}[{index}]"
        if not isinstance(action, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = sorted(fields - action.keys())
        if missing:
            errors.append(f"{label} missing field(s): {', '.join(missing)}")
            continue
        if not is_nonempty_text(action.get("action")):
            errors.append(f"{label}.action must be non-empty")
        if action_type == "proposed_actions":
            if action.get("risk") not in VALID_RISKS:
                errors.append(f"{label}.risk is invalid")
            if not is_nonempty_text(action.get("evidence")):
                errors.append(f"{label}.evidence must be non-empty")
            if not is_nonempty_text(action.get("authorization")):
                errors.append(f"{label}.authorization must be non-empty")
        else:
            if action.get("result") not in VALID_ACTION_RESULTS:
                errors.append(f"{label}.result is invalid")
            if not is_nonempty_text(action.get("verification")):
                errors.append(f"{label}.verification must be non-empty")
            if action.get("error_category") not in VALID_ERROR_CATEGORIES:
                errors.append(f"{label}.error_category is invalid")


def validate_result(payload: Any, rule_ids: list[str]) -> tuple[list[str], Counter[str], Counter[str]]:
    errors: list[str] = []
    readiness_counts: Counter[str] = Counter()
    verdict_counts: Counter[str] = Counter()

    if not isinstance(payload, dict):
        return ["Top-level JSON value must be an object"], readiness_counts, verdict_counts
    if has_placeholder(payload):
        errors.append("Result contains unresolved <...> placeholders")
    if payload.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    if not is_timestamp(payload.get("timestamp")):
        errors.append("timestamp must be ISO-8601 with a timezone")
    elif datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00")).utcoffset() is None:
        errors.append("timestamp must include a timezone")
    if not is_nonempty_text(payload.get("target")):
        errors.append("target must be non-empty")

    mode = payload.get("mode")
    if mode not in VALID_MODES:
        errors.append(f"mode must be one of: {', '.join(sorted(VALID_MODES))}")
    jira_modified = payload.get("jira_modified")
    if not isinstance(jira_modified, bool):
        errors.append("jira_modified must be a boolean")

    issues = payload.get("issues")
    if not isinstance(issues, list) or not issues:
        errors.append("issues must be a non-empty array")
        return errors, readiness_counts, verdict_counts

    issue_keys: list[str] = []
    applied_results: list[str] = []
    for issue_index, issue in enumerate(issues, start=1):
        issue_label = f"issues[{issue_index}]"
        if not isinstance(issue, dict):
            errors.append(f"{issue_label} must be an object")
            continue
        key = issue.get("key")
        if not isinstance(key, str) or not ISSUE_KEY_RE.fullmatch(key):
            errors.append(f"{issue_label}.key is not a valid Jira key")
            key = issue_label
        else:
            issue_keys.append(key)
            issue_label = key

        if not is_timestamp(issue.get("snapshot_updated")):
            errors.append(f"{issue_label}: snapshot_updated must be ISO-8601")
        final_updated = issue.get("final_updated")
        if final_updated is not None and not is_timestamp(final_updated):
            errors.append(f"{issue_label}: final_updated must be null or ISO-8601")

        readiness = issue.get("readiness")
        if readiness not in VALID_READINESS:
            errors.append(f"{issue_label}: invalid readiness")
        else:
            readiness_counts[readiness] += 1

        evaluations = issue.get("rule_evaluations")
        if not isinstance(evaluations, list):
            errors.append(f"{issue_label}: rule_evaluations must be an array")
            evaluations = []
        observed_ids = [item.get("rule_id") for item in evaluations if isinstance(item, dict)]
        if observed_ids != rule_ids:
            missing = [rule_id for rule_id in rule_ids if rule_id not in observed_ids]
            extras = [rule_id for rule_id in observed_ids if rule_id not in rule_ids]
            duplicates = sorted(
                rule_id for rule_id, count in Counter(observed_ids).items() if count > 1
            )
            detail = []
            if missing:
                detail.append(f"missing={','.join(missing)}")
            if extras:
                detail.append(f"extra={','.join(map(str, extras))}")
            if duplicates:
                detail.append(f"duplicate={','.join(map(str, duplicates))}")
            if not detail:
                detail.append("rule order differs from canonical order")
            errors.append(f"{issue_label}: invalid rule coverage ({'; '.join(detail)})")

        for evaluation_index, evaluation in enumerate(evaluations, start=1):
            label = f"{issue_label}: rule_evaluations[{evaluation_index}]"
            if not isinstance(evaluation, dict):
                errors.append(f"{label} must be an object")
                continue
            verdict = evaluation.get("verdict")
            severity = evaluation.get("severity")
            if verdict not in VALID_VERDICTS:
                errors.append(f"{label}.verdict is invalid")
            else:
                verdict_counts[verdict] += 1
            if severity not in VALID_SEVERITIES:
                errors.append(f"{label}.severity is invalid")
            elif verdict in {"PASS", "N/A"} and severity != "-":
                errors.append(f"{label}: {verdict} requires severity '-' ")
            elif verdict in {"NEEDS INFO", "ACTION"} and severity == "-":
                errors.append(f"{label}: {verdict} requires a finding severity")
            elif verdict == "BLOCKED" and severity != "Blocking":
                errors.append(f"{label}: BLOCKED requires severity Blocking")
            if not is_nonempty_text(evaluation.get("evidence")):
                errors.append(f"{label}.evidence must be non-empty")
            required_action = evaluation.get("required_action")
            if verdict in {"NEEDS INFO", "ACTION", "BLOCKED"} and not is_nonempty_text(
                required_action
            ):
                errors.append(f"{label}.required_action must be non-empty for {verdict}")
            elif required_action is not None and not isinstance(required_action, str):
                errors.append(f"{label}.required_action must be a string or null")

        if evaluations and readiness in VALID_READINESS:
            derived = expected_readiness(evaluations)
            if readiness != derived:
                errors.append(
                    f"{issue_label}: readiness {readiness!r} does not match derived {derived!r}"
                )

        draft_comment = issue.get("draft_comment")
        if draft_comment is not None and not is_nonempty_text(draft_comment):
            errors.append(f"{issue_label}: draft_comment must be null or non-empty")
        validate_action_fields(
            issue_label, issue.get("proposed_actions"), "proposed_actions", errors
        )
        validate_action_fields(
            issue_label, issue.get("applied_actions"), "applied_actions", errors
        )
        if isinstance(issue.get("applied_actions"), list):
            applied_results.extend(
                action.get("result")
                for action in issue["applied_actions"]
                if isinstance(action, dict) and isinstance(action.get("result"), str)
            )

    duplicate_issue_keys = sorted(
        key for key, count in Counter(issue_keys).items() if count > 1
    )
    if duplicate_issue_keys:
        errors.append(f"Duplicate issue key(s): {', '.join(duplicate_issue_keys)}")

    if mode == "dry-run":
        if jira_modified:
            errors.append("dry-run requires jira_modified=false")
        if applied_results:
            errors.append("dry-run must not contain applied actions")
    elif mode == "apply":
        has_applied = "APPLIED" in applied_results
        if jira_modified is True and not has_applied:
            errors.append("jira_modified=true requires at least one APPLIED action")
        if has_applied and jira_modified is not True:
            errors.append("an APPLIED action requires jira_modified=true")
        if has_applied and not all(issue.get("final_updated") for issue in issues if isinstance(issue, dict) and any(isinstance(action, dict) and action.get("result") == "APPLIED" for action in issue.get("applied_actions", []))):
            errors.append("issues with APPLIED actions require final_updated verification timestamps")

    return errors, readiness_counts, verdict_counts


def make_valid_fixture(rule_ids: list[str]) -> dict[str, Any]:
    payload = build_skeleton(["ITEP-12345"], rule_ids)
    payload["timestamp"] = "2026-09-03T12:00:00+00:00"
    payload["target"] = "ITEP-12345"
    issue = payload["issues"][0]
    issue["snapshot_updated"] = "2026-09-03T11:00:00+00:00"
    issue["readiness"] = "READY"
    for evaluation in issue["rule_evaluations"]:
        evaluation.update(
            verdict="PASS",
            severity="-",
            evidence=f"Observed evidence for {evaluation['rule_id']}",
            required_action=None,
        )
    return payload


def run_self_test(rule_ids: list[str]) -> int:
    tests: list[tuple[str, dict[str, Any], bool]] = []
    valid = make_valid_fixture(rule_ids)
    tests.append(("valid complete fixture", valid, True))

    missing_rule = copy.deepcopy(valid)
    missing_rule["issues"][0]["rule_evaluations"].pop()
    tests.append(("missing rule rejected", missing_rule, False))

    wrong_readiness = copy.deepcopy(valid)
    wrong_readiness["issues"][0]["rule_evaluations"][0].update(
        verdict="NEEDS INFO", severity="Blocking", required_action="Request details"
    )
    tests.append(("readiness drift rejected", wrong_readiness, False))

    dry_run_write = copy.deepcopy(valid)
    dry_run_write["jira_modified"] = True
    tests.append(("dry-run mutation rejected", dry_run_write, False))

    placeholder = copy.deepcopy(valid)
    placeholder["issues"][0]["rule_evaluations"][0]["evidence"] = "<evidence>"
    tests.append(("placeholder rejected", placeholder, False))

    for index, (name, payload, should_pass) in enumerate(tests, start=1):
        errors, _, _ = validate_result(payload, rule_ids)
        passed = not errors
        print(f"[{index}/{len(tests)}] {name}...", end=" ")
        if passed != should_pass:
            print("FAILED")
            if errors:
                print("\n".join(f"  {error}" for error in errors))
            return 1
        print("PASS")
    print("OK: scrub result checker self-test passed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, help="Scrub result JSON file")
    parser.add_argument("--rules-file", type=Path, default=DEFAULT_RULES_FILE)
    parser.add_argument("--emit-skeleton", action="store_true")
    parser.add_argument("--issue", action="append", default=[], help="Jira issue key")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        rule_ids = load_rule_ids(args.rules_file)
        if args.self_test:
            return run_self_test(rule_ids)
        if args.emit_skeleton:
            print(json.dumps(build_skeleton(args.issue, rule_ids), indent=2))
            return 0
        if args.input is None:
            raise ResultError("An input JSON file is required unless a mode flag is used")
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ResultError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    errors, readiness_counts, verdict_counts = validate_result(payload, rule_ids)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("FAILED: scrub result validation failed.", file=sys.stderr)
        return 1

    print(
        "SCRUB_SUMMARY: "
        f"issues={len(payload['issues'])} "
        + " ".join(
            f"{name.replace(' ', '_')}={readiness_counts[name]}"
            for name in ("READY", "READY WITH FOLLOW-UP", "NEEDS INFO", "BLOCKED")
        )
    )
    print(
        "VERDICT_SUMMARY: "
        + " ".join(
            f"{name.replace(' ', '_').replace('/', '_')}={verdict_counts[name]}"
            for name in ("PASS", "NEEDS INFO", "ACTION", "N/A", "BLOCKED")
        )
    )
    print(
        f"OK: {len(rule_ids)} rules reconciled for {len(payload['issues'])} issue(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())