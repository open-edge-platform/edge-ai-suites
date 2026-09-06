<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Machine-Readable Scrub Result

Every run MUST maintain one JSON result as the complete source of truth. The
human report may summarize it, but MUST NOT contradict it.

## Generate the Skeleton

After resolving the issue set and before evaluating issues, run from the skill
directory:

```bash
python3 scripts/check_scrub_result.py --emit-skeleton \
  --issue ITEP-12345 --issue ITEP-12346 > scrub-result.json
```

The generated file contains every rule ID for every issue. Fill all
placeholders. Do not add, remove, duplicate, or reorder rule evaluations.

## Result Schema

```json
{
  "schema_version": "1.0",
  "timestamp": "2026-09-03T12:00:00+00:00",
  "target": "project = ITEP AND issuetype = Bug",
  "mode": "dry-run",
  "jira_modified": false,
  "issues": [
    {
      "key": "ITEP-12345",
      "snapshot_updated": "2026-09-03T11:55:00+00:00",
      "final_updated": null,
      "readiness": "NEEDS INFO",
      "rule_evaluations": [
        {
          "rule_id": "BKM-01",
          "verdict": "PASS",
          "severity": "-",
          "evidence": "Project key is ITEP",
          "required_action": null
        }
      ],
      "draft_comment": "Bug scrub follow-up...",
      "proposed_actions": [],
      "applied_actions": []
    }
  ]
}
```

The example abbreviates `rule_evaluations`; the actual result MUST contain all
rule IDs emitted by the skeleton.

### Enumerations

- `mode`: `dry-run`, `apply`
- `readiness`: `READY`, `READY WITH FOLLOW-UP`, `NEEDS INFO`, `BLOCKED`
- `verdict`: `PASS`, `NEEDS INFO`, `ACTION`, `N/A`, `BLOCKED`
- `severity`: `-`, `Blocking`, `Non-blocking`
- proposed action `risk`: `Low`, `Medium`, `High`
- applied action `result`: `APPLIED`, `SKIPPED`, `BLOCKED`, `FAILED`
- applied action `error_category`: `none`, `PERMISSION`, `VALIDATION`,
  `CONFLICT`, `RATE_LIMIT`, `CONNECTIVITY`, `UNKNOWN`

Each proposed action has these fields:

```json
{
  "risk": "Medium",
  "action": "Set Component",
  "old_value": null,
  "new_value": "Example component",
  "evidence": "Ownership mapping returned by Jira metadata",
  "authorization": "Withheld in dry-run"
}
```

Each applied action has these fields:

```json
{
  "action": "Add consolidated follow-up comment",
  "result": "APPLIED",
  "verification": "Comment ID 123456 observed after re-read",
  "error_category": "none"
}
```

## Readiness Derivation

The checker derives readiness from the final rule verdicts:

1. Any `BLOCKED` verdict results in `BLOCKED`.
2. Otherwise, any `Blocking` `NEEDS INFO` or `ACTION` results in `NEEDS INFO`.
3. Otherwise, any `NEEDS INFO` or `ACTION` results in `READY WITH FOLLOW-UP`.
4. Otherwise, the result is `READY`.

In apply mode, re-evaluate rules after verified writes. A successfully corrected
rule should become `PASS`; a failed or withheld action remains `ACTION`.

## Validate the Result

Run:

```bash
python3 scripts/check_scrub_result.py scrub-result.json
```

The run is not complete until the command prints `OK:` and exits with status 0.
The checker enforces:

- exact, ordered rule coverage for every issue;
- valid verdict/severity combinations and evidence;
- readiness consistency;
- no unresolved skeleton placeholders;
- no duplicate issue keys;
- no applied actions or mutation claim in `dry-run`;
- mutation/action consistency in `apply`;
- required fields for proposed and applied actions.

Quote checker counts in the human report rather than recounting manually.