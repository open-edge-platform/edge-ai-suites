#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SKILL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
SKILL_FILE="$SKILL_DIR/SKILL.md"
RULES_FILE="$SKILL_DIR/references/rules-onboarding-validation.md"
REPORT_FILE="$SKILL_DIR/assets/sample-report.md"

check_report_contract() {
  echo "[1/3] Checking report format contract via golden fixture..."
  local output
  set +e
  output=$(RULES_FILE="$RULES_FILE" REPORT_FILE="$REPORT_FILE" "$SCRIPT_DIR/reconcile-report.sh" 2>&1)
  local rc=$?
  set -e

  # The fixture intentionally covers a subset of rules; reconcile should fail on
  # completeness, but still parse all format anchors and emit canonical counters.
  if [[ "$rc" -eq 0 ]]; then
    echo "ERROR: Expected reconcile-report.sh to fail on partial-rule fixture, but it passed."
    exit 1
  fi
  [[ "$output" == *"Counted: PASS=9 Critical=1 Major=2 Minor=1 N/A=2"* ]] || {
    echo "ERROR: Reconcile output does not match expected parsed verdict counters."
    echo "$output"
    exit 1
  }
  [[ "$output" != *"Could not find the Summary count table row"* ]] || {
    echo "ERROR: Summary table anchor not detected in sample report."
    echo "$output"
    exit 1
  }
  [[ "$output" != *"Could not find the '**Overall Result**:' line"* ]] || {
    echo "ERROR: Overall Result anchor not detected in sample report."
    echo "$output"
    exit 1
  }
  [[ "$output" != *"requires an Overall UX Score"* ]] || {
    echo "ERROR: UX score anchor not detected in sample report."
    echo "$output"
    exit 1
  }
}

check_references_linked() {
  echo "[2/3] Checking that all references files are linked from SKILL.md..."
  local missing=0
  local rel
  while IFS= read -r rel; do
    rel="references/${rel##*/}"
    if ! grep -Fq "$rel" "$SKILL_FILE"; then
      echo "ERROR: Unlinked reference file: $rel"
      missing=1
    fi
  done < <(find "$SKILL_DIR/references" -maxdepth 1 -type f | sort)

  if [[ "$missing" -ne 0 ]]; then
    exit 1
  fi
}

check_relative_links_resolve() {
  echo "[3/3] Checking that relative links in SKILL.md resolve..."
  local missing=0
  local link

  while IFS= read -r link; do
    [[ -z "$link" ]] && continue
    [[ "$link" =~ ^https?:// ]] && continue
    [[ "$link" =~ ^mailto: ]] && continue

    if [[ "$link" == *"#"* ]]; then
      link="${link%%#*}"
    fi
    [[ -z "$link" ]] && continue

    if [[ ! -e "$SKILL_DIR/$link" ]]; then
      echo "ERROR: Broken relative link in SKILL.md: $link"
      missing=1
    fi
  done < <(
    {
      grep -oE '(example-prompts|references|scripts|assets)/[A-Za-z0-9._/-]+' "$SKILL_FILE" || true
      grep -oE '\]\((example-prompts|references|scripts|assets)/[^)#]+' "$SKILL_FILE" | sed -E 's/^\]\(//' || true
    } | sort -u
  )

  if [[ "$missing" -ne 0 ]]; then
    exit 1
  fi
}

check_report_contract
check_references_linked
check_relative_links_resolve

echo "OK"
