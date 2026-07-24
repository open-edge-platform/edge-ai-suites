<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

---
name: onboarding-validation
description: >-
  Validate the get-started experience of a containerized application from the
  perspective of a first-time user. Use this skill when a user wants an AI
  agent to follow onboarding or deployment documentation exactly, validate a
  Docker Compose or Helm/Kubernetes path, collect evidence, apply pass/fail
  rules, and produce a structured onboarding validation report with a process
  log. Trigger on onboarding validation, first-time-user validation,
  documentation-driven deployment checks, reproducibility checks, UX scoring,
  and release-readiness reviews for Edge AI Suite or Edge AI Libraries
  applications. Do not use this skill for debugging, fixing application code,
  or ad hoc exploratory testing outside the documented path.
license: Apache-2.0
compatibility: >-
  Requires a bash-compatible shell, git, and access to the target environment.
  The validated application may additionally require Docker Compose or
  Helm/Kubernetes, depending on the documented deployment method.
metadata:
  author: open-edge-platform
  version: "1.11.0"
  tags:
    - validation
    - onboarding
    - qa
    - docker-compose
    - helm
    - kubernetes
    - edge-ai
allowed-tools: bash git
---

# User Onboarding Experience Validation

Validate the get-started experience of a containerized application from the perspective of a first-time user. The agent follows the documentation exactly, collects evidence, evaluates pass/fail rules, and produces a structured report plus a verbatim process log.

| Field | Value |
|-------|-------|
| Skill ID | onboarding-validation |
| Version | 1.11.0 |
| Date | 2026-07-24 |
| Trigger | Validation prompt (see `example-prompts/01-validate-onboarding.md`) |
| Input | GitHub URL of application + deployment method |
| Output | Markdown report in `./validation-reports/` + process log in `./validation-logs/` |
| Rules | `references/onboarding-validation-rules.md` |
| Charter | `references/charter.md` |
| Checker | `scripts/reconcile-report.sh` |

> **Inherits `references/charter.md`.** This skill ships with the full charter so it remains self-contained after installation. The operational detail here (isolation, "No workarounds", reconciliation, faithful reporting) is the concrete *realization* of those principles, not a replacement — if anything here appears to conflict with the bundled charter, **the charter wins**.

---

## When to Use

Use this skill when the user wants to:

- Validate the get-started experience of a containerized application as a first-time user.
- Check whether Docker Compose or Helm/Kubernetes onboarding documentation is reproducible.
- Produce a structured onboarding report with per-rule PASS / FAIL / N/A verdicts.
- Audit release readiness or onboarding UX for Edge AI Suite or Edge AI Libraries apps.

Do not use this skill to:

- Debug, patch, or improve the application under test.
- Explore undocumented alternative deployment paths.
- Perform general code review that is unrelated to the documented onboarding path.

---

## Purpose

Validate the get-started experience of an Edge AI Suite application from the perspective of a first-time user. The agent follows the documentation exactly and reports pass/fail for each rule.

---

## Instructions

### Execution Procedure

The agent MUST follow this procedure to avoid using stale or pre-existing workspace state:

1. **Work in an isolated directory, and record the whole session.** Create a fresh directory outside the workspace and immediately start a terminal transcript so every command and its output is captured to a process log:
   ```bash
   WORK_DIR="/tmp/validation-<app-name>-$(date +%s)"
   mkdir -p "$WORK_DIR" && cd "$WORK_DIR"
   RUN_LOG="$WORK_DIR/run.log"
   script -q -f "$RUN_LOG"        # everything below is now recorded; type `exit` at the very end to flush
   ```
   The persistent SSH terminal makes this a faithful, verbatim record of commands + outputs. As you work, **mark each phase in the log** so it reads step by step — e.g. `echo "=== Step 4: clone (ref=<ref>) ==="` — and echo a one-line note before any judgement the chat would otherwise explain (severity calls, skips, retries), e.g. `echo "NOTE: rule 12.1 FAIL Major — no bundled sample"`. The log is saved next to the report at the end (see Output Format).
2. **Clone from scratch.** The agent MUST NOT use any pre-existing copy of the application from the workspace. All commands MUST start from the fresh clone as a first-time user would. The prompt's `GITHUB_URL` is a GitHub **web URL** (e.g. `…/tree/<ref>/<path>`), not a `git clone` target — extract the base repo, `<ref>`, and `<path>` from it; clone the base repo at `<ref>`, then `cd` into `<path>`. If the `GITHUB_URL` folder contains more than one application, the prompt's **`Name`** selects which one to validate — scope the clone and follow the get-started for that sub-app only.
3. **Use only the cloned documentation.** After cloning, the agent MUST read and follow get-started instructions exclusively from the cloned repository — not from any workspace copy. This ensures the tested docs match the tested code.
   - **Documentation path selection.** The agent MUST scan the application's root `README.md` **from top to bottom** and select the **first section** whose heading clearly serves the purpose of guiding a new user through installation and first run. Common headings include "Get Started", "Getting Started", "Quick Start", "Quickstart", "Installation", "Setup", "Deploy", "Deployment", "Deployment Options", or similar — the exact wording may vary, but the intent must be unambiguous. The agent MUST NOT skip ahead to a shorter path or cherry-pick a different section — this tests the experience of a real first-time user who reads from the top. If a simplified quick-start exists below the fold but the first installation section is a full get-started guide, the agent follows the full guide and notes the quick-start in "Documentation path followed".
   - **Record every document visited.** As the agent follows the instructions, it MUST record every documentation page and section heading it reads, in order. This list goes into the report's "Documentation path followed" field. It reveals how many pages and sections the user must navigate to deploy — a concrete measure of onboarding complexity.
4. **Branch/Tag checkout.** If the validation prompt specifies a branch or tag, the agent MUST:
   - **The agent clones the prompt's `<ref>` (step 2), never the docs' clone target.** The version under test is fixed by the prompt's `GITHUB_URL`, so the run stays deterministic even when the get-started clone command points elsewhere. The agent MUST NOT rewrite or "fix" the documented `git clone` to make it match the intended ref (that is a forbidden workaround — step 6); it reproduces the pinned ref for its own test and reports the documented command **as written**.
   - Verify the docs instruct cloning/checking-out that exact ref.
   - After clone, run `git log -1 --format='%H'` and record the full commit SHA. This value MUST appear in the report Summary table.
   - **If the docs reference a different ref than the one under test, the agent still clones the prompt's `<ref>` and reports the mismatch — never Critical.** Because the agent *consciously* reproduces the correct version (from the prompt link) instead of blindly following the docs onto the wrong/undetermined commit, the run is never blocked, so this is **never Critical**. Two sub-cases:
      - **Moving ref** in the docs (`main`, a release **branch** like `--branch release-2026.1`, `latest`, or any non-pinned target): the documented path is non-deterministic — a user who copies it later gets a different, moving commit — so report a reproducibility FAIL (**rule 10.2**) at **Major** severity (also fail **rule 1.3** if no exact tag/commit is named at all). It is **Major**, not a cosmetic Minor (a real defect a real user hits), and **never Critical** (the agent reproduced the pinned ref).
      - **Different but fixed ref** — typically the docs already name the **final release tag/branch** while the prompt pins an **RC** (e.g. validating `…-rc2` against docs that point to the GA tag). The documented clone is itself deterministic (an exact tag), so the clone rules (1.3/10.2) may still PASS; this is an **expected, conscious** release-process discrepancy. The agent MUST clone the prompt's `<ref>` (the RC) and **note the mismatch in Execution Notes** for transparency. This is **not Critical** and is **not a reproducibility FAIL by itself**.
   - **Submodule apps.** If the app folder is a git submodule of the base repo (it appears in the base repo's `.gitmodules`), the version under test is the commit the base ref pins for that submodule — its **gitlink SHA** — which is the ground truth **regardless of what the submodule's own documentation says to clone**. The agent MUST:
      - Resolve the pinned commit and reproduce exactly it (do NOT clone the submodule's own repository directly — that bypasses the suite pin):
        ```bash
        git clone --filter=blob:none --sparse --branch <ref> <base-repo> <base>
        cd <base>
        git ls-tree HEAD <submodule-path>                 # -> 160000 commit <PINNED_SHA> <path>
        git sparse-checkout set <submodule-path>
        git submodule update --init --recursive -- <submodule-path>
        git -C <submodule-path> rev-parse HEAD            # MUST equal <PINNED_SHA>
        ```
     - Record BOTH SHAs in the Summary: base `Commit` and `Commit (submodule)` = `<PINNED_SHA>`.
     - Evaluate the clone rules (1.x) against the **app's** documented get-started, which lives inside the submodule at `<PINNED_SHA>`.
     - If that documentation tells the user to clone the submodule repo at a moving ref (e.g., `main`) or at a commit other than `<PINNED_SHA>`, the documented path does NOT reproduce the released version — report it as a reproducibility FAIL (rule 10.2), exactly like the `main`-vs-tag discrepancy above.
5. **Single linear execution.** The agent MUST NOT restart, re-clone, or redo steps. If a step fails, record the failure and continue. If the agent needs to redo a step due to its own procedural error (not an app bug), it MUST document this in the "Execution Notes" section of the report.
6. **No workarounds.** The agent MUST NOT debug, fix, or work around deployment issues. If a command fails, the agent MUST record the failure as-is and move on. The agent MUST NOT: modify source code, add missing environment variables, change ports, fix typos in docs commands, or apply any fix not explicitly documented. The goal is to test the documented path — not to prove the app can work with effort.
7. **Cleanup using only documented commands.** Use exactly `docker compose down` (or `helm uninstall`, or `docker stop && docker rm`) as the application documents. If additional cleanup is needed (e.g., root-owned files on host), record this as evidence for rule 8.2.

---

## Evidence Collection

- **System inventory** (collect once at start, include in report header):
  ```bash
  # OS
  cat /etc/os-release | grep -E "^(NAME|VERSION)="
  # CPU
  lscpu | grep "Model name"
  # RAM (report raw value from free and physical size from dmidecode if available)
  free -h | grep Mem | awk '{print $2}'
  # Optional: if sudo available, get exact physical RAM
  sudo dmidecode -t memory 2>/dev/null | grep "Maximum Capacity" || true
  # GPU / NPU availability
  ls /dev/dri/render* 2>/dev/null && echo "GPU: available" || echo "GPU: not found"
  ls /dev/accel/accel* 2>/dev/null && echo "NPU: available" || echo "NPU: not found"
  # GPU model (if available)
  lspci | grep -i "vga\|display\|3d"
  ```
- Measure clone size: `du -sh` after clone.
- Measure time: use `time` prefix on key commands.
- Check health based on deployment method:
  - Docker Compose: `docker compose ps`, `docker compose logs`
  - Helm/K8s: `kubectl get pods`, `kubectl logs`
  - Docker (single-container): `docker ps --filter name=<container>`, `docker logs <container>`
- Check resources based on deployment method:
  - Docker Compose: `docker stats --no-stream`, `df -h`
  - Helm/K8s: `kubectl top pods`, `df -h`
  - Docker (single-container): `docker stats --no-stream <container>`, `df -h`
- Verify endpoints using the URL documented by the application.

---

## Verdict per Rule

For each rule, report one of:

- **✅ PASS**: The application meets the rule.
- **❌ FAIL**: The application does not meet the rule. Include the reason and evidence.
- **⚪ N/A**: The rule does not apply to this application.

The Result cell in the Detailed Results table MUST be prefixed with the status emoji (`✅` / `❌` / `⚪`), joined to the word by a **non-breaking space** (Unicode U+00A0, not a regular space) — e.g. `✅` + U+00A0 + `PASS` — so the icon can never wrap onto its own line. GitHub Markdown supports neither cell background colors nor `<nobr>`; emoji + non-breaking space is the portable equivalent.

The Summary count table header MUST carry matching icons, each joined to its label by a non-breaking space: `✅ PASS`, `🔴 FAIL (Critical)`, `🟠 FAIL (Major)`, `🟡 FAIL (Minor)`, `⚪ N/A` (the `Total Rules` column stays plain).

> **Enforced.** `scripts/reconcile-report.sh` FAILS the report if any status icon in a table row is followed by a regular space instead of U+00A0. A regular space here is a common, easy-to-miss regression — the script catches it so the icon never wraps to its own line in the rendered table.

---

## Completeness and Reconciliation (MANDATORY)

Before saving the report, the agent MUST run these checks and fix any failure:

1. **Cover every rule.** The Detailed Results table MUST contain exactly one row for every rule ID in the rules file of the stated Rules Version — including sections that seem irrelevant. If a rule does not apply, mark it **N/A**; NEVER omit it or stop early. Skipping sections (e.g., 15.x, 16.x) is not allowed.
2. **Tally from the table.** The five summary counts (PASS, Critical, Major, Minor, N/A) MUST be obtained by counting the Detailed Results rows — not estimated or carried over from another report.
3. **Reconcile.** PASS + Critical + Major + Minor + N/A MUST equal the number of rule rows, and that number MUST equal the rule count of the stated Rules Version. Put that number in the "Total Rules" column. These counts come ONLY from the Detailed Results table.
4. **Narrative sections group, but MUST cover.** "Critical Issues" and "Recommendations" are organized by root cause, so their item counts need NOT equal the defect counts — related rules MAY be combined into one item. Coverage is still mandatory: every Critical FAIL MUST be named in "Critical Issues"; every FAIL (any severity) MUST be addressed by at least one recommendation; and no rule may appear in "Critical Issues" unless it is marked Critical in the table.

> **Why the count is canonical — and there is NO deduplication.** The canonical rule count is whatever `scripts/reconcile-report.sh` extracts — currently **76**. The script counts only the rule rows in sections 1–16; it stops at the `## Rationale for Key Thresholds` heading, so those explanatory rows are never counted (regardless of how that table is formatted). The script does **NOT** deduplicate rule IDs — a duplicate ID is an error it reports, not something it silently merges. The agent MUST NOT explain the count by claiming IDs are "deduplicated."

### Runtime Verification (MANDATORY)

The manual tally that fills the Summary counts is a starting point, not the final authority. After writing the report file, the agent MUST run the reconciliation script and fix any discrepancy before considering the report complete:

```bash
export RULES_FILE="<absolute-path-to-this-skill>/references/onboarding-validation-rules.md"
export REPORT_FILE="<absolute-path-to-generated-report>"
./scripts/reconcile-report.sh
```

Run the command above **from this skill directory** so `./scripts/reconcile-report.sh` resolves to the bundled checker.

The script (`scripts/reconcile-report.sh` relative to this skill file) performs these checks, in order:
1. Extracts rule IDs from the rules file (sections 1–16 only — it stops at the `## Rationale` heading) and from the report's Detailed Results table.
2. Detects missing, extra, or duplicate rule IDs.
3. Counts per-category verdicts (PASS, Critical, Major, Minor, N/A) by reading the **Result and Severity columns only** — never the whole line — asserts every row resolves to exactly one verdict (and each FAIL to exactly one severity), and prints a `CHAT_SUMMARY:` line with the authoritative counts for the agent to reuse verbatim.
4. Verifies the sum equals the total rule count, AND cross-checks that the headline **Summary count table** matches the counted rows (catches drift even when the sum is still correct).
5. Enforces a **non-breaking space (U+00A0)** between each status icon and its label in table rows, so icons never wrap onto their own line in the rendered table.
6. Cross-checks the headline **Overall Result** against the computed FAIL counts: FAIL ⟺ ≥1 Critical; CONDITIONAL PASS ⟺ 0 Critical and ≥1 Major/Minor; PASS ⟺ no FAILs.
7. Exits with code 1 and prints `FAILED` if any check fails; prints `OK: Reconciliation passed.` on success.

If any `ERROR` is printed, the agent MUST:
- Add missing rule rows (mark as N/A if not applicable, or evaluate them).
- Remove extra or duplicate rows.
- Recount and update the Summary count table so it matches the Detailed Results.
- Re-run the verification until it passes.

The agent MUST NOT save the report as final until the verification script prints `OK: Reconciliation passed.` with zero errors.

### Reporting Counts in Chat (MANDATORY)

After the script prints `OK: Reconciliation passed.`, the agent's chat reply MUST quote the counts **verbatim from the script's `CHAT_SUMMARY:` line**. The agent MUST NOT hand-count, re-summarize, or alter the PASS / Critical / Major / Minor / N/A numbers — or the per-rule severities — when writing the chat summary. The reconciliation script only validates the saved file; an inconsistent chat summary is invisible to it. If the chat summary and the script output ever disagree, the **script output is authoritative**, and the agent MUST correct the chat before responding.

---

## Severity Levels

Each FAIL MUST be classified based on its **observable impact during the validation run**, using this decision tree:

```
Did this failure prevent the agent from completing the next step?
  YES → Critical
  NO  → Did the application start and produce a correct result despite this failure?
          YES → Was the issue found only through code/doc review (not runtime behavior)?
                  YES → Minor
                  NO  → Major
          NO  → Critical
```

| Severity | Decision criterion |
|----------|-------------------|
| **Critical** | The agent could not proceed to the next step, OR the application did not produce a verifiable result. |
| **Major** | The agent completed all steps and verified the result, but observed a runtime issue (poor UX, insecure behavior, unclear errors). |
| **Minor** | The agent completed all steps successfully. The issue was found only through inspection of files, docs, or config — not through runtime failure. |

The agent MUST NOT assign severity based on opinion. It MUST reference the specific step where the failure was observed or state "found during inspection" for Minor items.

### Severity consistency (deterministic guards)

These guards remove judgment drift on identical facts (the same finding must not swing between Major and Critical across runs):

1. **Verified output caps verification-blocking severity.** If rule **7.6 (Functional output verified) is PASS**, the application produced a verifiable result. Therefore a missing or bring-your-own sample input (rules **12.1**, **12.2**) is **NOT** "no verifiable result" — it is **at most Major, never Critical**. The agent MUST apply this when assigning severity (it is a documented decision rule the agent enforces itself — the reconciliation script does not check it).
2. **One root cause = one defect.** Do NOT record the same underlying gap as Critical on two different rules. Rules 12.1 and 12.2 are distinct: **12.1** = a ready-to-use sample input is bundled or auto-downloaded; **12.2** = a command or container to simulate the live input is documented. A documented simulator that requires the user to point it at their own file **still satisfies 12.2 (PASS)** — the absence of a bundled file is solely a **12.1** finding.

---

## Overall Result Criteria

| Result | Condition |
|--------|-----------|
| **PASS** | Zero FAIL at any severity. |
| **CONDITIONAL PASS** | Zero Critical FAILs. One or more Major or Minor FAILs exist. |
| **FAIL** | One or more Critical FAILs. The user cannot reach a working application. |

---

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

---

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

