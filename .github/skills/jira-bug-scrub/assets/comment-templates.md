<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Jira Bug Scrub Comment Templates

Use these patterns to draft one consolidated English comment per issue. Adapt
only the bracketed content. Remove unused bullets and all placeholder text
before posting. Never post a template verbatim.

Comments must be factual, neutral, concise, and based on the issue snapshot.
Do not include internal rule IDs unless the project team explicitly finds them
useful; rule IDs always remain in the scrub report.

## Missing Information

```text
Bug scrub follow-up

Thank you for reporting this issue. The current description does not yet contain enough information to reproduce and triage the observed behavior. Please update the Description with:

- [specific missing fact and why it is needed]
- [specific missing fact and why it is needed]

Please keep the durable reproduction details in the Description rather than only in comments. Redact credentials, tokens, personal data, and other sensitive information from logs or attachments.
```

Choose only applicable requests from this question bank:

- Which build, release, and commit/PR were tested?
- What platform/cluster, OS, browser, hardware, and configuration were used?
- What preconditions, input, and numbered steps reproduce the issue?
- At which step does the behavior diverge, and what is the exact expected result?
- What exact behavior or error is observed? Please include a minimal redacted log
  excerpt or attachment reference.
- How often does it reproduce, and across how many attempts?
- Which platforms/configurations are affected and known not to be affected?
- Is this a regression? If known, what is the last working version or commit?
- Is there a workaround? If yes, what are its limitations? If none is known,
  please state that.
- What user, release, or functional impact supports the current Priority?
- Which Component owns the issue, and which Affects/Fix Version should be used?

## Stale Update Request

```text
Bug scrub follow-up

This issue has no meaningful update since [date]. Please add a current status update covering:

- progress or new isolation/reproduction evidence since the previous update;
- the next action and owner;
- any current blocker and linked dependency;
- the target date/ETA, or why an estimate is not currently available;
- the fix PR/commit or verification result, if available.

The issue will remain open; this request does not imply closure or a Priority change.
```

## Priority Clarification

```text
Bug scrub follow-up

The current issue does not contain enough impact information to confirm Priority [current priority]. Please clarify:

- whether a basic/main flow is blocked or only partially impaired;
- affected users, platforms, and release scope;
- whether results are incorrect, incomplete, or inconsistent;
- reproducibility and stability/crash frequency;
- available workaround or recovery and its limitations;
- any privacy, IP, legal, or suspected security impact.

Priority will not be changed until this evidence is available.
```

## Suspected Security Follow-Up

```text
Security triage follow-up

The issue contains indicators of a potential security defect. Please confirm that the "Suspected Security Defect" field and the approved security-defect workflow are being used.

Do not add credentials, secrets, personal data, exploit details, or other sensitive material to this general Jira comment. Share sensitive evidence only through the approved security channel.
```

Do not ask the reporter to prove exploitability before suspected-security
classification. Do not quote sensitive details already present in the issue.

## Ownership or Planning Clarification

```text
Bug scrub follow-up

The issue is actionable, but ownership/planning needs clarification before the next workflow step. Please confirm:

- owning Component/team: [current evidence or question];
- assignee/next-action owner: [current evidence or question];
- Affects Version: [question];
- target Fix Version or approved backlog disposition: [question];
- linked blocker/dependency and its owner, if applicable: [question].
```

## Duplicate Candidate Review

```text
Bug scrub observation

[candidate key] may describe related behavior because [specific matching evidence]. The current evidence differs or remains unclear in these areas: [specific differences/unknowns].

Please confirm whether both issues share the same root behavior and scope before any Duplicate resolution is applied.
```

Never call an issue a duplicate based only on title similarity, a shared test,
or a common scanner/tool name.

## Closure Evidence Request

```text
Bug scrub follow-up

Before this issue can be verified as resolved, please add:

- implementing PR/commit and Fix Version;
- retest environment and tested build/commit;
- the original reproduction steps that were rerun;
- observed verification result against Expected behavior;
- verifier or automated test reference;
- confirmation that no blocking information request remains.
```

## Reopened Issue Request

```text
Bug scrub follow-up

Please document why the previous resolution is no longer valid, including the current reproduction or failed verification, tested build/commit, environment, exact result, and any difference from the original report.
```

## Cannot Reproduce Review

```text
Bug scrub follow-up

Before using a Cannot Reproduce resolution, please record the tested environment/version, exact steps, attempt count or duration, observed results, and the specific additional evidence requested from the reporter.
```

## No Comment Needed

Do not post a comment when:

- all applicable rules pass;
- the only action is a deterministic field correction that requires no human
  response and the caller authorized it;
- an unresolved existing comment already requests the same facts;
- the draft would add no concrete question, decision, or new evidence;
- the issue is inaccessible or the comment permission is unavailable.

Report the reason in the scrub report instead.