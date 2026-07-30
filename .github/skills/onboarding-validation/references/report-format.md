<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Report Format Reference

This file is part of the `onboarding-validation` skill instructions.

## Report format contract

`scripts/reconcile-report.sh` binds to this report template through five named anchors only:

- `RULE_ROW_RE`: `^\| [0-9]+\.[0-9]+ \|`
- `SUMMARY_ROW_RE`: `^\| *[0-9]+ *\| *[0-9]+ *\| *[0-9]+ *\| *[0-9]+ *\| *[0-9]+ *\| *[0-9]+ *\|`
- `OVERALL_RESULT_RE`: `^\*\*Overall Result\*\*:`
- `UX_BAR_RE`: `^[█░]+ [0-9]+\.[0-9]+ / 10`
- `RATIONALE_STOP_RE`: `^## Rationale`

Changing any of these anchors requires a `Skill Version` bump and updates to this file and the checker.

## Output Format

The agent MUST save the report as a markdown file — NOT display it inline in chat. The file MUST be saved to:

```text
./validation-reports/<application>-<date>-<commit8>.md
```

Where `<application>` and `<date>` are the values from the report's Summary table (Application and Date fields), and `<commit8>` is the first 8 characters of the validated Commit SHA (for a git-submodule app, use the submodule's pinned SHA — it identifies the app version under test). Example: `validation-reports/live-video-captioning-2026-05-29-b13c69c9.md`. Including the short commit keeps two runs of the same app on the same day from overwriting each other (a re-run against a different commit produces a distinct file).

The agent MUST create the `validation-reports/` directory if it does not exist.

### Process log (second artifact)

Every run produces **two** files: this report **and** a process log — the terminal transcript started in Execution step 1. After finishing the run (and after `exit` flushes the `script` session), the agent MUST copy the transcript to:

```text
./validation-logs/<application>-<date>-<commit8>.log
```

It uses the **same `<application>-<date>-<commit8>` stem** as the report; create `validation-logs/` if missing. The log is the verbatim record of what the agent actually ran — it exists so the **Evaluation** layer can independently confirm the report's claims are backed by real command output (Charter principle 1, *evidence over opinion*). Therefore **every PASS/FAIL verdict's evidence MUST be traceable to a command in this log**; if a check could not be backed by a logged command, mark that rule **N/A** and explain in Execution Notes.

The report MUST use the following structure. It MUST begin with a top-level title — `# Onboarding Validation Report: <App Display Name>` — where `<App Display Name>` is the application's full name from its README (the top `#` heading), e.g. `# Onboarding Validation Report: Live Video Captioning`. The remaining sections follow in this order:

### Summary

| Field | Value |
|-------|-------|
| Rules Version | X.Y.Z |
| Skill Version | X.Y.Z |
| Date | YYYY-MM-DD |
| Application | kebab-case name, e.g., `live-video-captioning` |
| GitHub URL | The URL from the validation prompt |
| Commit | Full 40-character SHA from `git log -1 --format='%H'` after clone |
| Commit (submodule) | Only when the app is a git submodule: its pinned gitlink SHA (`git -C <submodule-path> rev-parse HEAD`). Omit this row otherwise. |
| Deployment method | docker-compose / helm / docker |
| OS | e.g., Ubuntu 24.04.4 LTS |
| CPU | e.g., Intel Core Ultra 7 265K |
| RAM | e.g., 94 Gi available (96 GB physical) |
| GPU | e.g., Intel Arc A770 (`/dev/dri/renderD128` present) or "not found" |
| NPU | e.g., available (`/dev/accel/accel0` present) or "not found" |
| Documentation path followed | Ordered list of document(s) and section(s) the agent read to complete the installation. Example: `1. README.md → "Quick Start Guide"  2. docs/prerequisites.md → "GPU Driver Setup"`. List every page and heading the agent had to visit — this shows the complexity of the documentation trail. |

**Overall UX Score**

```text
██████████████████████████████████████████░░░░░░░░ 8.4 / 10 — Good
```

The UX score bar uses Unicode block characters: `█` for filled positions and `░` for empty. Always **50 characters** total. Filled count = `round(score * 5)` (each character = 0.2 points; score 8.4 → 42 filled + 8 empty). The score value and band follow on the same line. The bar MUST be in a fenced code block for consistent monospace rendering.

| Total Rules | ✅ PASS | 🔴 FAIL (Critical) | 🟠 FAIL (Major) | 🟡 FAIL (Minor) | ⚪ N/A |
|-------------|------|-----------------|-----------------|-----------------|-----|
| X           | X    | X               | X               | X               | X   |

**Overall Result**: PASS / CONDITIONAL PASS / FAIL

### User Experience Summary

A reader-facing view of how hard the application is to onboard. See "User Experience Score" for the model. This section has two tables. Use **plain text** for bands — do NOT use status icons here, so the U+00A0 rule does not apply.

**Measured UX Facts** — objective numbers observed during the run (these carry the nuance the score cannot: a deploy of 19 s and one of 4 min 59 s both PASS rule 4.1, but the reader sees the difference here):

| # | Metric | Value | Target | Source |
|---|--------|-------|--------|--------|
| 1 | Clone size | … | ≤ 100 MB | rule 1.2 |
| 2 | Clone time | … | < 2 min | rule 1.5 |
| 3 | Get-started steps | … | ≤ 4 | rule 5.1 |
| 4 | Start commands | … | 1 | rule 4.2 |
| 5 | App start (deploy) | … | < 5 min | rule 4.1 |
| 6 | One-time model prep | … | one-time | rule 4.4 |
| 7 | Time-to-first-result | … | n/a | rule 7.6 |
| 8 | Image size | … | ≤ 30 GB | rule 9.1 |
| 9 | Peak RAM | … | ≤ 80% of min | rule 9.2 |
| 10 | External tools | … | ≤ 3 | rule 2.2 |
| 11 | UI ready | … | ≤ 60 s | rule 7.2 |
| 12 | Minimum skill level | A / B / C | B | rule 11.6 |

**UX Dimension Scores** — the seven dimensions, each a rating 1–10, its band, and the rule verdicts behind it:

| Dim | Name | Rating (1–10) | Band | Rule basis (non-N/A) → points/max | Notes |
|-----|------|---------------|------|-----------------------------------|-------|
| D1 | Time-to-Deploy | … | … | … | … |
| D2 | Setup Effort & Steps | … | … | … | … |
| D3 | Prerequisites & Footprint | … | … | … | … |
| D4 | Documentation & Skill | … | … | … | … |
| D5 | Reliability & Reproducibility | … | … | … | … |
| D6 | Cleanup, Security & Observability | … | … | … | … |
| D7 | UI & Interaction | … | … | … | … |

### Detailed Results

Use the `Short` column from the rules tables as the rule label:

| ID | Rule (short) | Result | Severity | Evidence / Reason |
|----|--------------|--------|----------|-------------------|
| 1.1 | Partial clone used | ✅ PASS / ❌ FAIL / ⚪ N/A | Critical/Major/Minor/— | ... |
| ... | ... | ... | ... | ... |

### Critical Issues

List each FAIL that prevents the user from reaching a working application.

### Recommendations

Suggested fixes grouped by severity (Critical first, then Major, then Minor). Each recommendation MUST reference the rule ID it addresses.

### Execution Notes

Document any procedural issues (agent retries, timing anomalies, network issues unrelated to the app).

## User Experience Score (MANDATORY)

In addition to the per-rule verdicts and the Overall Result, the agent MUST compute a single **Overall UX Score (1–10)** plus a per-dimension breakdown, and present them in the report's **User Experience Summary** section. The score is **fully derived from the rule verdicts** — it adds no subjective input (Charter principle 1, *evidence over opinion*). It is deterministic: the same verdicts always yield the same score, and `scripts/reconcile-report.sh` recomputes it from the Detailed Results table and FAILS the report if the declared value does not match.

### Dimensions and weights (canonical)

Every rule belongs to **exactly one** of seven UX dimensions — a strict partition of all 76 rules, so no rule is counted twice. This table is the **single source of truth**; `scripts/reconcile-report.sh` embeds a copy and self-checks that the copy covers every rule ID in the report (it prints any unmapped ID). When the rules file changes, update BOTH this table and the script.

| Dim | Name | Weight | Rule IDs |
|-----|------|--------|----------|
| D1 | Time-to-Deploy | 2.0 | 1.5, 4.1, 4.3, 4.4, 4.5, 7.2 |
| D2 | Setup Effort & Steps | 2.0 | 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.2, 5.1, 5.2, 5.3, 5.4, 5.5 |
| D3 | Prerequisites & Footprint | 1.5 | 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 6.1, 6.2, 6.3, 6.4, 9.1, 9.2, 9.3, 12.3 |
| D4 | Documentation & Skill | 1.5 | 7.1, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8 |
| D5 | Reliability & Reproducibility | 2.5 | 7.3, 7.4, 7.5, 7.6, 10.1, 10.2, 10.3, 10.4, 12.1, 12.2, 15.1, 15.2, 15.3, 15.4 |
| D6 | Cleanup, Security & Observability | 1.0 | 8.1, 8.2, 8.3, 13.1, 13.2, 13.3, 13.4, 14.1, 14.2, 14.3 |
| D7 | UI & Interaction | 1.0 | 16.1, 16.2, 16.3, 16.4, 16.5 |

D5 carries the highest weight because it contains `10.1 First-attempt success` and `7.6 Functional output verified` — deploying and producing a verified result is the most important onboarding outcome.

### Points per verdict

| Verdict | Points |
|---------|--------|
| ✅ PASS | 1.00 |
| ❌ FAIL (Minor) | 0.50 |
| ❌ FAIL (Major) | 0.25 |
| ❌ FAIL (Critical) | 0.00 |
| ⚪ N/A | excluded from the dimension's denominator |

### Formula

1. **Per-dimension sub-score**: `sub(D) = Σ points(non-N/A rules in D) / count(non-N/A rules in D)`. A dimension whose rules are all N/A is itself N/A and its weight is dropped from the overall.
2. **Per-dimension rating (display only)**: `rating(D) = 1 + 9 × sub(D)`, rounded half-up to 1 decimal. Shown in the report's Table B.
3. **Overall raw score**: `raw = 1 + 9 × [ Σ weight(D)·sub(D) / Σ weight(D) ]` over non-N/A dimensions. Computed from **unrounded** sub-scores — so the rounded per-dimension ratings need NOT re-sum to the overall (this is expected, not an error).
4. **Severity caps** (keep the score consistent with the Overall Result):
   - any Critical FAIL ⇒ `score ≤ 4.0` (Overall Result is FAIL);
   - zero Critical and ≥1 Major/Minor ⇒ `score ≤ 8.9` (CONDITIONAL PASS — never reaches Excellent);
   - zero FAILs ⇒ `score = 10.0` (PASS).
5. **Rounding**: half-up to 1 decimal.
6. **No floor.** A formally-passing app (CONDITIONAL PASS) with many defects MAY land in a low band. The score reports UX honestly and is allowed to be lower than the three-level Overall Result would suggest.

### Bands

| Score | Band |
|-------|------|
| 9.0–10.0 | Excellent |
| 7.0–8.9 | Good |
| 5.0–6.9 | Fair |
| 3.0–4.9 | Poor |
| 1.0–2.9 | Very Poor |

The band MUST stay consistent with the Overall Result: PASS ⇒ Excellent (10.0); CONDITIONAL PASS ⇒ at most Good; FAIL ⇒ at most Poor.
