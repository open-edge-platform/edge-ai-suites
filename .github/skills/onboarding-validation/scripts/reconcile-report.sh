#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SKILL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

# Canonical UX dimension/weight table lives in the report format reference; this script parses it
# instead of embedding a copy, so the two can never drift.
FORMAT_FILE="${FORMAT_FILE:-$SKILL_DIR/references/report-format.md}"

# Use a private temp directory to avoid /tmp collisions in shared environments
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# =============================================================================
# Report format contract
#
# Everything that binds this script to the report template is declared below and
# NOWHERE else. The same constants drive both modes of this script:
#   --emit-skeleton  writes a report skeleton FROM these constants
#   (default)        validates a filled-in report AGAINST these constants
# Because the producer and the consumer of the format share one definition, a
# template change cannot silently break the checker.
#
# Changing any constant below requires bumping `Skill Version` and updating the
# "Report format contract" section of references/report-format.md, which lists
# them verbatim. scripts/self-test.sh fails if the two lists drift apart.
# =============================================================================
# CONTRACT-BEGIN

# --- Row anchors -------------------------------------------------------------
# Note: bracket expressions ([|], [.]) are used instead of backslash escapes because these
# patterns are also passed to awk with -v, where awk would interpret "\." as an escape sequence.
RULE_ROW_RE='^[|] [0-9]+[.][0-9]+ [|]'
SUMMARY_ROW_RE='^[|] *[0-9]+ *[|] *[0-9]+ *[|] *[0-9]+ *[|] *[0-9]+ *[|] *[0-9]+ *[|] *[0-9]+ *[|]'
OVERALL_RESULT_RE='^\*\*Overall Result\*\*:'
UX_BAR_RE='^[█░]+ [0-9]+\.[0-9]+ / 10'
UX_INLINE_RE='^\*\*Overall UX Score\*\*:'
RATIONALE_STOP_RE='^## Rationale'
AGENT_ROW_RE='^[|] *AI agent *[|]'
MODEL_ROW_RE='^[|] *Model *[|]'
UX_DIM_ROW_RE='^[|] *D[0-9]+ *[|]'

# --- Table headers (asserted before any positional parsing) ------------------
DETAIL_HEADER_RE='^[|] *ID *[|] *Rule \(short\) *[|] *Result *[|] *Severity *[|]'
SUMMARY_HEADER_RE='^[|] *Total Rules *[|]'

# --- Column positions (awk fields, -F'|') ------------------------------------
# COL_VALUE is the value column of the "| Field | Value |" Summary table.
# SUMMARY_COL_FIRST is "Total Rules"; the next five are PASS, Critical, Major, Minor, N/A.
COL_ID=2
COL_SHORT=3
COL_RESULT=4
COL_SEVERITY=5
COL_VALUE=3
SUMMARY_COL_FIRST=2

# --- Verdict and severity vocabulary -----------------------------------------
ICON_PASS='✅'
ICON_FAIL='❌'
ICON_NA='⚪'
ICON_ANY_RE='(✅|❌|⚪|🔴|🟠|🟡)'
SEV_CRITICAL='Critical'
SEV_MAJOR='Major'
SEV_MINOR='Minor'
RESULT_FAIL='FAIL'
RESULT_CONDITIONAL='CONDITIONAL PASS'
RESULT_PASS='PASS'

# --- UX bands ----------------------------------------------------------------
BAND_EXCELLENT='Excellent'
BAND_GOOD='Good'
BAND_FAIR='Fair'
BAND_POOR='Poor'
BAND_VERY_POOR='Very Poor'
# CONTRACT-END

# Non-breaking space (U+00A0) between a status icon and its label; a regular space would let the
# icon wrap onto its own line in rendered Markdown tables. Written as explicit UTF-8 bytes: $'\u00a0'
# depends on the locale and emits a lone 0xA0 (invalid UTF-8) under LC_ALL=C.
NBSP=$'\xc2\xa0'

# =============================================================================
# Helpers
# =============================================================================

# Every failure path MUST be observable the same way: exit 1 and, in check mode, a `FAILED:` footer
# (references/evaluation-model.md, "Reconciliation Script Checks", item 9).
MODE=check
die() {
  echo "ERROR: $*" >&2
  if [[ "$MODE" == "check" ]]; then
    echo "FAILED: Reconciliation aborted: $*" >&2
  fi
  exit 1
}


# Emit "<id><TAB><short>" for every rule row in the rules file, stopping at the Rationale section
# (explanatory, not part of the rule set). Rows are emitted VERBATIM -- no de-duplication -- so that
# a duplicated rule ID in the rules file surfaces as an error instead of being silently merged.
extract_rules() {
  awk -F'|' -v STOP="$RATIONALE_STOP_RE" -v ROW="$RULE_ROW_RE" -v CI="$COL_ID" -v CSH="$COL_SHORT" '
    $0 ~ STOP { exit }
    $0 ~ ROW {
      id=$CI; short=$CSH
      gsub(/^[ \t]+|[ \t]+$/, "", id)
      gsub(/^[ \t]+|[ \t]+$/, "", short)
      printf "%s\t%s\n", id, short
    }
  ' "$1"
}

# A duplicate rule ID is a rules-file error: it makes the rule total ambiguous and would let two
# different rules share one report row. Fail loudly in BOTH modes rather than de-duplicating.
assert_unique_rule_ids() {
  local dupes
  dupes=$(extract_rules "$1" | cut -f1 | sort | uniq -d || true)
  if [[ -n "$dupes" ]]; then
    echo "ERROR: Duplicate rule ID(s) in $1:" >&2
    printf '%s\n' "$dupes" >&2
    die "Each rule ID MUST appear exactly once in the rules file."
  fi
}

band_for_score() {
  awk -v s="$1" -v e="$BAND_EXCELLENT" -v g="$BAND_GOOD" -v f="$BAND_FAIR" \
      -v p="$BAND_POOR" -v v="$BAND_VERY_POOR" 'BEGIN{
    s=s+0
    if (s >= 9.0)      print e
    else if (s >= 7.0) print g
    else if (s >= 5.0) print f
    else if (s >= 3.0) print p
    else               print v
  }'
}

# =============================================================================
# Mode: --emit-skeleton
#
# Writes an empty but structurally complete report to stdout: one Detailed Results row per rule,
# both tables, and every anchor the checker looks for. The agent fills in the values; it never
# hand-writes the structure.
# =============================================================================

emit_skeleton() {
  local rules_file="$1" total id short bar rules_version skill_version
  bar=$(printf '░%.0s' $(seq 1 50))
  total=$(extract_rules "$rules_file" | wc -l | tr -d ' ')
  [[ "$total" -gt 0 ]] || die "No rules extracted from $rules_file. Check file format."

  rules_version=$(grep -E '^\| *Version *\|' "$rules_file" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
  skill_version=$(grep -E '^\| *Version *\|' "$SKILL_DIR/SKILL.md" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)

  cat <<EOF
# Onboarding Validation Report: <App Display Name>

### Summary

| Field | Value |
|-------|-------|
| Rules Version | ${rules_version:-<x.y.z>} |
| Skill Version | ${skill_version:-<x.y.z>} |
| AI agent | <harness that executed this run> |
| Model | <model identifier, or "unknown (self-reported)"> |
| Date | $(date +%F) |
| Application | <kebab-case-name> |
| GitHub URL | <url from the validation prompt> |
| Commit | <40-character SHA> |
| Deployment method | <docker-compose / helm / docker> |
| OS | <operating system> |
| CPU | <cpu> |
| RAM | <ram> |
| GPU | <gpu, or "not found"> |
| NPU | <npu, or "not found"> |
| Documentation path followed | <ordered list of documents and sections> |

**Overall UX Score**

\`\`\`text
$bar 0.0 / 10 — $BAND_VERY_POOR
\`\`\`

| Total Rules | ${ICON_PASS}${NBSP}PASS | 🔴${NBSP}FAIL (Critical) | 🟠${NBSP}FAIL (Major) | 🟡${NBSP}FAIL (Minor) | ${ICON_NA}${NBSP}N/A |
|-------------|------|-----------------|-----------------|-----------------|-----|
| $total | 0 | 0 | 0 | 0 | 0 |

**Overall Result**: $RESULT_PASS

### User Experience Summary

**Measured UX Facts**

| # | Metric | Value | Target | Source |
|---|--------|-------|--------|--------|
| 1 | Clone size | | ≤ 100 MB | rule 1.2 |
| 2 | Clone time | | < 2 min | rule 1.5 |
| 3 | Get-started steps | | ≤ 4 | rule 5.1 |
| 4 | Start commands | | 1 | rule 4.2 |
| 5 | App start (deploy) | | < 5 min | rule 4.1 |
| 6 | One-time model prep | | one-time | rule 4.4 |
| 7 | Time-to-first-result | | n/a | rule 7.6 |
| 8 | Image size | | ≤ 30 GB | rule 9.1 |
| 9 | Peak RAM | | ≤ 80% of min | rule 9.2 |
| 10 | External tools | | ≤ 3 | rule 2.2 |
| 11 | UI ready | | ≤ 60 s | rule 7.2 |
| 12 | Minimum skill level | | B | rule 11.6 |

**UX Dimension Scores**

| Dim | Name | Rating (1–10) | Band | Rule basis (non-N/A) → points/max | Notes |
|-----|------|---------------|------|-----------------------------------|-------|
EOF

  # Only the canonical dimension table has a numeric weight column; the illustrative table in the
  # report structure section uses placeholders and must not be emitted as well.
  awk -F'|' -v ROW="$UX_DIM_ROW_RE" '
    $0 ~ ROW {
      d=$2; n=$3; w=$4
      gsub(/^[ \t]+|[ \t]+$/, "", d); gsub(/^[ \t]+|[ \t]+$/, "", n); gsub(/^[ \t]+|[ \t]+$/, "", w)
      if (w !~ /^[0-9]+(\.[0-9]+)?$/) next
      printf "| %s | %s | | | | |\n", d, n
    }
  ' "$FORMAT_FILE"

  cat <<'EOF'

### Detailed Results

| ID | Rule (short) | Result | Severity | Evidence / Reason |
|----|--------------|--------|----------|-------------------|
EOF

  while IFS=$'\t' read -r id short; do
    printf '| %s | %s |  |  |  |\n' "$id" "$short"
  done < <(extract_rules "$rules_file")

  cat <<'EOF'

### Critical Issues

<one item per Critical FAIL>

### Recommendations

<grouped by severity, each referencing a rule ID>

### Execution Notes

<procedural issues, retries, timing anomalies>
EOF
}

if [[ "${1:-}" == "--emit-skeleton" ]]; then
  MODE=skeleton
  : "${RULES_FILE:?ERROR: RULES_FILE not set. Export it before running.}"
  [[ -f "$RULES_FILE" ]]  || die "Rules file not found: $RULES_FILE"
  [[ -f "$FORMAT_FILE" ]] || die "Report format reference not found: $FORMAT_FILE"
  assert_unique_rule_ids "$RULES_FILE"
  emit_skeleton "$RULES_FILE"
  exit 0
elif [[ -n "${1:-}" ]]; then
  die "Unknown argument: $1 (supported: --emit-skeleton)"
fi

# =============================================================================
# Mode: check (default)
# =============================================================================

# Require RULES_FILE and REPORT_FILE as environment variables
: "${RULES_FILE:?ERROR: RULES_FILE not set. Export it before running.}"
: "${REPORT_FILE:?ERROR: REPORT_FILE not set. Export it before running.}"

# Validate files exist
[[ -f "$RULES_FILE" ]]  || die "Rules file not found: $RULES_FILE"
[[ -f "$REPORT_FILE" ]] || die "Report file not found: $REPORT_FILE"
[[ -f "$FORMAT_FILE" ]] || die "Report format reference not found: $FORMAT_FILE"

ERRORS=0

# 0. Assert both table headers BEFORE any positional parsing. Without this, an added or reordered
#    column would silently shift COL_RESULT/COL_SEVERITY and produce wrong counts instead of an
#    error -- exactly the failure mode that makes a format change dangerous.
if ! grep -qE "$DETAIL_HEADER_RE" "$REPORT_FILE"; then
  echo "ERROR: Detailed Results header not found, or its columns changed."
  echo "       Expected: | ID | Rule (short) | Result | Severity | Evidence / Reason |"
  echo "FAILED: Reconciliation found errors above."
  exit 1
fi
if ! grep -qE "$SUMMARY_HEADER_RE" "$REPORT_FILE"; then
  echo "ERROR: Summary count table header ('| Total Rules |') not found."
  echo "FAILED: Reconciliation found errors above."
  exit 1
fi

# 0b. Run identity: the report MUST state which agent and model produced it. Two runs of the same
#     application are only comparable when the harness and the model are known.
check_identity_row() {
  local label="$1" re="$2" value
  value=$(grep -E "$re" "$REPORT_FILE" | head -1 \
    | awk -F'|' -v C="$COL_VALUE" '{v=$C; gsub(/^[ \t]+|[ \t]+$/,"",v); print v}')
  if [[ -z "$value" ]]; then
    echo "ERROR: Summary table row '| $label |' is missing or empty."
    echo "       Record the harness and the model used for this run (see references/report-format.md)."
    return 1
  fi
}
check_identity_row "AI agent" "$AGENT_ROW_RE" || ERRORS=1
check_identity_row "Model" "$MODEL_ROW_RE" || ERRORS=1

# 1. Extract canonical rule IDs from the rules file (stop at the Rationale table). The
#    "## Rationale for Key Thresholds" section is explanatory, not part of the rule set; stopping
#    at its heading means its rows can never inflate the count. Duplicate rule IDs are rejected
#    first -- they are a rules-file error and MUST NOT be silently merged.
assert_unique_rule_ids "$RULES_FILE"
extract_rules "$RULES_FILE" | cut -f1 | sort > "$TMPDIR/reconcile_rules.txt"

# 2. Extract rule IDs present in the report's Detailed Results table
grep -E "$RULE_ROW_RE" "$REPORT_FILE" \
  | awk -F'|' -v C="$COL_ID" '{v=$C; gsub(/ /,"",v); print v}' \
  > "$TMPDIR/reconcile_report.txt"

# 3. Sanity check: rules file must yield at least one rule
TOTAL=$(wc -l < "$TMPDIR/reconcile_rules.txt")
if [[ "$TOTAL" -eq 0 ]]; then
  die "No rules extracted from $RULES_FILE. Check file format."
fi

# 4. Check for missing or extra rules (grep -Fxvf requires no sorting)
MISSING=$(grep -Fxvf "$TMPDIR/reconcile_report.txt" "$TMPDIR/reconcile_rules.txt" || true)
EXTRA=$(grep -Fxvf "$TMPDIR/reconcile_rules.txt" "$TMPDIR/reconcile_report.txt" || true)

if [[ -n "$MISSING" ]]; then
  echo "ERROR: Rules missing from report:" && echo "$MISSING"
  ERRORS=1
fi
if [[ -n "$EXTRA" ]]; then
  echo "ERROR: Extra IDs in report not in rules:" && echo "$EXTRA"
  ERRORS=1
fi

# 4b. A rule MUST appear exactly once in the report. Catch accidental duplicate rows.
DUPES=$(sort "$TMPDIR/reconcile_report.txt" | uniq -d || true)
if [[ -n "$DUPES" ]]; then
  echo "ERROR: Duplicate rule rows in report:" && echo "$DUPES"
  ERRORS=1
fi

# 5. Count per category from the Result and Severity COLUMNS only. Grepping whole lines would
#    double-count a rule whose Evidence column contains a severity word. Reading the columns also
#    lets us assert that every row resolves to exactly one verdict (and each FAIL to one severity).
read -r PASS CRITICAL MAJOR MINOR NA SUM BADROWS < <(
  awk -F'|' -v ROW="$RULE_ROW_RE" -v CR="$COL_RESULT" -v CS="$COL_SEVERITY" \
      -v I_PASS="$ICON_PASS" -v I_FAIL="$ICON_FAIL" -v I_NA="$ICON_NA" \
      -v S_CRIT="$SEV_CRITICAL" -v S_MAJ="$SEV_MAJOR" -v S_MIN="$SEV_MINOR" '
    $0 ~ ROW {
      r=$CR; s=$CS
      pass=(index(r, I_PASS)>0); fail=(index(r, I_FAIL)>0); na=(index(r, I_NA)>0)
      if (pass+fail+na != 1) { bad++; next }          # exactly one verdict per row
      if (pass) { P++ }
      else if (na) { NA++ }
      else {
        c=(index(s, S_CRIT)>0); mj=(index(s, S_MAJ)>0); mn=(index(s, S_MIN)>0)
        if (c+mj+mn != 1) { bad++; next }             # exactly one severity per FAIL
        if (c) C++; else if (mj) MJ++; else MN++
      }
    }
    END { print P+0, C+0, MJ+0, MN+0, NA+0, (P+C+MJ+MN+NA)+0, bad+0 }
  ' "$REPORT_FILE"
)

echo "Expected: $TOTAL | Counted: PASS=$PASS Critical=$CRITICAL Major=$MAJOR Minor=$MINOR N/A=$NA | Sum=$SUM"
# Reuse this exact line in the chat reply -- do NOT hand-count (skill v1.6.0 mandate).
echo "CHAT_SUMMARY: ${TOTAL} rules — ✅ ${PASS} PASS | 🔴 ${CRITICAL} Critical | 🟠 ${MAJOR} Major | 🟡 ${MINOR} Minor | ⚪ ${NA} N/A"

if [[ "$BADROWS" -ne 0 ]]; then
  echo "ERROR: $BADROWS row(s) lack exactly one verdict (${ICON_PASS}/${ICON_FAIL}/${ICON_NA}) and (for FAIL) one severity. Fix the Result/Severity columns."
  ERRORS=1
fi
if [[ "$SUM" -ne "$TOTAL" ]]; then
  echo "ERROR: Sum ($SUM) != Total rules ($TOTAL). Fix the report."
  ERRORS=1
fi

# 6. Cross-check the human-visible Summary count table against the computed per-row tally.
#    Catches the case where the headline numbers drift from the actual verdicts even though
#    their sum still equals the rule total -- the exact failure that motivated this hardening.
SUMMARY_ROW=$(grep -E "$SUMMARY_ROW_RE" "$REPORT_FILE" | head -1 || true)
if [[ -z "$SUMMARY_ROW" ]]; then
  echo "ERROR: Could not find the Summary count table row (6 integer columns) in the report."
  ERRORS=1
else
  read -r D_TOTAL D_PASS D_CRIT D_MAJOR D_MINOR D_NA < <(
    printf '%s\n' "$SUMMARY_ROW" \
      | awk -F'|' -v F="$SUMMARY_COL_FIRST" '{for(i=F;i<=F+5;i++) gsub(/ /,"",$i); print $F, $(F+1), $(F+2), $(F+3), $(F+4), $(F+5)}'
  )
  if [[ "$D_TOTAL/$D_PASS/$D_CRIT/$D_MAJOR/$D_MINOR/$D_NA" != "$TOTAL/$PASS/$CRITICAL/$MAJOR/$MINOR/$NA" ]]; then
    echo "ERROR: Summary count table ($D_TOTAL/$D_PASS/$D_CRIT/$D_MAJOR/$D_MINOR/$D_NA) does not match counted rows ($TOTAL/$PASS/$CRITICAL/$MAJOR/$MINOR/$NA)."
    echo "       Update the Summary count table (Total/PASS/Critical/Major/Minor/N/A) to match the Detailed Results."
    ERRORS=1
  fi
fi

# 7. Enforce a NON-BREAKING space (U+00A0) between every status icon and its label in table rows.
#    A regular space (U+0020) right after an icon lets the icon wrap onto its own line in rendered
#    Markdown tables. The check is positive -- every icon MUST be followed by the exact UTF-8
#    sequence for U+00A0 -- so it also catches a lone 0xA0 byte, which looks like a non-breaking
#    space in some editors but is invalid UTF-8 and renders as a replacement character.
#    Done with awk (same engine used for counting -- avoids the grep -P "supports only unibyte and
#    UTF-8 locales" pitfall).
read -r BADICON_COUNT BADICON_EXAMPLES < <(
  awk -v ICONS="$ICON_ANY_RE" -v NB="$NBSP" '
    /^\|/ {
      a=$0; total=gsub(ICONS, "", a)
      if (total == 0) next
      b=$0; good=gsub(ICONS NB, "", b)
      if (good != total) { c++; if (c<=3) ex=ex (ex?",":"") NR }
    }
    END { print c+0, (ex==""?"-":ex) }' "$REPORT_FILE"
)
if [[ "$BADICON_COUNT" -gt 0 ]]; then
  echo "ERROR: $BADICON_COUNT table row(s) do not put a non-breaking space (U+00A0, UTF-8 C2 A0)"
  echo "       directly after a status icon, so the icon can wrap onto its own line."
  echo "       Example line(s): $BADICON_EXAMPLES"
  ERRORS=1
fi

# 8. Cross-check the headline Overall Result against the computed FAIL counts (structural --
#    no rule IDs). FAIL iff >=1 Critical; CONDITIONAL PASS iff 0 Critical and >=1 Major/Minor;
#    PASS iff zero FAILs. Catches a verdict that contradicts its own defect counts.
if [[ "$CRITICAL" -gt 0 ]]; then
  EXPECTED_RESULT="$RESULT_FAIL"
elif [[ $((MAJOR + MINOR)) -gt 0 ]]; then
  EXPECTED_RESULT="$RESULT_CONDITIONAL"
else
  EXPECTED_RESULT="$RESULT_PASS"
fi
DECLARED_RESULT=$(grep -E "$OVERALL_RESULT_RE" "$REPORT_FILE" | head -1 \
  | sed -E 's/^\*\*Overall Result\*\*:[[:space:]]*//; s/[[:space:]]*$//; s/\*//g' \
  | tr '[:lower:]' '[:upper:]')
EXPECTED_RESULT_UC=$(printf '%s' "$EXPECTED_RESULT" | tr '[:lower:]' '[:upper:]')
if [[ -z "$DECLARED_RESULT" ]]; then
  echo "ERROR: Could not find the '**Overall Result**:' line in the report."
  ERRORS=1
elif [[ "$DECLARED_RESULT" != "$EXPECTED_RESULT_UC" ]]; then
  echo "ERROR: Overall Result is '$DECLARED_RESULT' but the counts (Critical=$CRITICAL, Major=$MAJOR, Minor=$MINOR) require '$EXPECTED_RESULT'."
  echo "       FAIL needs >=1 Critical; CONDITIONAL PASS needs 0 Critical + >=1 Major/Minor; PASS needs zero FAILs."
  ERRORS=1
fi

# 9. Recompute the Overall UX Score (1-10) from the verdicts and cross-check the declared value
#    and band. The dimension map and weights are READ FROM references/report-format.md -- the
#    single source of truth -- so a rules or weighting change cannot leave a stale copy behind.
#    Points: PASS=1.0, FAIL Minor=0.5, FAIL Major=0.25, FAIL Critical=0.0, N/A excluded.
#    Severity caps keep the score consistent with the Overall Result: >=1 Critical => <=4.0;
#    0 Critical and >=1 Major/Minor => <=8.9; zero FAILs => 10.0. Rounding: half-up, 1 decimal.
awk -F'|' -v ROW="$UX_DIM_ROW_RE" '
  $0 ~ ROW {
    d=$2; w=$4; ids=$5
    gsub(/^[ \t]+|[ \t]+$/, "", d); gsub(/^[ \t]+|[ \t]+$/, "", w)
    gsub(/[ \t]/, "", ids)
    if (w !~ /^[0-9]+(\.[0-9]+)?$/) next
    n=split(ids, A, ",")
    for (i=1; i<=n; i++) if (A[i] != "") printf "%s %s %s\n", A[i], d, w
  }
' "$FORMAT_FILE" > "$TMPDIR/ux_dimensions.txt"

if [[ ! -s "$TMPDIR/ux_dimensions.txt" ]]; then
  die "Could not parse the UX dimension table from $FORMAT_FILE."
fi

UX_LINE=$(grep -E "$UX_INLINE_RE" "$REPORT_FILE" | head -1 || true)
# Since skill 1.11.0 the score lives in a fenced code block after "**Overall UX Score**":
# ██████████████████████████████████████████░░░░░░░░ 8.4 / 10 — Good
if [[ -z "$UX_LINE" ]]; then
  UX_LINE=$(grep -E "$UX_BAR_RE" "$REPORT_FILE" | head -1 || true)
fi

if [[ -z "$UX_LINE" ]]; then
  echo "ERROR: No Overall UX Score found (inline or code block). The score is mandatory."
  ERRORS=1
else
  read -r RECOMPUTED_UX UNMAPPED_IDS < <(
    awk -F'|' -v CRIT="$CRITICAL" -v MAJ="$MAJOR" -v MIN="$MINOR" -v ROW="$RULE_ROW_RE" \
        -v CI="$COL_ID" -v CR="$COL_RESULT" -v CS="$COL_SEVERITY" -v DIMFILE="$TMPDIR/ux_dimensions.txt" \
        -v I_PASS="$ICON_PASS" -v I_NA="$ICON_NA" \
        -v S_CRIT="$SEV_CRITICAL" -v S_MAJ="$SEV_MAJOR" -v S_MIN="$SEV_MINOR" '
      BEGIN{
        while ((getline line < DIMFILE) > 0) {
          split(line, F, " ")
          dim[F[1]] = F[2]; w[F[2]] = F[3] + 0
        }
        close(DIMFILE)
        unmapped="";
      }
      $0 ~ ROW {
        id=$CI; gsub(/ /,"",id);
        d=dim[id];
        if (d=="") { unmapped = unmapped (unmapped==""?"":",") id; next }
        r=$CR; s=$CS;
        if (index(r, I_NA)>0) next;                  # N/A excluded from denominator
        if (index(r, I_PASS)>0) { p=1.0 }
        else if (index(s, S_CRIT)>0) { p=0.0 }
        else if (index(s, S_MAJ)>0)  { p=0.25 }
        else if (index(s, S_MIN)>0)  { p=0.5 }
        else { p=0.0 }
        pts[d]+=p; cnt[d]+=1;
      }
      END{
        totW=0; acc=0;
        for (d in w) if (cnt[d]>0) { ds=pts[d]/cnt[d]; acc+=w[d]*ds; totW+=w[d]; }
        raw = (totW>0) ? 1 + 9*(acc/totW) : 1;
        if (CRIT+0 > 0)            { if (raw > 4.0) raw = 4.0 }
        else if (MAJ+MIN+0 > 0)    { if (raw > 8.9) raw = 8.9 }
        else                       { raw = 10.0 }
        score = int(raw*10 + 0.5) / 10;
        printf "%.1f %s\n", score, (unmapped==""?"-":unmapped);
      }
    ' "$REPORT_FILE"
  )

  EXPECTED_BAND=$(band_for_score "$RECOMPUTED_UX")
  echo "UX_SUMMARY: Overall UX Score = ${RECOMPUTED_UX} / 10 - ${EXPECTED_BAND}"

  if [[ "$UNMAPPED_IDS" != "-" ]]; then
    echo "ERROR: report rule IDs not mapped to any UX dimension: $UNMAPPED_IDS"
    echo "       The UX dimension table in $FORMAT_FILE does not cover every rule."
    ERRORS=1
  fi

  DECLARED_UX=$(printf '%s\n' "$UX_LINE" | grep -oE '[0-9]+\.[0-9]+' | head -1 || true)
  # Extract band: the last word(s) after "X.Y / 10" + separator. Works for both inline and bar formats.
  DECLARED_BAND=$(printf '%s\n' "$UX_LINE" | awk '{
    if (match($0, /[0-9]+\.[0-9]+ \/ 10/)) {
      rest = substr($0, RSTART+RLENGTH)
      gsub(/^[[:space:]]*[-\342\200\223\342\200\224]+[[:space:]]*/, "", rest)
      gsub(/[[:space:]]*$/, "", rest)
      print rest
    }
  }')

  UXNUM_OK=$(awk -v a="${DECLARED_UX:-0}" -v b="$RECOMPUTED_UX" 'BEGIN{ d=a-b; if(d<0)d=-d; print (d<=0.05)?"1":"0" }')
  if [[ "$UXNUM_OK" -ne 1 ]]; then
    echo "ERROR: Overall UX Score is '${DECLARED_UX:-<none>}' but recomputed from the verdicts is '$RECOMPUTED_UX'."
    echo "       Update the Overall UX Score line to match the computed value."
    ERRORS=1
  fi
  if [[ "$DECLARED_BAND" != "$EXPECTED_BAND" ]]; then
    echo "ERROR: Overall UX band is '$DECLARED_BAND' but score $RECOMPUTED_UX requires '$EXPECTED_BAND'."
    ERRORS=1
  fi
fi

if [[ "$ERRORS" -ne 0 ]]; then
  echo "FAILED: Reconciliation found errors above."
  exit 1
else
  echo "OK: Reconciliation passed."
fi

