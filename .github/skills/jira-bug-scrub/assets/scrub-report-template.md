<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Jira Bug Scrub Report Template

Use this structure for every run. Replace placeholders and remove instructional
text. For a single issue, keep the run summary and one issue section. For JQL,
include every selected key in the compact table, including blocked issues.

```markdown
# Jira Bug Scrub Report

## Run Summary

| Field | Value |
|-------|-------|
| Timestamp | `<ISO-8601 with timezone>` |
| Target | `<issue key/URL or exact JQL>` |
| Mode | `dry-run` / `apply` |
| Project scope | `<projects observed>` |
| Issue limit | `<max_issues>` |
| Issues matched | `<Jira total>` |
| Issues selected | `<processed count>` |
| Language | `English` |
| Stale policy | `<priority thresholds or caller override>` |
| Write authorization | `<none or exact authorized scope>` |

| READY | READY WITH FOLLOW-UP | NEEDS INFO | BLOCKED |
|-------|----------------------|------------|---------|
| `<n>` | `<n>` | `<n>` | `<n>` |

**Mutation statement**: `Jira was not modified (dry-run).` / `Jira was modified; all applied changes were verified.` / `Jira was partially modified; see per-issue failures.` / `Jira was not modified because all writes were blocked or skipped.`

## Issues

| Key | Summary | Priority | Status | Assignee | Updated | Readiness | Blocking findings | Proposed actions | Applied actions |
|-----|---------|----------|--------|----------|---------|-----------|-------------------|------------------|-----------------|
| `<KEY>` | `<summary>` | `<priority>` | `<status>` | `<assignee/unassigned>` | `<timestamp>` | `<result>` | `<count>` | `<count>` | `<count>` |

## `<KEY>` - `<Summary>`

**Snapshot**

| Field | Observed value |
|-------|----------------|
| Project / Type | `<project>` / `<issue type>` |
| Component | `<value/missing>` |
| Affects Version | `<value/missing>` |
| Fix Version | `<value/missing>` |
| Priority | `<value>` |
| Suspected Security Defect | `<value/unavailable>` |
| Status / Resolution | `<status>` / `<resolution>` |
| Assignee / Reporter | `<assignee>` / `<reporter>` |
| Created / Updated | `<created>` / `<updated>` |
| Last meaningful update | `<timestamp and evidence>` |

**Rule findings**

| Rule | Verdict | Finding severity | Evidence | Required information or action |
|------|---------|------------------|----------|--------------------------------|
| `<BKM/SCRUB-ID>` | `PASS/NEEDS INFO/ACTION/N/A/BLOCKED` | `Blocking/Non-blocking/-` | `<field/comment evidence>` | `<specific request/action>` |

Include every non-PASS finding. Include PASS rows when they are important to a Priority, security, transition, or closure decision. The complete rule evaluation may be attached as a machine-readable artifact when the run processes many issues.

**Priority assessment**: `<aligned / needs clarification / proposed increase / proposed change withheld>`

Evidence: `<impact, scope, workaround, reproducibility, stability, privacy/IP/legal/security facts>`

**SLA and staleness**: `<state, source timestamps, applicable calendar/freeze assumptions, or "SLA not determined">`

**Duplicate candidates**

| Candidate | Matching evidence | Differing/unknown evidence | Action |
|-----------|-------------------|----------------------------|--------|
| `<KEY or none>` | `<facts>` | `<facts>` | `<human review/link/no action>` |

**Draft consolidated comment**

> `<exact comment text, or "No comment needed: reason">`

**Proposed mutations**

| Risk | Action | Old value | New value | Evidence / entry criteria | Authorization |
|------|--------|-----------|-----------|---------------------------|---------------|
| `Low/Medium/High` | `<comment/field/transition>` | `<old>` | `<new>` | `<facts>` | `<authorized/withheld>` |

**Applied and verified mutations**

| Action | Result | Verification | Error category |
|--------|--------|--------------|----------------|
| `<action or none>` | `<APPLIED/SKIPPED/BLOCKED/FAILED>` | `<observed post-write state>` | `<none/PERMISSION/VALIDATION/CONFLICT/RATE_LIMIT/CONNECTIVITY/UNKNOWN>` |

**Readiness**: `<READY / READY WITH FOLLOW-UP / NEEDS INFO / BLOCKED>`

## Run-Level Blockers and Notes

- `<permissions, field ambiguity, inaccessible issue, result truncation, concurrency conflicts, or none>`
```

## Mandatory Machine-Readable Record

Every run MUST include the complete JSON artifact described in
`../references/result-format.md`. It supplements, not replaces, the human
report. The abbreviated shape below is only an orientation; generate the real
file with `scripts/check_scrub_result.py --emit-skeleton` so every rule is
present.

```json
{
  "timestamp": "<ISO-8601>",
  "target": "<key or JQL>",
  "mode": "dry-run",
  "jira_modified": false,
  "issues": [
    {
      "key": "ITEP-00000",
      "snapshot_updated": "<ISO-8601>",
      "readiness": "NEEDS INFO",
      "rule_evaluations": [
        {
          "rule_id": "BKM-16",
          "verdict": "NEEDS INFO",
          "severity": "Blocking",
          "evidence": "Steps to reproduce section is missing",
          "required_action": "Ask the reporter for numbered reproduction steps"
        }
      ],
      "draft_comment": "Bug scrub follow-up...",
      "proposed_actions": [],
      "applied_actions": []
    }
  ]
}
```