---
name: video-summary-prompt-studio
description: "MANDATORY for creating, previewing, refining, or registering any Smart Building video analytics use case. Enforces primary-event capability checks, Q1 alerting, Q2 schema extension, Final Schema + Rule Path selection, prompt authoring, two-step registration, and monitor binding."
homepage: https://github.com/open-edge-platform/edge-ai-libraries
metadata:
  {
    "openclaw":
      {
        "emoji": "✍️"
      }
  }
---

# Video Summary Prompt Studio

Creates and registers Smart Building video-analysis use cases. This Skill owns
capability negotiation, output mode, Final Schema, rule path, registration, and
monitor binding. It does not contain domain definitions; those are compiled
into each use-case prompt from the user's business requirements.

## References

Read references only at their stated trigger:

- **Always before drafting/refining a prompt:**
  `references/prompt-authoring.md` — Detection Contract, runtime execution
  matrix, four-section template, semantic lint, and behavior validation.
- **Extended schema or custom alert behavior:**
  `references/evaluate-rules.md` — `evaluate_rules.py` contract and templates.
- **Overwrite/refine an existing use case:**
  `references/inspect-existing.md` — read its active schema and artifacts.
- **MCP server unavailable:**
  `references/curl-fallback.md` — direct `/v1/tasks` task management only.
- **Final inventory:**
  `scripts/list_use_cases.sh` — list use cases from the server's booted config.

## Data-model boundary

Before Q1/Q2, determine whether the user needs:

- **Primary-event mode:** persist one primary event per clip; secondary visible
  observations may appear in `DESC`.
- **Multi-occurrence mode:** persist every simultaneous event/person occurrence
  independently.

Structured runtime currently supports primary-event mode only. If the user
needs multi-occurrence mode, stop before drafting/registration and explain that
it requires a different ingestion/data model. Never encode it as arrays,
slash-separated values, repeated `EVENT:` lines, or unqueryable prose.

Also stop when the request requires per-person records, bounding boxes,
coordinates, exact counts, persistent trajectories, multilabel output,
calibrated confidence, structured time intervals, event graphs, or cross-camera
identity. Prompt wording cannot add these runtime capabilities.

Do not ask this as a Q0. Use primary-event mode unless the request explicitly
requires an unsupported capability above. For an explicit unsupported
requirement, stop and explain the limitation without adding a boundary question.

## Mode matrix

This table is authoritative. Later steps must not mix invariants across rows.

| Mode | Final Schema | LOCAL output | Rule path | Report source |
|---|---|---|---|---|
| Report-only | none | factual narrative; multiple findings allowed | none | completed `video_summary_tasks` |
| Base alerting | `severity, event, desc` | one primary EVENT | `defaultRuleEvaluator` | `alerts` |
| Extended alerting | base + Q2-requested extensions | one primary EVENT + extension fields | `evaluate_rules.py` | `alerts` |

Product invariants:

- Detection targets are `EVENT` values, never schema columns.
- Extensions are incremental; they never replace `severity, event, desc`.
- Base alerting has no `evaluate_rules.py` and alerts on parsed
  `severity=warn|critical`.
- Any extended schema **must** have `evaluate_rules.py` generated from the
  complete Final Schema. Falling back to `defaultRuleEvaluator` is forbidden.
- Custom alert behavior also selects `evaluate_rules.py`, even with base schema.
- Report-only has neither structured fields nor an evaluator.

## Question flow

Skip questions already answered by the initial request.

Q1 and Q2 are the only user-facing confirmation questions in this workflow.
After they are answered, do not ask for separate confirmation of event names,
evidence, severity, priority, uncertainty, report behavior, the Detection
Contract, or generated artifacts. State any inferred defaults briefly and
continue directly to authoring and registration.

### Q1 — Alerting?

Does this use case need to raise alerts?

- **No:** report-only; Final Schema = none; Rule Path = none; skip Q2.
- **Yes:** structured alerting; base schema = `severity, event, desc`; ask Q2.

### Q2 — Schema extension? (Q1 = yes only)

Persist fields beyond `severity/event/desc`?

- **No:** Base alerting; no `evaluate_rules.py`.
- **Yes:** Extended alerting; Final Schema = base + only explicitly requested
  fields; generate `evaluate_rules.py` from that complete schema.

Outside Q1/Q2, resolve ordinary business ambiguity with conservative defaults:

- Use the behavior named by the user as the single primary detection event.
- Use `warn` for a detected policy/safety violation unless the user explicitly
  requested another severity or described visible immediate severe harm.
- Use `info` for non-alerting baseline, absence, and uncertainty events.
- Use severity-first primary-event priority: `critical > warn > info`.
- Derive minimum visible evidence and common look-alike exclusions narrowly
  from the named behavior.
- Do not invent critical escalation scenarios, special policies for adjacent
  behaviors such as vaping, extra business events, custom alert behavior, or
  persisted fields.

The capability stops in **Data-model boundary** still apply. Stop and explain
an unsupported requirement rather than turning it into a third question.
Never ask the user to write the prompt.

If the agent cannot ask:

- When the user explicitly requested alerts, use base alerting and invent no
  extensions unless the request explicitly named persisted fields.
- When alerting intent is not explicit, generate a preview only. Do not
  register an alerting use case by assumption.

## Q1/Q2 decision block

After Q1/Q2, show the applicable block and a compact Detection Contract from
`prompt-authoring.md` for transparency, then continue in the same turn. This is
not another confirmation gate: do not ask the user to approve the block or wait
for a reply.

```text
Report-only
  Final Schema: none
  Rule Path: none
  Report Source: completed video_summary_tasks

Base alerting
  Final Schema: severity, event, desc
  Rule Path: defaultRuleEvaluator
  Report Source: alerts

Extended alerting
  Final Schema: severity, event, desc, <extensions>
  Rule Path: evaluate_rules.py
  Report Source: alerts
```

## Defaults

- `video_summary_task = <use_case>_monitor`; omit the argument to use it.
- `use_case` must match `^[a-z][a-z0-9_]{1,63}$`.
- Alerting reports:
  `{ data_source: "alerts", default_type: "daily", filter: {} }`.
- Report-only reports (pass explicitly):
  `{ data_source: "video_summary_tasks", default_type: "daily", filter: { status: "completed" } }`.
- Omit `summarize`; register supplies
  `{ method: "SIMPLE", processor_kwargs: { levels: 1, level_sizes: [-1], process_fps: 2 } }`.
- `persist: true`; `overwrite: false` unless the user explicitly updates an
  existing use case.
- Never invent YAML fields such as `rules`, `alert_conditions`,
  `severity_levels`, or `cooldown_seconds`.

Default realtime execution is `SIMPLE`, `levels=1`: LOCAL determines persisted
fields and immediate alerts. MACRO/GLOBAL are used for aggregate reports;
T_MINUS affects only explicitly configured history modes. See
`references/prompt-authoring.md` for the full execution matrix.

## Draft and lint

1. Read `references/prompt-authoring.md`.
2. Build the resolved Detection Contract from the request, Q1/Q2, and defaults.
3. Draft all four Skill-required sections:
   `GLOBAL_PROMPT`, `MACRO_CHUNK_PROMPT`, `LOCAL_PROMPT`, `T_MINUS_1_PROMPT`.
4. Run the reference's semantic lint and contract round-trip.
5. On Extended alerting/custom behavior, read `references/evaluate-rules.md`
   and create `evaluate_rules.py` from the complete Final Schema.

The Skill requires all four authored sections for predictable realtime/report
behavior. The VLM service itself requires GLOBAL + LOCAL and can auto-fill
MACRO/T_MINUS; do not rely on those generic defaults for registered use cases.

## Register (two steps)

Use only `smartbuilding_use_case_register`. Never manually POST `/v1/tasks`
while MCP is available.

Common arguments: `use_case`, one-line English `description`, `persist: true`,
and `overwrite: false` unless updating.

### Step 1 — generate task and stage artifacts

Call `action=generate_task` with the complete `prompt_text`.

- Base alerting/report-only: omit `evaluate_rules_path`.
- Extended alerting/custom behavior: pass `evaluate_rules_path`.
- The server checks consistency, registers/updates the VLM task, and on success
  writes `use-cases/<use_case>/prompt.md`; a rule file is staged beside it.
- It does not ALTER schema or update `use_case_dict`/config.

### Step 2 — register the use case

Call `action=register`, `persist=true`, and omit `prompt_text` and
`evaluate_rules_path`; the server auto-reads/auto-discovers staged artifacts.

- Applies the Final Schema idempotently.
- Injects the in-memory `use_case_dict` entry.
- Writes the booted config when persistence succeeds.
- Runs post-registration structural validation.

### `schema_extensions`

Normally omit it: Final Schema is inferred from LOCAL's UPPER_SNAKE output
lines. Pass it only to declare a non-text type or override a required flag, and
then list only extension fields explicitly requested through Q2. Detection events, risk labels,
derived counts, and booleans not explicitly requested for persistence do not
belong here.

The consistency gate runs before side effects. In particular:

- Report-only must have no output KEY lines.
- Base alerting must match exactly `severity,event,desc`.
- Extended fields without `evaluate_rules.py` are rejected.
- Prompt fields and Final Schema must match exactly.
- Rules may read only Final Schema fields.

Do not continue to monitor binding until registration returns `ok:true`.

## Register the monitor

When the request includes a stream URL, bind it after successful use-case
registration with `smartbuilding_monitor_ctl action=register_source`:

- omit `monitor_id` for the default `cam_<use_case>`;
- pass a short English `name`;
- pass `source_url`, `use_case`, and `persist:true`.

Pass a custom `monitor_id` only for additional cameras; it must start with
`cam_`. Never use `<use_case>_monitor` as the monitor ID.

## Validation and final report

Registration success proves structural validity, not detection quality. Apply
the minimum behavior-validation set in `references/prompt-authoring.md` when
representative media exists. Otherwise report **registered but behaviorally
unvalidated**.

Final response contains:

```text
New Use Case
  Use Case: <use_case>
  VLM Task: <use_case>_monitor
  Mode: report-only | base alerting | extended alerting
  Events/Findings: <...>
  Final Schema: none | severity,event,desc[,extensions]
  Rule Path: none | defaultRuleEvaluator | evaluate_rules.py
  Report Source: completed video_summary_tasks | alerts
  Monitor: cam_<use_case> -> <source_url>   # omit when no stream was supplied
  Validation: behaviorally validated | registered but behaviorally unvalidated
```

Then report system inventory:

- Monitors: use `smartbuilding_monitor_ctl action=list`; list ID + use case.
- Use cases: run `scripts/list_use_cases.sh <server-config-path>` against the
  config the MCP server actually booted with.
- If one inventory source is unavailable, report the other and state the gap.

## Failure handling

- A failed consistency report is authoritative; fix the named prompt/schema/rule
  mismatch and retry at most three times.
- Extended schema missing rules: create `evaluate_rules.py`; never drop fields
  or fall back to default merely to pass.
- Behavior names mistakenly supplied as extensions: move them to EVENT values.
- Format violations: remove generated fences, JSON/YAML/arrays/tables, `<<<`,
  repeated EVENT lines, and slash-separated values.
- Existing artifact conflict: read `references/inspect-existing.md`; use
  `overwrite=true` only for an intentional update.
- Do not bypass validation with direct DB edits or manual task POSTs.

## Intent mapping

| User request | Action |
|---|---|
| Create/register use case | Capability check → Q1/Q2 → resolve defaults → author → register → monitor → report |
| Preview only | Capability check → Q1/Q2 → author/lint → show preview; no registration |
| Refine/overwrite existing | Read `inspect-existing.md` → confirm changes → register with overwrite |
| Delete use case | Confirm destructive action → `action=unregister`, `persist=true` → verify `cascaded_monitors`: `db_row="deleted"` means the monitor was fully unregistered; `db_row="kept_offline"` means the row delete failed (e.g. existing alerts history) and it fell back to stop — tell the user the monitor row remains |
| MCP unavailable task CRUD | Read `curl-fallback.md` |
