---
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
name: onboarding-validation
description: >-
  Validate the get-started experience of Open Edge Platform (OEP) software
  components from the perspective of a first-time user. Use this skill when a
  user wants an AI agent to follow onboarding or deployment documentation
  exactly, validate a Docker Compose or Helm/Kubernetes path, collect evidence,
  apply pass/fail rules, and produce a structured onboarding validation report
  with a process log. Trigger on onboarding validation, first-time-user
  validation, documentation-driven deployment checks, reproducibility checks,
  UX scoring, and release-readiness reviews for OEP components including Edge
  AI Suite and Edge AI Libraries applications. Do not use this skill for
  debugging, fixing application code, or ad hoc exploratory testing outside
  the documented path.
license: Apache-2.0
compatibility: >-
  Requires a bash-compatible shell, git, and access to the target environment.
  The validated application may additionally require Docker Compose or
  Helm/Kubernetes, depending on the documented deployment method.
metadata:
  author: open-edge-platform
  version: "1.13.0"
  tags: validation, onboarding, qa, docker-compose, helm, kubernetes, edge-ai
allowed-tools: bash git
---

# User Onboarding Experience Validation

Validate the get-started experience of a containerized application from the perspective of a first-time user. The agent follows the documentation exactly, collects evidence, evaluates pass/fail rules, and produces a structured report plus a verbatim process log.

| Field | Value |
|-------|-------|
| Skill ID | onboarding-validation |
| Version | 1.13.0 |
| Date | 2026-07-31 |
| Trigger | Validation prompt (see `example-prompts/01-validate-onboarding.md`) |
| Input | GitHub URL of application + deployment method |
| Output | Markdown report in `./validation-reports/` + process log in `./validation-logs/` |
| Rules | `references/rules-onboarding-validation.md` (**normative**) |
| Charter | `references/rules-charter.md` (**normative**) |
| Checker | `scripts/reconcile-report.sh` (also generates the report skeleton) |
| Benchmark | `benchmark.md` — validation runs, eval coverage, open gaps (maintainers only; not read during a run) |

> **Inherits `references/rules-charter.md`.** This skill ships with the full charter so it remains self-contained after installation. The operational detail here (isolation, "No workarounds", reconciliation, faithful reporting) is the concrete *realization* of those principles, not a replacement — if anything here appears to conflict with the bundled charter, **the charter wins**.

---

## When to Use

Use this skill when the user wants to:

- Validate the get-started experience of a containerized application as a first-time user.
- Check whether Docker Compose or Helm/Kubernetes onboarding documentation is reproducible.
- Produce a structured onboarding report with per-rule PASS / FAIL / N/A verdicts.
- Audit release readiness or onboarding UX for Open Edge Platform (OEP) software components, including Edge AI Suite and Edge AI Libraries applications.

Do not use this skill to:

- Debug, patch, or improve the application under test.
- Explore undocumented alternative deployment paths.
- Perform general code review that is unrelated to the documented onboarding path.

---

## Purpose

Validate the get-started experience of Open Edge Platform (OEP) software components from the perspective of a first-time user. The agent follows the documentation exactly and reports pass/fail for each rule.

---

## References

Read all files listed below in full before starting step 1; they are part of this skill's instructions, not optional background.

| File | Purpose | Status |
|------|---------|--------|
| `references/rules-onboarding-validation.md` | Pass/fail criteria (76 rules) | **normative** |
| `references/rules-charter.md` | Non-negotiable principles | **normative** |
| `references/evaluation-model.md` | Evidence model, verdict semantics, severity, overall result, checker logic | required |
| `references/report-format.md` | Report structure, UX scoring model, formatting contract | required |
| `references/clone-and-refs.md` | Branch/tag mismatch and submodule ref handling | required |

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
   echo "=== Run identity: agent=<harness> model=<model id or 'unknown (self-reported)'> ==="
   ```
   The persistent SSH terminal makes this a faithful, verbatim record of commands + outputs. The run identity line is the first entry: it names the harness and the model executing this run, and the same two values go into the report's Summary rows `AI agent` and `Model` (both mandatory — see `references/report-format.md`). The agent MUST state only what it knows about itself and MUST NOT invent a model version. As you work, **mark each phase in the log** so it reads step by step — e.g. `echo "=== Step 4: clone (ref=<ref>) ==="` — and echo a one-line note before any judgement the chat would otherwise explain (severity calls, skips, retries), e.g. `echo "NOTE: rule 12.1 FAIL Major — no bundled sample"`. The log is saved next to the report at the end (see `references/report-format.md`).
2. **Clone from scratch.** The agent MUST NOT use any pre-existing copy of the application from the workspace. All commands MUST start from the fresh clone as a first-time user would. The prompt's `GITHUB_URL` is a GitHub **web URL** (e.g. `…/tree/<ref>/<path>`), not a `git clone` target — extract the base repo, `<ref>`, and `<path>` from it; clone the base repo at `<ref>`, then `cd` into `<path>`. If the `GITHUB_URL` folder contains more than one application, the prompt's **`Name`** selects which one to validate — scope the clone and follow the get-started for that sub-app only.
3. **Use only the cloned documentation.** After cloning, the agent MUST read and follow get-started instructions exclusively from the cloned repository — not from any workspace copy. This ensures the tested docs match the tested code.
   - **Documentation path selection.** The agent MUST scan the application's root `README.md` **from top to bottom** and select the **first section** whose heading clearly serves the purpose of guiding a new user through installation and first run. Common headings include "Get Started", "Getting Started", "Quick Start", "Quickstart", "Installation", "Setup", "Deploy", "Deployment", "Deployment Options", or similar — the exact wording may vary, but the intent must be unambiguous. The agent MUST NOT skip ahead to a shorter path or cherry-pick a different section — this tests the experience of a real first-time user who reads from the top. If a simplified quick-start exists below the fold but the first installation section is a full get-started guide, the agent follows the full guide and notes the quick-start in "Documentation path followed".
   - **Record every document visited.** As the agent follows the instructions, it MUST record every documentation page and section heading it reads, in order. This list goes into the report's "Documentation path followed" field. It reveals how many pages and sections the user must navigate to deploy — a concrete measure of onboarding complexity.
4. **Branch/Tag checkout.** If the validation prompt specifies a branch or tag, the agent MUST:
   - **The agent clones the prompt's `<ref>` (step 2), never the docs' clone target.** The version under test is fixed by the prompt's `GITHUB_URL`, so the run stays deterministic even when the get-started clone command points elsewhere. The agent MUST NOT rewrite or "fix" the documented `git clone` to make it match the intended ref (that is a forbidden workaround — step 6); it reproduces the pinned ref for its own test and reports the documented command **as written**.
   - Apply the full branch/tag mismatch and submodule handling contract in `references/clone-and-refs.md`.
5. **Single linear execution.** The agent MUST NOT restart, re-clone, or redo steps. If a step fails, record the failure and continue. If the agent needs to redo a step due to its own procedural error (not an app bug), it MUST document this in the "Execution Notes" section of the report.
6. **No workarounds.** The agent MUST NOT debug, fix, or work around deployment issues. If a command fails, the agent MUST record the failure as-is and move on. The agent MUST NOT: modify source code, add missing environment variables, change ports, fix typos in docs commands, or apply any fix not explicitly documented. The goal is to test the documented path — not to prove the app can work with effort.
7. **Cleanup using only documented commands.** Use exactly `docker compose down` (or `helm uninstall`, or `docker stop && docker rm`) as the application documents. If additional cleanup is needed (e.g., root-owned files on host), record this as evidence for rule 8.2.

---

## Completeness and Reconciliation (MANDATORY)

Before saving the report, the agent MUST run these checks and fix any failure:

1. **Cover every rule.** The Detailed Results table MUST contain exactly one row for every rule ID in the rules file of the stated Rules Version — including sections that seem irrelevant. If a rule does not apply, mark it **N/A**; NEVER omit it or stop early. Skipping sections (e.g., 15.x, 16.x) is not allowed.
2. **Tally from the table.** The five summary counts (PASS, Critical, Major, Minor, N/A) MUST be obtained by counting the Detailed Results rows — not estimated or carried over from another report.
3. **Reconcile.** PASS + Critical + Major + Minor + N/A MUST equal the number of rule rows, and that number MUST equal the rule count of the stated Rules Version. Put that number in the "Total Rules" column. These counts come ONLY from the Detailed Results table.
4. **Narrative sections group, but MUST cover.** "Critical Issues" and "Recommendations" are organized by root cause, so their item counts need NOT equal the defect counts — related rules MAY be combined into one item. Coverage is still mandatory: every Critical FAIL MUST be named in "Critical Issues"; every FAIL (any severity) MUST be addressed by at least one recommendation; and no rule may appear in "Critical Issues" unless it is marked Critical in the table.

### Runtime Verification (MANDATORY)

The agent MUST NOT hand-write the report structure. It MUST create the report file with the bundled
generator, which emits one Detailed Results row per rule plus every section the checker expects:

```bash
export RULES_FILE="<absolute-path-to-this-skill>/references/rules-onboarding-validation.md"
export REPORT_FILE="<absolute-path-to-generated-report>"
./scripts/reconcile-report.sh --emit-skeleton > "$REPORT_FILE"
```

The generator and the checker are the same script and share one definition of the format, so a
skeleton is always structurally valid; only its **content** is missing.

The manual tally that fills the Summary counts is a starting point, not the final authority. After
filling in the report file, the agent MUST run the reconciliation and fix any discrepancy before
considering the report complete:

```bash
./scripts/reconcile-report.sh
```

Run the command above **from this skill directory** so `./scripts/reconcile-report.sh` resolves to the bundled checker.

For the full checker contract (ordered checks, verdict extraction rules, severity model, and result criteria), follow `references/evaluation-model.md`.

If any `ERROR` is printed, the agent MUST:
- Add missing rule rows (mark as N/A if not applicable, or evaluate them).
- Remove extra or duplicate rows.
- Recount and update the Summary count table so it matches the Detailed Results.
- Re-run the verification until it passes.

The agent MUST NOT save the report as final until the verification script prints `OK: Reconciliation passed.` with zero errors.

### Reporting Counts in Chat (MANDATORY)

After the script prints `OK: Reconciliation passed.`, the agent's chat reply MUST quote the counts **verbatim from the script's `CHAT_SUMMARY:` line**. The agent MUST NOT hand-count, re-summarize, or alter the PASS / Critical / Major / Minor / N/A numbers — or the per-rule severities — when writing the chat summary. The reconciliation script only validates the saved file; an inconsistent chat summary is invisible to it. If the chat summary and the script output ever disagree, the **script output is authoritative**, and the agent MUST correct the chat before responding.
