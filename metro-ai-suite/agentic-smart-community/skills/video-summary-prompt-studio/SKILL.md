---
name: video-summary-prompt-studio
description: "MANDATORY for creating, previewing, refining, registering, or deleting any Smart Building video analytics use case. Requires two cross-turn gates before drafting or registration: explicit Q1/Q2 answers, then explicit approval of the proposed Final Schema, Rule Path, and Detection Contract. Requires an explicit cross-turn confirmation before any use-case deletion."
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

- **After final approval, immediately before drafting/refining a prompt:**
  `references/prompt-authoring.md` — Detection Contract, runtime execution
  matrix, four-section template, semantic lint, and behavior validation.
- **Extended schema or custom alert behavior:**
  `references/evaluate-rules.md` — `evaluate_rules.py` contract and templates.
- **Overwrite/refine an existing use case:**
  `references/inspect-existing.md` — read its active schema and artifacts.
- **Delete a use case:** `references/delete-use-case.md` — impact, confirmation, cascade verification.
- **Final report:** `references/final-report.md` — report blocks, inventory rendering, fallbacks.
- **MCP server unavailable:**
  `references/curl-fallback.md` — direct `/v1/tasks` task management only.

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
| Extended alerting | base + user-confirmed extensions | one primary EVENT + extension fields | `evaluate_rules.py` | `alerts` |

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

Q1/Q2 are a mandatory cross-turn gate for every new use case, including preview
requests. First collect only the use-case name and a simple business
description. A stream URL may be recorded at intake, but it does not change the
gate.

The initial request never answers Q1 or Q2, even when words such as "alert",
"warning", "notify", "persist", "field", or an apparent schema occur in the
business description. Never infer either answer from the use-case name,
detection targets, safety implications, recommended defaults, prior use cases,
or canonical examples.

After the name and description are available:

1. Before the explicit Q1/Q2 reply, the only permitted tool call is reading this
  main `SKILL.md` file itself when it has not already been loaded. Do not read
  any reference, other skill, config, existing artifact, workspace file, or
  memory. Do not call memory, search, shell, MCP, `smartbuilding_*`, or any
  other tool. Once this main file is loaded and the name and description are
  available, ask the questions without another tool call.
2. Ask Q1 and Q2 together using the wording below. Explain that Q2 applies only
  when Q1 is Yes.
3. End the assistant turn immediately after the questions. Do not draft a
  prompt, create or modify files, call any tool, write memory, or claim the
  answers are confirmed in that turn.
4. Unlock the remaining workflow only from a later user message that explicitly
  answers Q1 and, when Q1 is Yes, Q2. Examples of valid replies are
  `Q1=yes, Q2=no` and `Q1=yes, Q2=yes: zone_id (text)`. For Q1=No, record Q2 as
  not applicable.
5. If an answer is missing or ambiguous, ask only for the missing answer and end
  the turn again. Silence, a recommendation, or the agent's own proposed answer
  is never confirmation.

Q1 and Q2 are the only user-facing design questions in this workflow. After the
explicit reply is received, resolve event names, evidence, severity, priority,
uncertainty, and report behavior with the conservative defaults below. Do not
ask separate design questions for those details. Present the resolved design at
the mandatory final approval gate below before authoring or registration.

### Q1 — Alerting?

Does this use case need to raise alerts?

- **No:** report-only; Final Schema = none; Rule Path = none; skip Q2.
- **Yes:** structured alerting; base schema = `severity, event, desc`; ask Q2.

### Q2 — Schema extension? (Q1 = yes only)

Persist fields beyond `severity/event/desc`?

- **No:** Base alerting; no `evaluate_rules.py`.
- **Yes:** Extended alerting; Q2 confirms the extension schema with the user.
  Final Schema = base + only user-confirmed fields; generate `evaluate_rules.py`
  from that complete schema.

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

- Stop after intake and state that explicit Q1/Q2 confirmation is required.
- Do not infer answers, generate a preview, draft artifacts, or register a use
  case. There is no fallback that bypasses this gate.

## Q1/Q2 decision block

In the assistant turn after the user's explicit Q1/Q2 reply:

1. Show the applicable block and a compact resolved Detection Contract.
2. Ask the user to confirm this proposed design and continue.
3. End the assistant turn immediately. Do not read authoring references, draft
  prompts, create or modify files, or call any `smartbuilding_*` tool.

This is a mandatory second cross-turn gate. Continue only after a later user
message explicitly approves the displayed Final Schema, Rule Path, and Detection
Contract, for example `confirm`, `approved`, or `确认，继续`. The Q1/Q2 reply
itself cannot approve a design that had not yet been displayed. Silence or the
agent's own statement that the design is resolved is never approval.

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
- `persist: true` (tool default; mirrors into the booted `<data_dir>/config.yaml`
  — `<data_dir>` = `$SMARTBUILDING_DATA_DIR` or `~/.mcp-smartbuilding`);
  `overwrite: false` unless the user explicitly updates an existing use case.
- Never invent YAML fields such as `rules`, `alert_conditions`,
  `severity_levels`, or `cooldown_seconds`.

Default realtime execution is `SIMPLE`, `levels=1`: LOCAL determines persisted
fields and immediate alerts. MACRO/GLOBAL are used for aggregate reports;
T_MINUS affects only explicitly configured history modes. See
`references/prompt-authoring.md` for the full execution matrix.

## Draft and lint

1. Verify that a later user message explicitly answered Q1 and, if applicable,
  Q2. If not, return to **Question flow** without drafting or calling tools.
2. Verify that the proposed decision block and Detection Contract were then
  displayed and explicitly approved in another later user message. If not,
  return to **Q1/Q2 decision block** and end the turn.
3. Read `references/prompt-authoring.md`.
4. Build the approved Detection Contract from the request, Q1/Q2, and defaults.
5. Draft all four Skill-required sections:
   `GLOBAL_PROMPT`, `MACRO_CHUNK_PROMPT`, `LOCAL_PROMPT`, `T_MINUS_1_PROMPT`.
6. Run the reference's semantic lint and contract round-trip.
7. On Extended alerting/custom behavior, read `references/evaluate-rules.md`
   and create `evaluate_rules.py` from the complete Final Schema.

The Skill requires all four authored sections for predictable realtime/report
behavior. The VLM service itself requires GLOBAL + LOCAL and can auto-fill
MACRO/T_MINUS; do not rely on those generic defaults for registered use cases.

## Register (two steps)

Use only `smartbuilding_use_case_register`. Never manually POST `/v1/tasks`
while MCP is available.

Before either registration step, verify both user messages are present in order:
the explicit Q1/Q2 reply after the question turn, and the explicit final approval
after the proposed design was displayed. Initial-request wording, agent
inference, defaults, or a plan item marked complete do not satisfy either
precondition. If either message is absent, do not call the tool.

Common arguments: `use_case`, one-line English `description`, `persist: true`,
and `overwrite: false` unless updating.

### Step 1 — generate task and stage artifacts

Call `action=generate_task` with the complete `prompt_text`.

- Base alerting/report-only: omit `evaluate_rules_path`.
- Extended alerting/custom behavior: pass `evaluate_rules_path`.
- The server checks consistency, registers/updates the VLM task, and on success
  writes `<data_dir>/use-cases/<use_case>/prompt.md`; a rule file is staged beside it.
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

## Delete a use case (confirmation gate)

Deletion is destructive (entry removed, bound monitors unregistered, artifacts
archived) and requires a mandatory cross-turn confirmation gate.

1. On a delete request, read `references/delete-use-case.md`, fetch the real
   impact (`action=list` on both register and monitor tools), display it, and
   ask for explicit confirmation (e.g. `confirm delete <use_case>`). End the
   turn — the initial request is never confirmation, even when it says
   "delete", because the user has not yet seen the cascade impact.
2. Only after a later message explicitly confirms: `action=unregister` with
   `persist: true`, then verify `cascaded_monitors` per the reference.

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

Then report system inventory as ONE grouped view — use cases as headers,
bound monitors nested underneath — fetched from `action=list` on both tools;
format, example, and fallbacks per `references/final-report.md`.

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
| Create/register use case | Collect name + description → capability check → ask Q1/Q2 and end turn → receive answers → show resolved design, ask final approval, and end turn → receive explicit approval → author → register → monitor → report |
| Preview only | Collect name + description → capability check → ask Q1/Q2 and end turn → receive answers → show resolved design, ask final approval, and end turn → receive explicit approval → author/lint → show preview; no registration |
| Refine/overwrite existing | Read `inspect-existing.md` → confirm changes → register with overwrite |
| Delete use case | Fetch inventory → display cascade impact, ask confirmation, and end turn → receive explicit confirmation in a later message → `action=unregister`, `persist=true` → verify `cascaded_monitors` (see **Delete a use case (confirmation gate)**) |
| MCP unavailable task CRUD | Read `curl-fallback.md` |
