<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Jira Bug Scrub Skill: High-Level Workflow

```mermaid
flowchart TD
    A[Start: issue key, Jira URL, or JQL] --> B[Load BKM rules, scrub rules, automation policy, and templates]
    B --> C[Record mode, scope, issue limit, language, and write authorization]
    C --> D[Connect to Jira and discover fields, allowed values, and transitions]
    D --> E{Readable Jira data available?}
    E -- No --> E1[Mark affected review as BLOCKED]
    E -- Yes --> F[Resolve issue set and paginate JQL results]
    F --> G[Sort keys and create a stable issue snapshot]
    G --> H[Generate JSON skeleton with all 62 rules for every issue]

    H --> I[Evaluate required fields, title, description, reproduction, impact, commit, and versions]
    I --> J[Evaluate priority, security classification, SLA, ownership, staleness, duplicates, and closure evidence]
    J --> K[Assign rule verdicts and derive issue readiness]
    K --> L[Build one consolidated draft comment and exact proposed action plan]

    L --> M{Mode}
    M -- dry-run --> N[Do not modify Jira]
    M -- apply --> O[Re-read issue and compare updated timestamp]
    O --> P{Issue changed since snapshot?}
    P -- Yes --> Q[Discard stale plan and re-evaluate issue]
    Q --> K
    P -- No --> R{Action authorized and policy criteria met?}
    R -- No --> S[Mark action SKIPPED or BLOCKED]
    R -- Yes --> T[Post one comment, update approved fields, or perform approved transition]
    T --> U[Re-read Jira and verify each applied change]

    E1 --> V[Finalize machine-readable result]
    N --> V
    S --> V
    U --> V
    V --> W[Run result checker: coverage, readiness, placeholders, and mutation consistency]
    W --> X{Checker passes?}
    X -- No --> Y[Correct result inconsistencies]
    Y --> W
    X -- Yes --> Z[Produce human scrub report with findings, drafts, actions, and mutation statement]
```

## Outcome States

| State | Meaning |
|-------|---------|
| `READY` | All applicable checks pass. |
| `READY WITH FOLLOW-UP` | Only non-blocking information or maintenance remains. |
| `NEEDS INFO` | At least one blocking item requires submitter or owner input. |
| `BLOCKED` | Jira data or permissions prevented a complete review. |

## Safety Boundary

`dry-run` is the default and never modifies Jira. In `apply`, the skill executes
only pre-planned and authorized actions, checks for concurrent issue updates,
and verifies the resulting Jira state. Priority, security, resolution, and
terminal workflow changes have additional authorization requirements.