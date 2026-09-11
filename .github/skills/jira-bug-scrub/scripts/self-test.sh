#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SKILL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
SKILL_FILE="$SKILL_DIR/SKILL.md"
RULES_FILE="$SKILL_DIR/references/bug-scrub-rules.md"
POLICY_FILE="$SKILL_DIR/references/automation-policy.md"
RESULT_FORMAT_FILE="$SKILL_DIR/references/result-format.md"
COMMENTS_FILE="$SKILL_DIR/assets/comment-templates.md"
REPORT_FILE="$SKILL_DIR/assets/scrub-report-template.md"
WORKFLOW_FILE="$SKILL_DIR/assets/workflow-overview.md"
CHECKER="$SCRIPT_DIR/check_scrub_result.py"

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

require_file() {
    [[ -f "$1" ]] || fail "Missing required file: $1"
}

require_text() {
    local file=$1
    local text=$2
    grep -Fq -- "$text" "$file" || fail "Missing required text in $file: $text"
}

echo "[1/5] Skill structure and frontmatter..."
for file in \
    "$SKILL_FILE" \
    "$RULES_FILE" \
    "$POLICY_FILE" \
    "$RESULT_FORMAT_FILE" \
    "$COMMENTS_FILE" \
    "$REPORT_FILE" \
    "$WORKFLOW_FILE" \
    "$CHECKER"; do
    require_file "$file"
done
require_text "$SKILL_FILE" "name: jira-bug-scrub"
require_text "$SKILL_FILE" "version: \"0.1.0\""
require_text "$SKILL_FILE" "mode=dry-run|apply"
require_text "$SKILL_FILE" "./references/bug-scrub-rules.md"
require_text "$SKILL_FILE" "./references/automation-policy.md"
require_text "$SKILL_FILE" "./references/result-format.md"
require_text "$SKILL_FILE" "./assets/comment-templates.md"
require_text "$SKILL_FILE" "./assets/scrub-report-template.md"
require_text "$SKILL_FILE" "./assets/workflow-overview.md"
echo "PASS"

echo "[2/5] Canonical rule IDs and counts..."
rule_count=$(grep -Ec '^\| (BKM|SCRUB)-[0-9]{2} \|' "$RULES_FILE")
[[ "$rule_count" -eq 62 ]] || fail "Expected 62 rules, found $rule_count"
for number in $(seq -w 1 35); do
    count=$(grep -Ec "^\\| BKM-${number} \\|" "$RULES_FILE")
    [[ "$count" -eq 1 ]] || fail "Expected BKM-${number} exactly once, found $count"
done
for number in $(seq -w 1 27); do
    count=$(grep -Ec "^\\| SCRUB-${number} \\|" "$RULES_FILE")
    [[ "$count" -eq 1 ]] || fail "Expected SCRUB-${number} exactly once, found $count"
done
echo "PASS"

echo "[3/5] Attached BKM coverage..."
for text in \
    "Correct project" \
    "Correct issue type" \
    "Summary present" \
    "Component present" \
    "Description present" \
    "Affects Version present" \
    "Fix Version present" \
    "Priority present" \
    "Security field handled" \
    "Issue summary" \
    "Impact" \
    "Steps to reproduce" \
    "Expected behavior" \
    "Actual behavior" \
    "Characterization / Isolation input" \
    "Commit" \
    "P1 - Stopper" \
    "P2 - High" \
    "P3 - Medium" \
    "P4 - Low" \
    "within 2 business days" \
    "within 5 business days" \
    "within 10 business days" \
    "within 20 business days" \
    "Suspected Security Defect"; do
    require_text "$RULES_FILE" "$text"
done
echo "PASS"

echo "[4/5] Automation safeguards and output templates..."
for text in \
    '`dry-run` is the default' \
    "Never decrease Priority automatically" \
    'Never set `Suspected Security Defect` to `No`' \
    "Never perform terminal transitions solely because of age" \
    "Post at most one follow-up comment per issue per run" \
    "SKIPPED_DUPLICATE_COMMENT" \
    'Re-read key, `updated`, relevant fields' \
    "Jira issue content"; do
    require_text "$POLICY_FILE" "$text"
done
for heading in \
    "## Missing Information" \
    "## Stale Update Request" \
    "## Priority Clarification" \
    "## Suspected Security Follow-Up" \
    "## Closure Evidence Request"; do
    require_text "$COMMENTS_FILE" "$heading"
done
require_text "$REPORT_FILE" "**Mutation statement**"
require_text "$REPORT_FILE" "**Applied and verified mutations**"
require_text "$RESULT_FORMAT_FILE" "exact, ordered rule coverage"
require_text "$WORKFLOW_FILE" '```mermaid'
require_text "$WORKFLOW_FILE" "Run result checker"
echo "PASS"

echo "[5/5] Result checker mutation tests..."
python3 "$CHECKER" --self-test

echo "OK: jira-bug-scrub skill self-test passed."