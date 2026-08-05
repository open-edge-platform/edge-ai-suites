<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Evaluation Model Reference

This file is part of the `onboarding-validation` skill instructions.

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

## Verdict per Rule

For each rule, report one of:

- **✅ PASS**: The application meets the rule.
- **❌ FAIL**: The application does not meet the rule. Include the reason and evidence.
- **⚪ N/A**: The rule does not apply to this application.

The Result cell in the Detailed Results table MUST be prefixed with the status emoji (`✅` / `❌` / `⚪`), joined to the word by a **non-breaking space** (Unicode U+00A0, not a regular space) — e.g. `✅` + U+00A0 + `PASS` — so the icon can never wrap onto its own line. GitHub Markdown supports neither cell background colors nor `<nobr>`; emoji + non-breaking space is the portable equivalent.

The Summary count table header MUST carry matching icons, each joined to its label by a non-breaking space: `✅ PASS`, `🔴 FAIL (Critical)`, `🟠 FAIL (Major)`, `🟡 FAIL (Minor)`, `⚪ N/A` (the `Total Rules` column stays plain).

> **Enforced.** `scripts/reconcile-report.sh` FAILS the report if any status icon in a table row is followed by a regular space instead of U+00A0. A regular space here is a common, easy-to-miss regression — the script catches it so the icon never wraps to its own line in the rendered table.

## Reconciliation Script Checks

`scripts/reconcile-report.sh` (relative to this skill file) runs in two modes. With `--emit-skeleton`
it writes the report skeleton — one Detailed Results row per rule, both tables, every anchor — from
the same constants it validates against (see `report-format.md`, *Report format contract*). Without
arguments it performs these checks, in order:

1. Asserts the **Detailed Results** and **Summary count** table headers before reading any column, so an inserted or reordered column fails loudly instead of shifting the counts.
2. Requires the run-identity rows **`AI agent`** and **`Model`** to be present and non-empty.
3. Extracts rule IDs from the rules file (sections 1–16 only — it stops at the `## Rationale` heading) and from the report's Detailed Results table, and detects missing, extra, or duplicate rule IDs.
4. Counts per-category verdicts (PASS, Critical, Major, Minor, N/A) by reading the **Result and Severity columns only** — never the whole line — asserts every row resolves to exactly one verdict (and each FAIL to exactly one severity), and prints a `CHAT_SUMMARY:` line with the authoritative counts for the agent to reuse verbatim.
5. Verifies the sum equals the total rule count, AND cross-checks that the headline **Summary count table** matches the counted rows (catches drift even when the sum is still correct).
6. Enforces a **non-breaking space (U+00A0)** between each status icon and its label in table rows, so icons never wrap onto their own line in the rendered table.
7. Cross-checks the headline **Overall Result** against the computed FAIL counts: FAIL ⟺ ≥1 Critical; CONDITIONAL PASS ⟺ 0 Critical and ≥1 Major/Minor; PASS ⟺ no FAILs.
8. Recomputes the **Overall UX Score** and its band from the verdicts, using the dimension table it reads directly from `report-format.md`, and fails on any mismatch or on a rule ID that table does not cover. The score is mandatory for every report.
9. Exits with code 1 and prints `FAILED` if any check fails; prints `OK: Reconciliation passed.` on success.

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

## Overall Result Criteria

| Result | Condition |
|--------|-----------|
| **PASS** | Zero FAIL at any severity. |
| **CONDITIONAL PASS** | Zero Critical FAILs. One or more Major or Minor FAILs exist. |
| **FAIL** | One or more Critical FAILs. The user cannot reach a working application. |

> **Why the count is canonical — and there is NO deduplication.** The canonical rule count is whatever `scripts/reconcile-report.sh` extracts — currently **76**. The script counts only the rule rows in sections 1–16; it stops at the `## Rationale for Key Thresholds` heading, so those explanatory rows are never counted (regardless of how that table is formatted). The script does **NOT** deduplicate rule IDs — a duplicate ID is an error it reports, not something it silently merges. The agent MUST NOT explain the count by claiming IDs are "deduplicated."
