#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

# Use a private temp directory to avoid /tmp collisions in shared environments
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Require RULES_FILE and REPORT_FILE as environment variables
: "${RULES_FILE:?ERROR: RULES_FILE not set. Export it before running.}"
: "${REPORT_FILE:?ERROR: REPORT_FILE not set. Export it before running.}"

# Validate files exist
[[ -f "$RULES_FILE" ]]  || { echo "ERROR: Rules file not found: $RULES_FILE"; exit 1; }
[[ -f "$REPORT_FILE" ]] || { echo "ERROR: Report file not found: $REPORT_FILE"; exit 1; }

# 1. Extract canonical rule IDs from sections 1-16 ONLY (stop at the Rationale table),
#    then de-duplicate as a safety net. The "## Rationale for Key Thresholds" section is
#    explanatory, not part of the rule set; stopping at its heading means its rows can never
#    inflate the count, regardless of how that table is formatted. There is NO merging of real
#    rules here -- a duplicate rule ID is a rules-file error, caught by the check below.
awk -F'|' '
  /^## Rationale/ { exit }
  /^\| [0-9]+\.[0-9]+ \|/ { gsub(/ /,"",$2); print $2 }
' "$RULES_FILE" | sort -u > "$TMPDIR/reconcile_rules.txt"

# 2. Extract rule IDs present in the report's Detailed Results table
grep -E "^\| [0-9]+\.[0-9]+ \|" "$REPORT_FILE" \
  | awk -F'|' '{gsub(/ /,"",$2); print $2}' \
  > "$TMPDIR/reconcile_report.txt"

# 3. Sanity check: rules file must yield at least one rule
TOTAL=$(wc -l < "$TMPDIR/reconcile_rules.txt")
if [[ "$TOTAL" -eq 0 ]]; then
  echo "ERROR: No rules extracted from $RULES_FILE. Check file format."
  exit 1
fi

# 4. Check for missing or extra rules (grep -Fxvf requires no sorting)
MISSING=$(grep -Fxvf "$TMPDIR/reconcile_report.txt" "$TMPDIR/reconcile_rules.txt" || true)
EXTRA=$(grep -Fxvf "$TMPDIR/reconcile_rules.txt" "$TMPDIR/reconcile_report.txt" || true)

ERRORS=0
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

# 5. Count per category from the Result ($4) and Severity ($5) COLUMNS only.
#    The old approach grepped the whole line, so a severity word inside the Evidence column
#    (e.g. the text "Critical") double-counted a rule. Reading the columns also lets us assert
#    that every row resolves to exactly one verdict (and each FAIL to exactly one severity).
read -r PASS CRITICAL MAJOR MINOR NA SUM BADROWS < <(
  awk -F'|' '
    /^\| [0-9]+\.[0-9]+ \|/ {
      r=$4; s=$5
      pass=(r ~ /✅/); fail=(r ~ /❌/); na=(r ~ /⚪/)
      if (pass+fail+na != 1) { bad++; next }          # exactly one verdict per row
      if (pass) { P++ }
      else if (na) { NA++ }
      else {
        c=(s ~ /Critical/); mj=(s ~ /Major/); mn=(s ~ /Minor/)
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
  echo "ERROR: $BADROWS row(s) lack exactly one verdict (✅/❌/⚪) and (for FAIL) one severity. Fix the Result/Severity columns."
  ERRORS=1
fi
if [[ "$SUM" -ne "$TOTAL" ]]; then
  echo "ERROR: Sum ($SUM) != Total rules ($TOTAL). Fix the report."
  ERRORS=1
fi

# 6. Cross-check the human-visible Summary count table against the computed per-row tally.
#    Catches the case where the headline numbers drift from the actual verdicts even though
#    their sum still equals the rule total -- the exact failure that motivated this hardening.
SUMMARY_ROW=$(grep -E '^\| *[0-9]+ *\| *[0-9]+ *\| *[0-9]+ *\| *[0-9]+ *\| *[0-9]+ *\| *[0-9]+ *\|' "$REPORT_FILE" | head -1 || true)
if [[ -z "$SUMMARY_ROW" ]]; then
  echo "ERROR: Could not find the Summary count table row (6 integer columns) in the report."
  ERRORS=1
else
  read -r D_TOTAL D_PASS D_CRIT D_MAJOR D_MINOR D_NA < <(
    printf '%s\n' "$SUMMARY_ROW" | awk -F'|' '{for(i=2;i<=7;i++) gsub(/ /,"",$i); print $2, $3, $4, $5, $6, $7}'
  )
  if [[ "$D_TOTAL/$D_PASS/$D_CRIT/$D_MAJOR/$D_MINOR/$D_NA" != "$TOTAL/$PASS/$CRITICAL/$MAJOR/$MINOR/$NA" ]]; then
    echo "ERROR: Summary count table ($D_TOTAL/$D_PASS/$D_CRIT/$D_MAJOR/$D_MINOR/$D_NA) does not match counted rows ($TOTAL/$PASS/$CRITICAL/$MAJOR/$MINOR/$NA)."
    echo "       Update the Summary count table (Total/PASS/Critical/Major/Minor/N/A) to match the Detailed Results."
    ERRORS=1
  fi
fi

# 7. Enforce a NON-BREAKING space (U+00A0) between every status icon and its label in table
#    rows. A regular space (U+0020) right after an icon lets the icon wrap onto its own line in
#    rendered Markdown tables. Done with awk (same engine used for counting -- avoids the
#    grep -P "supports only unibyte and UTF-8 locales" pitfall). A correctly formatted cell has
#    the icon followed by U+00A0, so "icon + regular space" never matches.
#    Icons: ✅ ❌ ⚪ (Result column) and 🔴 🟠 🟡 (Summary count header).
read -r BADICON_COUNT BADICON_EXAMPLES < <(
  awk '/^\|/ && /(✅|❌|⚪|🔴|🟠|🟡) /{ c++; if (c<=3) ex=ex (ex?",":"") NR }
       END { print c+0, (ex==""?"-":ex) }' "$REPORT_FILE"
)
if [[ "$BADICON_COUNT" -gt 0 ]]; then
  echo "ERROR: $BADICON_COUNT table row(s) put a regular space after a status icon; use a"
  echo "       non-breaking space (U+00A0) so the icon cannot wrap onto its own line."
  echo "       Example line(s): $BADICON_EXAMPLES"
  ERRORS=1
fi

# 8. Cross-check the headline Overall Result against the computed FAIL counts (structural --
#    no rule IDs). FAIL iff >=1 Critical; CONDITIONAL PASS iff 0 Critical and >=1 Major/Minor;
#    PASS iff zero FAILs. Catches a verdict that contradicts its own defect counts.
if [[ "$CRITICAL" -gt 0 ]]; then
  EXPECTED_RESULT="FAIL"
elif [[ $((MAJOR + MINOR)) -gt 0 ]]; then
  EXPECTED_RESULT="CONDITIONAL PASS"
else
  EXPECTED_RESULT="PASS"
fi
DECLARED_RESULT=$(grep -E '^\*\*Overall Result\*\*:' "$REPORT_FILE" | head -1 \
  | sed -E 's/^\*\*Overall Result\*\*:[[:space:]]*//; s/[[:space:]]*$//; s/\*//g' \
  | tr '[:lower:]' '[:upper:]')
if [[ -z "$DECLARED_RESULT" ]]; then
  echo "ERROR: Could not find the '**Overall Result**:' line in the report."
  ERRORS=1
elif [[ "$DECLARED_RESULT" != "$EXPECTED_RESULT" ]]; then
  echo "ERROR: Overall Result is '$DECLARED_RESULT' but the counts (Critical=$CRITICAL, Major=$MAJOR, Minor=$MINOR) require '$EXPECTED_RESULT'."
  echo "       FAIL needs >=1 Critical; CONDITIONAL PASS needs 0 Critical + >=1 Major/Minor; PASS needs zero FAILs."
  ERRORS=1
fi

# 9. Recompute the Overall UX Score (1-10) from the verdicts and cross-check the declared
#    value + band. The dimension map and weights below are a COPY of the canonical table in
#    SKILL.md (section "User Experience Score"); keep the two in sync.
#    The script self-checks that this map covers every rule ID found in the report, so a rules
#    change that is not reflected here is caught (it prints the unmapped IDs and FAILs).
#    Points: PASS=1.0, FAIL Minor=0.5, FAIL Major=0.25, FAIL Critical=0.0, N/A excluded.
#    Severity caps keep the score consistent with the Overall Result: >=1 Critical => <=4.0;
#    0 Critical and >=1 Major/Minor => <=8.9; zero FAILs => 10.0. Rounding: half-up, 1 decimal.
SKILL_VER=$(grep -E '^\| *Skill Version *\|' "$REPORT_FILE" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
UX_REQUIRED=$(awk -v v="$SKILL_VER" 'BEGIN{ n=split(v,a,"."); maj=a[1]+0; mn=a[2]+0; print (maj>1||(maj==1&&mn>=11))?"1":"0" }')
UX_LINE=$(grep -E '^\*\*Overall UX Score\*\*:' "$REPORT_FILE" | head -1 || true)
# New format (skill >= 1.11.0): score is inside a fenced code block after "**Overall UX Score**"
# Line looks like: ██████████████████████████████████████████░░░░░░░░ 8.4 / 10 — Good
if [[ -z "$UX_LINE" ]]; then
  UX_LINE=$(grep -E '^[█░]+ [0-9]+\.[0-9]+ / 10' "$REPORT_FILE" | head -1 || true)
fi

if [[ -z "$UX_LINE" ]]; then
  if [[ "$UX_REQUIRED" -eq 1 ]]; then
    echo "ERROR: Skill Version ${SKILL_VER:-?} requires an Overall UX Score (inline or code block), but none was found."
    ERRORS=1
  else
    echo "NOTE: No Overall UX Score found; report predates skill 1.11.0 - skipping UX score check."
  fi
else
  read -r RECOMPUTED_UX UNMAPPED_IDS < <(
    awk -F'|' -v CRIT="$CRITICAL" -v MAJ="$MAJOR" -v MIN="$MINOR" '
      BEGIN{
        n=split("1.5 4.1 4.3 4.4 4.5 7.2",A," "); for(i=1;i<=n;i++) dim[A[i]]="D1";
        n=split("3.1 3.2 3.3 3.4 3.5 3.6 3.7 4.2 5.1 5.2 5.3 5.4 5.5",A," "); for(i=1;i<=n;i++) dim[A[i]]="D2";
        n=split("1.1 1.2 1.3 1.4 2.1 2.2 2.3 2.4 2.5 2.6 2.7 6.1 6.2 6.3 6.4 9.1 9.2 9.3 12.3",A," "); for(i=1;i<=n;i++) dim[A[i]]="D3";
        n=split("7.1 11.1 11.2 11.3 11.4 11.5 11.6 11.7 11.8",A," "); for(i=1;i<=n;i++) dim[A[i]]="D4";
        n=split("7.3 7.4 7.5 7.6 10.1 10.2 10.3 10.4 12.1 12.2 15.1 15.2 15.3 15.4",A," "); for(i=1;i<=n;i++) dim[A[i]]="D5";
        n=split("8.1 8.2 8.3 13.1 13.2 13.3 13.4 14.1 14.2 14.3",A," "); for(i=1;i<=n;i++) dim[A[i]]="D6";
        n=split("16.1 16.2 16.3 16.4 16.5",A," "); for(i=1;i<=n;i++) dim[A[i]]="D7";
        w["D1"]=2.0; w["D2"]=2.0; w["D3"]=1.5; w["D4"]=1.5; w["D5"]=2.5; w["D6"]=1.0; w["D7"]=1.0;
        unmapped="";
      }
      /^\| [0-9]+\.[0-9]+ \|/ {
        id=$2; gsub(/ /,"",id);
        d=dim[id];
        if (d=="") { unmapped = unmapped (unmapped==""?"":",") id; next }
        r=$4; s=$5;
        if (r ~ /⚪/) next;                       # N/A excluded from denominator
        if (r ~ /✅/) { p=1.0 }
        else if (s ~ /Critical/) { p=0.0 }
        else if (s ~ /Major/)    { p=0.25 }
        else if (s ~ /Minor/)    { p=0.5 }
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

  EXPECTED_BAND=$(awk -v s="$RECOMPUTED_UX" 'BEGIN{
    s=s+0;
    if (s >= 9.0)      print "Excellent";
    else if (s >= 7.0) print "Good";
    else if (s >= 5.0) print "Fair";
    else if (s >= 3.0) print "Poor";
    else               print "Very Poor";
  }')
  echo "UX_SUMMARY: Overall UX Score = ${RECOMPUTED_UX} / 10 - ${EXPECTED_BAND}"

  if [[ "$UNMAPPED_IDS" != "-" ]]; then
    echo "ERROR: report rule IDs not mapped to any UX dimension: $UNMAPPED_IDS"
    echo "       The UX dimension map in reconcile-report.sh is out of sync with the rules file."
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
    echo "       Update the '**Overall UX Score**:' line to match the computed value."
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
