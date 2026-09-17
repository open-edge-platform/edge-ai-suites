#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Offline integrity check for the onboarding-validation skill. Requires no access to any
# validated application. Run it after ANY change to the skill (rules, SKILL.md, scripts,
# reference files) and before opening a PR.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SKILL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
SKILL_FILE="$SKILL_DIR/SKILL.md"
RULES_FILE="$SKILL_DIR/references/rules-onboarding-validation.md"
FORMAT_FILE="$SKILL_DIR/references/report-format.md"
FIXTURE="$SKILL_DIR/assets/sample-report.md"
CHECKER="$SCRIPT_DIR/reconcile-report.sh"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

fail() { echo "ERROR: $*"; exit 1; }

# Run the checker; print nothing, return its exit code.
# Optional 2nd argument overrides the rules file (used by the duplicate-rule mutation).
run_checker() {
  local report="$1" rules="${2:-$RULES_FILE}" out rc
  set +e
  out=$(RULES_FILE="$rules" REPORT_FILE="$report" "$CHECKER" 2>&1)
  rc=$?
  set -e
  printf '%s\n' "$out" > "$WORK/last-output.txt"
  return "$rc"
}

# -----------------------------------------------------------------------------
check_fixture_passes() {
  echo "[1/5] Golden fixture reconciles cleanly..."
  if ! run_checker "$FIXTURE"; then
    cat "$WORK/last-output.txt"
    fail "reconcile-report.sh failed on the golden fixture. Regenerate it with --emit-skeleton."
  fi
  grep -q "OK: Reconciliation passed." "$WORK/last-output.txt" \
    || fail "Checker did not report success on the golden fixture."
}

# -----------------------------------------------------------------------------
# Mutation tests: each mutation breaks exactly one part of the report contract. If the checker
# still passes, the contract is not actually enforced and the golden fixture proves nothing.
check_mutations_are_detected() {
  echo "[2/5] Mutated fixtures are rejected..."

  # a) A rule row silently deleted -> completeness check must fire.
  awk 'BEGIN{done=0} /^\| [0-9]+[.][0-9]+ \|/ && !done { done=1; next } { print }' \
    "$FIXTURE" > "$WORK/mut-missing-rule.md"

  # b) The Summary count table drifts from the verdicts (PASS inflated by one).
  awk '{
    if ($0 ~ /^\| [0-9]+ \| [0-9]+ \| [0-9]+ \| [0-9]+ \| [0-9]+ \| [0-9]+ \|$/) {
      n=split($0, F, "|")
      p=F[3]+1
      printf "|%s| %s |%s|%s|%s|%s|\n", F[2], p, F[4], F[5], F[6], F[7]
      next
    }
    print
  }' "$FIXTURE" > "$WORK/mut-summary-drift.md"

  # c) The UX score is changed, so it no longer matches the verdicts.
  sed 's|4\.0 / 10|9.5 / 10|' "$FIXTURE" > "$WORK/mut-ux-score.md"

  # d) A status icon is followed by a regular space instead of U+00A0. Written as explicit UTF-8
  #    bytes: $'\u00a0' / printf '\u00a0' depend on the locale and can emit a lone 0xA0.
  sed "s/$(printf '\xc2\xa0')/ /g" "$FIXTURE" > "$WORK/mut-nbsp.md"

  # e) A column is inserted into the Detailed Results table -> header assertion must fire.
  awk '{ sub(/^\| ID \| Rule \(short\) \|/, "| ID | Owner | Rule (short) |"); print }' \
    "$FIXTURE" > "$WORK/mut-header.md"

  # f) The run identity is removed (agent).
  grep -v '^| AI agent |' "$FIXTURE" > "$WORK/mut-identity.md"

  # g) The run identity is removed (model). Checked separately from (f): a checker that validates
  #    only the agent row would still pass (f)'s sibling mutation and hide the regression.
  grep -v '^| Model |' "$FIXTURE" > "$WORK/mut-identity-model.md"

  local m
  for m in mut-missing-rule mut-summary-drift mut-ux-score mut-nbsp mut-header mut-identity \
           mut-identity-model; do
    if run_checker "$WORK/$m.md"; then
      cat "$WORK/last-output.txt"
      fail "Mutation '$m' was NOT detected; the report format contract is not enforced."
    fi
  done

  # h) A rule row is duplicated in the RULES file -> the checker must reject the rules file
  #    instead of silently de-duplicating it (which would hide a real authoring error).
  awk 'BEGIN{done=0} { print } /^\| [0-9]+[.][0-9]+ \|/ && !done { done=1; print }' \
    "$RULES_FILE" > "$WORK/mut-dup-rules.md"
  if run_checker "$FIXTURE" "$WORK/mut-dup-rules.md"; then
    cat "$WORK/last-output.txt"
    fail "A duplicated rule ID in the rules file was NOT detected."
  fi
  grep -q "Duplicate rule ID" "$WORK/last-output.txt" \
    || fail "Duplicated rule ID was rejected, but not with the expected error message."

  # ...and the skeleton generator must refuse the same rules file.
  if RULES_FILE="$WORK/mut-dup-rules.md" "$CHECKER" --emit-skeleton >/dev/null 2>&1; then
    fail "--emit-skeleton accepted a rules file with a duplicated rule ID."
  fi
}

# -----------------------------------------------------------------------------
check_skeleton_matches_rules() {
  echo "[3/5] Generated skeleton covers every rule..."
  RULES_FILE="$RULES_FILE" "$CHECKER" --emit-skeleton > "$WORK/skeleton.md"

  awk -F'|' '/^\| [0-9]+[.][0-9]+ \|/ { v=$2; gsub(/ /,"",v); print v }' "$WORK/skeleton.md" \
    | sort -u > "$WORK/skeleton-ids.txt"
  awk -F'|' '/^## Rationale/ { exit } /^\| [0-9]+[.][0-9]+ \|/ { v=$2; gsub(/ /,"",v); print v }' \
    "$RULES_FILE" | sort -u > "$WORK/rules-ids.txt"

  if ! diff -q "$WORK/rules-ids.txt" "$WORK/skeleton-ids.txt" >/dev/null; then
    diff "$WORK/rules-ids.txt" "$WORK/skeleton-ids.txt" || true
    fail "The generated skeleton does not contain exactly one row per rule."
  fi

  # An unfilled skeleton must NOT pass: it has no verdicts yet.
  if run_checker "$WORK/skeleton.md"; then
    fail "An unfilled skeleton passed reconciliation; the verdict check is not enforced."
  fi
}

# -----------------------------------------------------------------------------
check_contract_not_drifted() {
  echo "[4/5] Format contract in the script matches references/report-format.md..."
  # CR is stripped from both sides: a CRLF checkout (git core.autocrlf=true on Windows) would
  # otherwise make every line differ by a trailing \r and report a drift that does not exist.
  awk '{ sub(/\r$/, "") }
       /^# CONTRACT-BEGIN/{f=1;next} /^# CONTRACT-END/{f=0} f && /^[A-Z_]+=/ { print }' \
    "$CHECKER" | sort > "$WORK/contract-script.txt"
  awk '{ sub(/\r$/, "") } /^[A-Z_]+=/ { print }' "$FORMAT_FILE" | sort > "$WORK/contract-doc.txt"

  [[ -s "$WORK/contract-script.txt" ]] || fail "No contract constants found in $CHECKER."

  if ! diff -q "$WORK/contract-script.txt" "$WORK/contract-doc.txt" >/dev/null; then
    echo "--- script vs report-format.md ---"
    diff "$WORK/contract-script.txt" "$WORK/contract-doc.txt" || true
    fail "The report format contract drifted. Update references/report-format.md and bump Skill Version."
  fi
}

# -----------------------------------------------------------------------------
check_references_and_links() {
  echo "[5/5] Bundled files are referenced from SKILL.md and all relative links resolve..."
  local missing=0 rel link root

  while IFS= read -r rel; do
    rel="references/${rel##*/}"
    if ! grep -Fq "$rel" "$SKILL_FILE"; then
      echo "ERROR: Unlinked reference file: $rel"
      missing=1
    fi
  done < <(find "$SKILL_DIR/references" -maxdepth 1 -type f | sort)

  # Root-level companion files (benchmark.md, ...) must be named in SKILL.md too. An agent only
  # discovers a bundled file through an explicit reference, and skill-validator warns about
  # "potentially unreferenced file" otherwise. SKILL.md itself is the entry point, so it is exempt.
  while IFS= read -r root; do
    root="${root##*/}"
    [[ "$root" == "SKILL.md" ]] && continue
    if ! grep -Fq "$root" "$SKILL_FILE"; then
      echo "ERROR: Unreferenced root-level file: $root (name it in SKILL.md so agents can find it)"
      missing=1
    fi
  done < <(find "$SKILL_DIR" -maxdepth 1 -type f -name '*.md' | sort)

  while IFS= read -r link; do
    [[ -z "$link" ]] && continue
    [[ "$link" =~ ^https?:// ]] && continue
    [[ "$link" =~ ^mailto: ]] && continue
    [[ "$link" == *"#"* ]] && link="${link%%#*}"
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

  [[ "$missing" -eq 0 ]] || exit 1
}

check_fixture_passes
check_mutations_are_detected
check_skeleton_matches_rules
check_contract_not_drifted
check_references_and_links

echo "OK"


