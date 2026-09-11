<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Jira Feature Test Generator: High-Level Workflow

```mermaid
flowchart TD
    A[Start: component, application, or repository path] --> B[Load skill rules and record mode, project, limit, and optional baseline]
    B --> C[Connect to Jira through MCP and discover Acceptance Criteria field]
    C --> D{Readable Jira data available?}
    D -- No --> D1[Mark affected Features as BLOCKED]
    D -- Yes --> E[Resolve exact Jira component]
    E --> F[Search and paginate all Features without a status filter]
    F --> G[Fetch descriptions, criteria, comments, versions, links, and workflow context]

    G --> H[Normalize Acceptance Criteria into stable AC identifiers]
    H --> I[Classify each criterion as READY, PARTIAL, NOT_TESTABLE, or CONFLICTED]
    I --> J[Run local test coverage scanner]
    J --> K{All candidate test files parsed?}
    K -- No --> K1[Report parse errors and mark uncertain coverage as BLOCKED]
    K -- Yes --> L[Read pytest markers, structured docstrings, and Robot tags]
    L --> M[Match exact ITEP keys and AC identifiers]
    M --> N[Assign Feature coverage verdicts]
    N --> O{Baseline supplied?}
    O -- Yes --> P[Classify new gaps, known gaps, regressions, and newly covered Features]
    O -- No --> Q[Create current coverage snapshot]
    P --> R{Mode}
    Q --> R

    R -- analyze --> S[Do not modify repository tests]
    R -- generate --> T[Select uncovered READY criteria]
    T --> U[Inspect nearest test module, fixtures, helpers, markers, and validation command]
    U --> V[Generate or extend Python or Robot Framework tests]
    V --> W[Add mandatory Jira Feature and criterion metadata]
    W --> X[Register pytest marker when needed]
    X --> Y[Run focused collection, syntax check, or executable test]
    Y --> Z{Validation result}
    Z -- Passed --> Z1[Record generated test as validated]
    Z -- Collection only --> Z2[Record test as collected but not executed]
    Z -- Failed --> Z3[Report failure without claiming coverage success]

    D1 --> AA[Build traceability matrix and machine-readable report]
    K1 --> AA
    S --> AA
    Z1 --> AA
    Z2 --> AA
    Z3 --> AA
    AA --> AB[Save JSON baseline and return coverage summary, gaps, changes, and validation evidence]
```

## Coverage States

| State | Meaning |
|-------|---------|
| `COVERED` | Every testable criterion has an exact, collected test reference. |
| `PARTIALLY_COVERED` | At least one criterion is covered, but coverage is incomplete or only feature-level. |
| `UNCOVERED` | No automated test contains the exact Jira Feature key. |
| `NOT_AUTOMATABLE` | All criteria describe work that cannot be validated by an automated test. |
| `NOT_APPLICABLE` | Explicit evidence shows the Feature is outside the selected repository or version scope. |
| `BLOCKED` | Missing Jira or repository evidence prevents a reliable verdict. |

## Generation Boundary

`analyze` is the default and never changes test files. `generate` creates tests
only for criteria classified as `READY`. Generated pytest tests carry a
`jira_feature` marker with the exact `ITEP-xxxxx` key and `AC-x` criterion;
other Python frameworks use structured docstrings, and Robot Framework uses
structured tags. Missing expectations or thresholds are reported for human
clarification instead of being invented.