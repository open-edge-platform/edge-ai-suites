<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Jira Bug Scrub Rules

This reference defines the checks for the `jira-bug-scrub` skill.

## Authority and Precedence

Rules with a `BKM-` prefix implement the user-provided four-page `How to open a
bug` guide. The guide was supplied on 2026-09-03 and is normative. Rules with a
`SCRUB-` prefix are general bug-scrub practices added for actionable triage,
backlog health, and safe automation. A `SCRUB-` rule MUST NOT weaken or
contradict a `BKM-` rule.

When local Jira workflow configuration requires a stricter rule, report both
requirements and follow the stricter one. Never silently replace the BKM with a
team convention.

## Evaluation Semantics

Evaluate every rule for every selected bug:

| Verdict | Meaning |
|---------|---------|
| `PASS` | Reliable issue evidence satisfies the rule. |
| `NEEDS INFO` | A human must provide or clarify evidence. |
| `ACTION` | The scrubber can perform a justified maintenance action. |
| `N/A` | The rule does not apply; evidence explains why. |
| `BLOCKED` | Permissions or unavailable data prevent evaluation. |

Finding severity is independent of Jira priority:

| Finding severity | Meaning |
|------------------|---------|
| `Blocking` | The bug cannot be reproduced, triaged, assigned, safely handled, or closed. |
| `Non-blocking` | The bug is actionable, but planning or documentation hygiene needs correction. |

Missing technical information is normally `NEEDS INFO`. A deterministic field
or workflow correction supported by existing evidence is normally `ACTION`.
Do not use `ACTION` when a human decision or unknown value is required.

## BKM Rules: Project and Required Fields

| ID | Check | Pass criteria | Default severity |
|----|-------|---------------|------------------|
| BKM-01 | Correct project | Project is `EdgeSW (ITEP)` / key `ITEP`, unless the caller explicitly requests an audit of another project using the same BKM. | Blocking |
| BKM-02 | Correct issue type | Issue Type is `Bug`. | Blocking |
| BKM-03 | Summary present | Summary is non-empty and contains a problem statement. | Blocking |
| BKM-04 | Component present | At least one valid Component is selected. | Blocking |
| BKM-05 | Description present | Description is non-empty and provides more than a test result or assertion. | Blocking |
| BKM-06 | Affects Version present | `Affects Version/s` identifies the version where the issue was observed. | Blocking |
| BKM-07 | Fix Version present | `Fix Version/s` contains the approved target or backlog value used by the project. | Non-blocking |
| BKM-08 | Priority present | Priority is set to one of the project-supported P1/P2/P3/P4 levels. | Blocking |
| BKM-09 | Security field handled | For a suspected security defect, `Suspected Security Defect` is set to `Yes`. For other bugs, no security conclusion is invented. | Blocking when security indicators exist; otherwise N/A |

Do not manufacture Component, versions, Priority, or security classification.
When a required value is absent and no reliable evidence determines it, request
the value from the reporter/owner.

## BKM Rules: Meaningful Summary

| ID | Check | Pass criteria | Default severity |
|----|-------|---------------|------------------|
| BKM-10 | Summary template | Summary follows `[Component][Area] Short description of the issue`; omit `[Area]` only when no meaningful sub-area exists and the component remains clear. | Non-blocking |
| BKM-11 | Concise and descriptive | A reader can identify what is wrong and where without opening the issue. | Blocking when the defect is ambiguous; otherwise Non-blocking |
| BKM-12 | Problem, not test result | Summary does not contain a test name/ID and does not merely state that a test failed. It names the underlying observed problem. | Blocking |
| BKM-13 | Neutral and factual | Summary does not assert an unverified root cause and is free of obvious spelling errors. | Non-blocking |

Accept flexible capitalization and product naming. Do not rewrite a clear title
solely for stylistic preference.

## BKM Rules: Description Structure

The Description must contain these recognizable sections. Markdown, Jira wiki
markup, or equivalent localized headings are acceptable. A section containing
only a placeholder such as `TBD`, `N/A`, `-`, or copied template text is empty
unless it explains why the section is not applicable.

| ID | Check | Pass criteria | Default severity |
|----|-------|---------------|------------------|
| BKM-14 | Issue summary | `Issue summary` gives context, location, and nature of the issue in one or two useful sentences. | Blocking |
| BKM-15 | Impact | `Impact` explains affected functionality/users and supports priority assessment. | Blocking |
| BKM-16 | Steps to reproduce | `Steps to reproduce` contains a clear numbered sequence that another person can execute. | Blocking |
| BKM-17 | Expected behavior | `Expected behavior` states the correct outcome and, where practical, identifies the corresponding reproduction step. | Blocking |
| BKM-18 | Actual behavior | `Actual behavior` states the observed outcome, identifies the corresponding step where practical, and includes the exact relevant error or symptom. | Blocking |
| BKM-19 | Characterization / Isolation input | The section contains relevant platform/cluster, app version, OS/browser, logs/screenshots references, reproduction scope/rate, and isolation results. Only context relevant to the bug is required. | Blocking when reproduction depends on it; otherwise Non-blocking |
| BKM-20 | Commit | `Commit` identifies the tested or introducing commit/PR. A full SHA is preferred; an unambiguous short SHA, PR link, or immutable release tag is acceptable. | Blocking for active code investigation; otherwise Non-blocking |
| BKM-21 | Underlying issue explained | Description does not conclude only that a test failed; it explains the underlying behavior or error. | Blocking |
| BKM-22 | Internal consistency | Summary, versions, environment, steps, expected result, actual result, and attachments do not materially contradict one another. | Blocking |

Information buried only in comments does not make the Description compliant.
Use it as evidence for a proposed Description update, but ask the reporter/owner
to consolidate durable reproduction data into the Description.

## BKM Rules: Priority

Assess priority from documented impact, scope, workaround, and stability. Do not
equate scanner severity, log level, customer emotion, or submitter seniority with
Jira priority.

| ID | Priority | BKM definition |
|----|----------|----------------|
| BKM-23 | P1 - Stopper | Complete system/subsystem/program failure; a basic feature is broken; repeated crashes or instability make the app unusable; or privacy, IP, or legal implications exist. Resolve immediately. |
| BKM-24 | P2 - High | The system produces incorrect, incomplete, or inconsistent results, or usability of a main flow is significantly impaired for a meaningful user base. No practical workaround exists, or a severe issue has a clear workaround/recovery. Resolve before release in normal development. |
| BKM-25 | P3 - Medium | The issue has noticeable but limited functional impact, is outside the main focus flow, causes a minor malfunction, or affects a small user base without impairing fluent use. It may be fixed after release/next release. |
| BKM-26 | P4 - Low | Aesthetic issue, enhancement, standards non-conformance, tiny impact, or rare/specific corner case. It may be fixed in a future major revision or not fixed. |
| BKM-27 | Priority evidence | Description and comments contain enough impact, scope, workaround, and reproducibility evidence to justify the selected priority. |
| BKM-28 | Priority alignment | Current Priority matches the applicable BKM definition. If evidence is ambiguous, request clarification instead of changing Priority. |

Never downgrade P1/P2 automatically. In apply mode, an increase may be proposed
only from explicit evidence and still requires the automation policy's
high-impact-field safeguards.

## BKM Rules: SLA and Security

| ID | Check | Pass criteria | Default severity |
|----|-------|---------------|------------------|
| BKM-29 | P1 SLA before feature freeze | When the run is known to be before feature freeze: assignee response/workaround is present within 2 business days and resolution within 5 business days, including response time. | Blocking |
| BKM-30 | P1 SLA after feature freeze | When the run is known to be after feature freeze: triage is present within 1 business day and resolution within 3 business days, including triage. | Blocking |
| BKM-31 | P2 SLA | Resolution target is within 10 business days. | Non-blocking until breached, then Blocking for release planning |
| BKM-32 | P3 SLA | Resolution target is within 20 business days. | Non-blocking until breached |
| BKM-33 | SLA context known | Feature-freeze state, working calendar, and pause/exclusion policy are known before declaring an SLA breach. Otherwise report `BLOCKED` or an observation, not a breach. | Non-blocking |
| BKM-34 | Suspected security classification | Security indicators trigger explicit review of `Suspected Security Defect`; `Yes` is used for suspected security defects. A `[Security]` title tag may supplement but never replace the field. | Blocking |
| BKM-35 | Security BKM escalation | A suspected security defect is directed to the approved `How to record a security defect in Jira` process. Sensitive details are not copied into a general scrub comment. | Blocking |

Security indicators include authentication/authorization bypass, secret or
personal-data exposure, injection, unsafe code execution, vulnerable dependency
findings, privilege escalation, privacy impact, and IP/legal implications.
Scanner output alone is enough to mark the defect as suspected, not enough to
assert exploitability or final severity.

## General Scrub Rules: Actionability

| ID | Check | Pass criteria | Default severity |
|----|-------|---------------|------------------|
| SCRUB-01 | Reproduction starts from a known state | Preconditions, configuration, data/input, and setup assumptions required by the steps are stated. | Blocking |
| SCRUB-02 | Reproduction is deterministic enough | Reproduction rate or frequency is stated for intermittent issues; timing/race conditions are characterized where relevant. | Blocking |
| SCRUB-03 | Evidence is attached or quoted safely | Relevant logs, screenshots, traces, or output are available and map to Actual behavior. Secrets, tokens, personal data, and unnecessary internal paths are redacted. | Blocking when evidence is required; otherwise Non-blocking |
| SCRUB-04 | Regression status | Issue states whether behavior is a regression and identifies the last known good version/commit when known. | Non-blocking |
| SCRUB-05 | Workaround documented | Known workaround and its limitations are recorded, or the issue explicitly says none is known. | Non-blocking; Blocking when Priority depends on it |
| SCRUB-06 | Acceptance/retest criteria | Expected behavior is specific enough to verify a fix without interpreting intent. | Blocking |
| SCRUB-07 | Scope bounded | Affected platforms, configurations, users, and unaffected comparisons are recorded when known. | Non-blocking; Blocking when assignment/priority depends on it |

## General Scrub Rules: Ownership and Planning

| ID | Check | Pass criteria | Default severity |
|----|-------|---------------|------------------|
| SCRUB-08 | Assignee present | Active work has an explicit assignee. New/untriaged bugs may use the project's triage owner if that is the configured workflow. | Blocking for In Progress; otherwise Non-blocking |
| SCRUB-09 | Component ownership | Selected Component routes the issue to the correct owning team; cross-component impact is represented by links or additional approved components. | Blocking when misrouted |
| SCRUB-10 | Fix target credible | Fix Version is compatible with priority, release scope, and owner plan. Do not infer a release target from Affects Version. | Non-blocking |
| SCRUB-11 | Dependencies linked | Blocking/blocked-by, caused-by, parent, epic, PR, or related bug links are present when the issue text identifies such dependencies. | Non-blocking; Blocking when progress depends on the missing link |
| SCRUB-12 | Duplicate candidates checked | Bounded search considers same component, symptom/error signature, affected version, and environment. A candidate is linked for human confirmation; similarity alone is not a duplicate conclusion. | Non-blocking |
| SCRUB-13 | No conflicting active owner | Assignee, component owner, and comments do not show unresolved ownership conflict. | Blocking |

## General Scrub Rules: Status and Updates

A meaningful update contains at least one of: new reproduction/isolation data,
progress since the prior update, current blocker and owner, next action and
target date, fix PR/commit, test result, or a justified plan/priority/version
change. Automated notifications and mechanical field changes are not meaningful
updates by themselves.

Default update-request thresholds are operational defaults, not PDF SLA rules:

| Priority | Request an update after |
|----------|-------------------------|
| P1 | 2 business days without a meaningful update |
| P2 | 5 business days without a meaningful update |
| P3 | 10 business days without a meaningful update |
| P4 | 20 business days without a meaningful update |

| ID | Check | Pass criteria | Default severity |
|----|-------|---------------|------------------|
| SCRUB-14 | Status matches evidence | Workflow state reflects actual work: new bugs await triage, active bugs show progress, blocked bugs name the blocker, and resolved/done bugs contain closure evidence. | Blocking when state is misleading |
| SCRUB-15 | Meaningful update is current | Time since the last meaningful update is within the configured threshold for Priority. | Non-blocking; Blocking for stale P1/release blockers |
| SCRUB-16 | In-progress update quality | In Progress issues identify progress, next action, owner, blocker if any, and a target/ETA or explain why one is unknown. | Non-blocking |
| SCRUB-17 | Blocked state is actionable | Blocked issues identify the blocker, linked dependency, blocker owner, and next review/checkpoint. | Blocking |
| SCRUB-18 | Needs-info state has a request | If waiting for submitter data, one consolidated comment lists exact missing items and the workflow state reflects that wait when the project provides such a transition. | Non-blocking |
| SCRUB-19 | Reopened reason | Reopened bugs identify failed verification/current reproduction, tested build or commit, and why prior resolution was insufficient. | Blocking |

Never close or downgrade an issue due only to inactivity. Request an update and
use an approved needs-information/stale workflow only when project policy
explicitly provides it.

## General Scrub Rules: Resolution and Closure

| ID | Check | Pass criteria | Default severity |
|----|-------|---------------|------------------|
| SCRUB-20 | Resolution set correctly | Resolved/Done issues have a resolution consistent with the outcome; active issues do not carry a stale resolution. | Blocking |
| SCRUB-21 | Fix reference | Fixed issues link or name the implementing PR/commit and identify Fix Version. | Blocking |
| SCRUB-22 | Verification evidence | Fixed issues include retest environment, tested version/commit, result, and verifier or automated test reference. | Blocking |
| SCRUB-23 | Acceptance criteria met | Verification explicitly demonstrates Expected behavior and covers the original reproduction. | Blocking |
| SCRUB-24 | Duplicate resolution proven | Duplicate closure identifies the canonical issue and evidence that both describe the same root behavior/scope. | Blocking |
| SCRUB-25 | Cannot-reproduce evidence | Cannot Reproduce records attempted environment, version, steps, frequency/attempt count, and evidence requested from the reporter. | Blocking |
| SCRUB-26 | Won't-fix rationale | Won't Fix / As Designed records a decision owner and rationale, including user/release impact. | Blocking |
| SCRUB-27 | No unresolved blockers | No blocking `NEEDS INFO` finding remains when transitioning to Resolved/Done. | Blocking |

## Overall Readiness

Compute readiness from all rule verdicts:

- `READY`: every applicable rule is `PASS`; no action is proposed.
- `READY WITH FOLLOW-UP`: at least one non-blocking `NEEDS INFO` or `ACTION`
  exists and no blocking finding exists.
- `NEEDS INFO`: at least one blocking `NEEDS INFO` or unresolved blocking
  `ACTION` exists.
- `BLOCKED`: required issue data could not be read or evaluated.

An SLA observation does not by itself prove the application defect is more
severe. Report bug priority, scrub readiness, and SLA state separately.