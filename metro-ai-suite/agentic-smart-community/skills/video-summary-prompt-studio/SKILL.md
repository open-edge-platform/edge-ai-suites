---
name: video-summary-prompt-studio
description: "MANDATORY for creating/registering any new Smart Building video analytics use case. Before calling `smartbuilding_use_case_register` or drafting files, ask Q1 alerting? and Q2 extend schema?, then confirm Final Schema + Rule Path. Generated prompt_text must use four anchors and plain KEY: value output lines; never JSON, code fences, arrays, markdown tables, 0-5 numeric severity, or local files under ~/.openclaw/workspace. Detection goals are EVENT values, not schema fields."
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

Authors and registers Smart Building video-analytics use cases: from a use-case
name + description, draft the four-section prompt (GLOBAL / MACRO / LOCAL /
T_MINUS_1) under `use-cases/<name>/`, optionally an `evaluate_rules.py`, then
register via `smartbuilding_use_case_register`. **Registration is gated — obey the
HARD GATE below before doing anything.** (For direct video-summary task management
without the MCP server, see the `/v1/tasks` curl recipes near the end.)

## REGISTRATION HARD GATE

Non-negotiable preconditions. Every one was violated by a real failed `pet_safety`
run — do not repeat it.

- **P1 — Ask before acting.** Do NOT generate `prompt.md` / `evaluate_rules.py`,
  and do NOT call `smartbuilding_use_case_register`, until Q1 + Q2 are answered
  and the final schema is confirmed. If you genuinely cannot ask the user, fall
  back to the default schema `severity, event, desc` and **invent no extension
  fields** (extend only fields the user's own message explicitly named).
- **P2 — Schema ≠ events.** Final Schema = `severity, event, desc` **+ only the
  extra fields the user explicitly asked to store**. The `schema_extensions` tool
  argument contains only those extra fields; register adds the default alert fields
  internally. Detection targets / behaviors (`escape`, `trapped`,
  `aggressive_behavior`, `*_risk`, `*_detected`, `*_count`, `risk_level`) are
  **`EVENT` values, never columns**.
- **P3 — `KEY: value` only.** LOCAL_PROMPT emits one `KEY: value` line per schema
  field. No JSON, no code fences, no arrays, no tables.
- **P4 — One registration tool; the server writes files.** Everything goes through
  `smartbuilding_use_case_register` in a **two-step** call sequence:
  **step 1 `action=register_task`** (POST the VLM task from `prompt_text` and write
  `use-cases/<uc>/{prompt.md,evaluate_rules.py}`), then **step 2 `action=register`
  (`persist=true`)** (schema + `use_case_dict` + `config.yaml`, reading the prompt
  back from disk). The server writes the artifacts to the **repo root** resolved from
  the server config, not your working directory. **Never** `POST /v1/tasks` yourself,
  **never** write business files into your agent workspace, **never** query the DB
  for use-case config (it lives in `config.yaml.example` → `use_case_dict`).
- **P5 — Bad draft discard rule.** If a draft prompt contains `Return JSON`, a JSON
  object, triple-backtick fences, `## Overview` instead of the four required anchors,
  0-5 numeric severity, or files under `~/.openclaw/workspace/use-cases/`, discard it
  completely and regenerate from this skill's template before registering.

## REQUIRED QUESTION FLOW

Ask **at most these two**; skip one the initial request already answers.

- **Q1 — Alerting?** Does this use case need to raise alerts?
  - **No** → report-only: Final Schema = none, `schema_extensions = []`, no `evaluate_rules.py`, skip Q2.
  - **Yes** → alert via built-in `defaultRuleEvaluator`; base schema is
    `severity, event, desc`.
- **Q2 — Schema extension?** *(only when Q1 = yes)* Beyond `severity/event/desc`,
  does the customer want extra persisted fields (e.g. `zone_id`, `risk_area`,
  `motion_direction`)?
  - **No** → **default rule path**: Final Schema stays `severity, event, desc`;
    pass `schema_extensions: []`; **no** `evaluate_rules.py`.
  - **Yes** → **custom rule path**: final schema = base **+ extensions**
    (`severity, event, desc + <extensions>`); pass only `<extensions>` in
    `schema_extensions`; you **must** write
    `use-cases/<uc>/evaluate_rules.py` that reads that final schema. Never infer
    extensions from event names or behavior descriptions.

## FINAL SCHEMA CONFIRMATION

Before generating any file or calling register, echo the decision and get
confirmation (unless the user already said "proceed"):

    Final Schema: severity, event, desc      (+ <extensions> ONLY if requested in Q2)
    Rule Path:    defaultRuleEvaluator        (or evaluate_rules.py on the custom path)

## CANONICAL EXAMPLE — pet_safety (the default path)

Request: "monitor pet escape / trapped / aggressive behavior, RTSP
`rtsp://.../live/pet`."

- **Q1 alerting?** yes → `defaultRuleEvaluator`.
- **Q2 extend schema?** no — the behaviors are things to detect, not columns to
  store → schema stays `severity, event, desc`.
- **Events**: `pet_escape`, `pet_trapped`, `aggressive_behavior`, `pet_normal`,
  `no_incident` (severity: escape/aggression → `warn`, trapped → `critical`,
  normal/none → `info`).
- **Final Schema**: `severity, event, desc`; **`schema_extensions` argument**: `[]`.
- **`evaluate_rules.py`**: none. **Monitor**: `cam_pet_safety` → the RTSP URL.

The **wrong** version (what the failed run did): putting `escape_risk`, `trapped`,
`aggressive_behavior`, `pet_count`, `risk_level` in `schema_extensions`. Those are
detection targets → `EVENT` values, never columns. See P2.

## Registration Pipeline (the spine of this skill)

Registering a use case runs as **four ordered phases**. Do not skip ahead —
gathering requirements first is what keeps `smartbuilding_use_case_register`
from bouncing on schema↔prompt mismatches.

1. **Phase 1 — Lightweight requirements gathering.** From the use-case name +
   short description, ask **two key questions**: (Q1) does it need alerting?
   and, only if yes, (Q2) does the customer want to extend the schema? Everything
   else (event names, severity mapping, `daily` reports) is defaulted and shown
   in a summary the user can correct. Skip a question whose answer the initial
   request already gave.
2. **Phase 2 — Generate artifacts in memory.** Draft the full `prompt_text` and —
  **only on the extended-schema path** — `evaluate_rules_text` built from the
  final schema. Do **not** create `use-cases/<use_case>/` or write business files
  from the agent workspace. Run the lint checklist on the text before registering.
3. **Phase 3 — Register (two steps).** First call `smartbuilding_use_case_register`
   with **`action=register_task`**, passing `prompt_text` (+ `evaluate_rules_text`
   on the custom path) — it runs the consistency HARD GATE, POSTs the VLM task, and
   on success writes `use-cases/<uc>/prompt.md` (+ `evaluate_rules.py`). Then call it
   again with **`action=register`** (`persist=true`), **omitting `prompt_text`** (it
   is auto-read from the file step 1 wrote) — this applies the schema, injects
   `use_case_dict`, and writes `config.yaml`. **`schema_extensions` is optional in
   both steps**: the server infers the Final Schema from the prompt's `## 输出格式`
   `KEY:` lines (all text columns), so you normally pass nothing — send it only to
   declare a non-text column type (integer/real). Both steps share the same
   consistency gate; fix per its diff and retry until `ok:true`, then register the
   monitor if a stream URL was given. (You may still do it in one `action=register`
   call by passing `prompt_text` inline, but the two-step flow keeps the large prompt
   in a single call and avoids re-sending it on retry.)
4. **Phase 4 — Final configuration report.** Report the new use case's config,
   then append a note listing **all monitors and all registered use cases** in
   the system.

The two decision branches from Phase 1 collapse to one binary that drives the
rest of the pipeline:

- **Default rule path** — default schema `severity, event, desc`, alerting via
  the built-in `defaultRuleEvaluator`; **no `evaluate_rules.py`**.
- **Custom rule path** — the customer extended the schema, so the final schema is
  `severity, event, desc` **+ the extension fields**, and you **must** write a
  `use-cases/<use_case>/evaluate_rules.py` that reads that final schema to decide
  alerts.

---

## Hard Invariants (check before every POST/PATCH)

| Rule | Value |
|---|---|
| **(P1) Ask before acting** | Never write files or call register before asking Q1 (alerting?) + Q2 (extend schema?) and echoing the final confirmed schema. Can't ask → default schema `severity/event/desc`, invent no fields. |
| **(P2) Schema ≠ detection targets** | Final Schema = `severity/event/desc` + user-named extra fields; `schema_extensions` argument = only those extra fields. Behaviors (`escape`/`trapped`/`aggressive_behavior`/`*_risk`/`*_detected`/`*_count`) are `EVENT` values, never columns. |
| **(P4) One registration tool, server writes files** | All registration goes through `smartbuilding_use_case_register`, two-step: `action=register_task` (POST VLM task + write `use-cases/<uc>/{prompt.md,evaluate_rules.py}`) then `action=register` (+`persist=true`) (schema + `use_case_dict` + `config.yaml`, prompt auto-read from disk). Never `POST /v1/tasks` yourself, never write business files to the agent workspace, never query the DB for use-case config. |
| Anchor names (**CASE-SENSITIVE, literal match**) | `GLOBAL_PROMPT`, `MACRO_CHUNK_PROMPT`, `LOCAL_PROMPT`, `T_MINUS_1_PROMPT` |
| Required placeholders — `LOCAL`, `MACRO` | `{st_tm}`, `{end_tm}` |
| Required placeholders — `T_MINUS_1` | `{dur}`, `{st_tm}`, `{end_tm}`, `{past_summary}` |
| Optional placeholder — `GLOBAL`, `MACRO`, `LOCAL` | `{question}` |
| `task_name` regex | `^[a-z][a-z0-9_]{1,63}$` (lowercase ASCII + underscore) |
| Name suffix convention | `_zh` or `_en` (`<task_name>_zh`, `<task_name>_en`) |
| Smart Building parser output | `LOCAL_PROMPT` must require plain line-oriented text with schema fields as `KEY: value` lines. Never ask for JSON, YAML, Markdown tables, arrays, or code blocks as the VLM output. |
| Schema field keys — **ENGLISH, verbatim** | The structured output lines MUST use the English schema field names as keys (`EVENT:`, `SEVERITY:`, `DESC:`, and any extension like `CONTEXT_ZONE:`). **Never translate the key** (no `事件:` / `严重性:`) — the runtime validates by case-insensitive substring, so a Chinese-only prompt with no literal `event` / `desc` substring FAILS `use_case_validate`. Values may be in any language; keys stay English. |
| Banned tokens anywhere in any section | Triple-backtick code fences, and the literal string `<<<` |
| Built-in names (never shadow, never modify, never delete) | Any runtime task reported as built-in by `/v1/tasks`; inspect before overwriting or deleting. |
| Final gate before POST/PATCH | Run the 6-item checklist in `Lint checklist (self-check before POST)` |

**Missing placeholders** get smart-autofilled server-side (safe to skip).
**Missing or misspelled anchors** cause 422 with a `missing` list + a
reference template — fix and retry. The anchor names are case-sensitive:
`global_prompt` or `GlobalPrompt` will **not** match.

---

## Prompt Language (auto-select)

- Detect the language of the user's latest request and author **all four
  sections in that same language**. Do not mix languages inside one prompt.
- If the user explicitly asks for a language (e.g. "write it in English" /
  "请用中文写"), honor that.
- Placeholder names (`{st_tm}`, `{end_tm}`, `{dur}`, `{past_summary}`,
  `{question}`) stay as literal English tokens in both languages.
- Use the `_zh` / `_en` suffix on `task_name` accordingly.

---

## Smart Building Use Case Workflow

Use this workflow when the user asks OpenClaw or another agent to create a
video analytics use case from a name plus natural-language description.

### Inputs

Minimum input:
- `use_case`: lowercase snake_case identifier
- `description`: natural-language event description in the user's language

Optional input:
- explicit event names and severity mapping
- schema fields such as `zone_id`, `risk_area`, or `motion_direction`
- custom alert behavior such as excluded events, zone filters, time windows,
  custom alert messages, or preview-before-register

### Phase 1 — Lightweight Requirements Gathering (two key questions)

Gather requirements **before** drafting. This is a deliberate change from a
"default silently, never ask" flow: a short up-front collection stops the
customer's real intent (alert? extra fields?) from being guessed wrong, which is
the main cause of failed `smartbuilding_use_case_register` retries later.

Keep it **lightweight — ask at most two questions**, and skip any question the
initial request already answers. In OpenClaw / agent contexts, ask them as
structured choices (AskUserQuestion-style single-selects).

**Q1 — Alerting?** Does this use case need to raise alerts?
- **No** → *report-only* use case: no alerting, `schema_extensions=[]`, no
  `evaluate_rules.py`. LOCAL_PROMPT declares/emits no output fields. Skip Q2.
- **Yes** → alerting via the built-in `defaultRuleEvaluator`; the base schema is
  `severity`, `event`, `desc` (alert on `severity=warn|critical`). Go to Q2.

**Q2 — Extend the schema?** (only when Q1 = yes) Beyond `severity/event/desc`,
does the customer want extra persisted fields (e.g. `zone_id`, `risk_area`,
`motion_direction`)?
- **No** → **Default rule path**: final schema stays `severity, event, desc`;
  **do not** generate `evaluate_rules.py` (the default evaluator handles it).
- **Yes** → **Custom rule path**: the final schema is the base **plus** the
  customer's extension fields — `severity, event, desc + <extensions>` (the
  extension is *incremental*, never replaces the base). Because the customer
  extended the schema, you **must** generate `evaluate_rules_text` that reads that
  final schema to decide alerts; the MCP server writes it to the repo during
  registration.

Everything not covered by Q1/Q2 is **defaulted, not asked**, then shown in the
Phase 2 pre-draft summary for the user to correct:
- event names (inferred, lowercase snake_case; see `Infer Events And Fields`),
- severity mapping,
- `reports.default_type = daily`,
- `video_summary_task = <use_case>_monitor`.

Only ask a *third* question if the use-case semantics stay too ambiguous to infer
event names / severity, or if the user asked for non-default report behavior
(weekly/custom) or custom alert behavior beyond warn/critical (event exclusions,
zone filters, time windows, custom alert text) — the latter also selects the
custom rule path. Do not turn defaulted items into extra questions.

### Defaults

- `use_case` must match `^[a-z][a-z0-9_]{1,63}$`; ask for a corrected name if
  it does not.
- `video_summary_task` defaults to `<use_case>_monitor`.
- Prompt file path defaults to `use-cases/<use_case>/prompt.md` under the
  Smart Building repo root.
- Fill defaults for whatever Phase 1 did not ask: `reports.default_type=daily`,
  and — once Q1 = yes — the base Final Schema `{severity,event,desc}`.
  Report-only (Q1 = no) uses Final Schema = none and `schema_extensions=[]`. Show these in the pre-draft
  summary.
- **Schema ownership rule**: Final Schema is NEVER generated from event
  names, detection goals, prompt prose, or LLM-inferred output fields. It is
  exactly the base `{severity,event,desc}` (default path), or the base **plus**
  the extension fields the customer explicitly asked for in Phase 1 Q2 (custom
  path). The `schema_extensions` tool argument contains only those extension
  fields. Detection targets are `EVENT` values, not schema fields.
- **Final schema is incremental**: the customer's extension is *added on top of*
  the base — the final schema is `severity, event, desc + <extensions>`, never a
  replacement of the base.
- Default action is generate + register. If the user asks to preview, or if
  event/schema inference is ambiguous, show a concise draft summary before
  registration.
- Default rule behavior for simple alert-style use cases is the built-in
  `defaultRuleEvaluator`: alert when parsed `severity` is `warn` or `critical`.
- Decide the Final Schema (the Phase 1 outcome) before drafting LOCAL_PROMPT,
  then write LOCAL_PROMPT's final structured output contract to match that schema
  exactly. Every custom `evaluate_rules.py` must read only those same parsed
  fields. Never invent schema fields from the use-case description.
- **The Phase 1 answers pick exactly one alert-rule path:**
  - **Default rule path** (Q2 = no): Final Schema is exactly `severity, event, desc`;
    **do not create `evaluate_rules.py`** — `defaultRuleEvaluator` alerts on
    `severity=warn|critical`. LOCAL_PROMPT must include `severity`, `event`, and
    `desc`; pass `schema_extensions: []` unless the customer requested extra fields.
  - **Custom rule path** (Q2 = yes, i.e. the schema was extended): create
    `use-cases/<use_case>/evaluate_rules.py` and register it via
    `evaluate_rules_path`. The script must read the final schema fields emitted by
    LOCAL_PROMPT (base + extensions, e.g. `severity/event/desc/zone_id`). Pass only
    the extra fields (e.g. `zone_id`) in `schema_extensions`. Boolean
    extension fields are allowed only when the customer explicitly requested them
    in Q2; do not derive them from detection targets.
  - A user request for custom alert behavior beyond warn/critical (event
    exclusions, zone filters, time windows, custom alert text) also selects the
    custom rule path even if no new schema field was added.
- Never create `rules`, `alert_conditions`, `severity_levels`, or
  `cooldown_seconds` fields in `use_case_dict` or MCP register params. There is
  no YAML rule DSL; custom decisions belong in `evaluate_rules.py`.
- Default `summarize` for monitor-alert use cases:
  - `method: "SIMPLE"`
  - `processor_kwargs: { levels: 1, level_sizes: [-1], process_fps: 2 }`
  - **Do NOT pass `summarize` at all in the normal flow** — let register apply the
    default above. If you ever pass it explicitly, `method` MUST be exactly one of
    `SIMPLE` / `USE_VLM_T-1` / `USE_LLM_T-1` / `USE_ALL_T-1`. Never invent values
    like `"default"` — the VLM returns HTTP 400 and every summary silently fails.
    (register also normalizes an illegal method back to `SIMPLE` as a backstop,
    but do not rely on it.)
- Default `reports`: `{ data_source: "alerts", default_type: "daily", filter: {} }`

### Infer Events And Fields

Infer event names from the description using lowercase snake_case. Prefer 3-6
events total: the risky events the user named plus safe/no-incident events.

Severity mapping:
- `critical`: immediate injury, trapped/stuck, violent attack, fall, fire,
  drowning, severe intrusion, or a person/animal unable to self-resolve.
- `warn`: escape attempts, abnormal agitation, risk proximity, forbidden-area
  entry, unsafe conditions, suspicious behavior, or conditions that may escalate.
- `info`: normal activity, expected activity, no visible actor, no incident.
- `normal`: only use as a severity keyword inside prose when the domain already
  uses it; for structured `SEVERITY` prefer `info` for safe/no-incident rows.

Safe event defaults:
- `<domain>_normal` when the actor is visible and safe.
- `no_incident` when the actor is absent or nothing relevant is happening.

Schema field defaults:
- Choose Final Schema before writing LOCAL_PROMPT. If the user did not
  explicitly request extension fields, Final Schema is exactly `severity`, `event`,
  and `desc`, and the `schema_extensions` tool argument is `[]`.
- Detection targets and inferred events become allowed `EVENT` values, not
  schema fields. For example, named risky behaviors belong in LOCAL guidance and
  `EVENT:` values; they must not become boolean fields unless the user explicitly
  requested those fields as schema extensions.
- For severity/event prompts, declare `severity`, `event`, and `desc`; add
  optional context fields such as `zone_id` only if the user explicitly asks for
  that schema extension.
- For boolean-style prompts, declare boolean fields only when the user explicitly
  names those fields as schema extensions. Do not infer boolean schema from a
  checklist of behaviors to detect.
- Add at most one optional location/context field when useful for alerts, such
  as `zone_id`, `risk_area`, or `motion_direction`.
- Schema extension names are lowercase snake_case. Prompt output keys may be
  uppercase (`EVENT:`, `SEVERITY:`, `DESC:`, `ZONE_ID:`) because the runtime
  parser matches schema fields case-insensitively, but include the lowercase
  schema name somewhere in LOCAL guidance so validation can find it.

Inference constraints:
- If the user does not request schema extensions, Final Schema is exactly
  `severity`, `event`, and `desc`, and the `schema_extensions` tool argument is `[]`. Risky behaviors become `EVENT` values; do NOT
  create `*_risk`, `*_status`, boolean, `confidence`, or `recommendation` fields
  unless the user explicitly requested them as schema fields.
- If LOCAL_PROMPT outputs `SEVERITY`, `EVENT`, `DESC`, and one optional context
  field, Final Schema is `severity`, `event`, `desc`, and that exact optional
  field; `schema_extensions` contains only the optional field, and that optional
  field is allowed only when explicitly requested.
- If a custom `evaluate_rules.py` is generated for that prompt, it should read
  only the declared schema fields, exclude safe/no-incident events, and alert on
  the intended warn/critical conditions.

> `pet_safety` is the canonical default-path example — see **CANONICAL EXAMPLE**
> at the top: behaviors (escape/trapped/aggression) are `EVENT` values, schema
> stays `severity, event, desc`, no `evaluate_rules.py`.

### Normalize Failed Register Payloads

When the user pastes a failed `smartbuilding_use_case_register` payload or tool
output, treat that payload as a draft to repair, not as authoritative config.
Apply these corrections before retrying:

- If `prompt_text` asks for JSON, YAML, Markdown tables, code fences, arrays, or
  object literals, rewrite `LOCAL_PROMPT` to plain line-oriented output with
  `KEY: value` lines.
- If `schema_extensions` contains names that match detection goals, event names,
  or boolean checklist items from the description, do NOT preserve those fields.
  Convert them into allowed `EVENT` values and use the default schema
  `severity`, `event`, and `desc` unless the user separately requested true
  persisted schema columns for reporting/querying.
- Words like `escape`, `trapped`, `aggressive`, `fall`, `intrusion`,
  `restricted_entry`, or other behavior/risk labels are event values by default,
  even if the failed payload placed them under `schema_extensions`.
- Boolean schema is allowed only when the user explicitly asks to store boolean
  columns as output data, not when they merely list behaviors to detect or show a
  JSON shape generated by another agent.
- On the default rule path, ensure the repaired `schema_extensions` includes
  exactly `severity`, `event`, and `desc`, and the LOCAL output contract includes
  exactly `SEVERITY:`, `EVENT:`, and `DESC:` lines.
- If a stream URL is present in the request, retry use-case registration first;
  only after it returns `ok:true`, register the monitor source for that URL.

#### Reading the consistency-gate diff (fix the RIGHT thing)

`register` returns a `steps.consistency` diff. Read it to fix the actual cause —
do not blindly make the prompt match a wrong schema.

- **Large `missing_in_prompt` / `default_path_missing_fields` full of
  behavior-like names** (`escape_risk`, `trapped`, `aggressive_behavior`,
  `*_count`, `risk_level`, …) ⇒ **your `schema_extensions` is wrong, not your
  prompt.** Collapse the schema back to `severity, event, desc`, move those names
  into `EVENT` values, and rewrite `## 输出格式` to just `SEVERITY:/EVENT:/DESC:`.
  Do **NOT** expand LOCAL_PROMPT to emit the bogus fields.
- `default_path_missing_fields: [severity, event, desc]` ⇒ you're on the default
  path but dropped a base field; put all three back in schema **and** the prompt.
- `format_violations` (```` ``` ````, `<<<`, JSON literal) ⇒ strip fences /
  rewrite the JSON block as `KEY: value` lines (P3).
- `extra_in_prompt` ⇒ the prompt emits a `KEY:` not in schema; delete that line
  or add the field to schema **only if the user asked to store it**.
- **Do not** escalate to manual `POST /v1/tasks`, DB queries, or web searches when
  the gate fails — the diff already tells you the one file to edit; fix it and call
  `register` again (≤3 attempts).

### Phase 2 & 3 — Generate, Save, Register

Steps 1–6 are **Phase 2 (generate & save)**; steps 7–9 are **Phase 3
(register)**. Phase 1 (the two key questions) is already done — its outcome is
the decided Final Schema, `schema_extensions` argument, and rule path you carry into step 2's summary.
After step 9, go to **Phase 4 — Final Configuration Report** below.

1. Read the schema before drafting (see `Read The Output Schema`).
2. Before drafting, echo back the decided configuration from Phase 1 as a short
   summary. Use this shape (fill from the Q1/Q2 answers):
   - Use Case: `<use_case>`
   - Events: `<risk_event_1>`, `<risk_event_2>`, `<normal_event>`,
     `no_incident`
   - Alerting: `enabled` (or `report-only` when Q1 = no)
   - Reports: daily
   - Schema: `severity`, `event`, `desc`  *(+ `<extensions>` on the custom path)*
   - Rule Path: `defaultRuleEvaluator` *(default path)* **or**
     `evaluate_rules.py` *(custom path — schema was extended)*
   Continue with prompt generation unless the user objects or requests changes.
3. Draft a complete Markdown `prompt.md` with exactly these top-level section
   headers: `## GLOBAL_PROMPT`, `## MACRO_CHUNK_PROMPT`, `## LOCAL_PROMPT`,
   `## T_MINUS_1_PROMPT`. Two LOCAL_PROMPT rules are non-negotiable — the register
   gate enforces both:
   - **`## 输出格式` must list exactly the decided Final Schema fields** — one
     `KEY: <说明>` line per field, UPPER_SNAKE keys (`SEVERITY:` / `EVENT:` /
     `DESC:` / `ZONE_ID:`), the SAME set as the Final Schema (no extra field, none
     missing). A report-only use case declares no fields and emits none.
   - **A `## 禁止事项` block is mandatory** (keep this intent verbatim):
       - 不要输出 JSON 格式
       - 不要加 markdown 符号或方括号
       - 不要写分析过程或逐条排查
       - 只输出 schema 要求的字段行,无其他内容
4. **Prepare the artifacts and let the server write them — do NOT hand-place
   files.** In the MCP / OpenClaw flow, pass the artifacts to **step 1
   (`action=register_task`)** and let the server write them to the correct location:
   - `prompt_text` = the full Markdown prompt — **required in step 1**.
   - `evaluate_rules_text` = the Python source — **only on the custom rule path**
     (Q2 = yes / schema extended), built from the final schema. **Omit it on the
     default path.**

   `register_task` writes these to
   `<repo-root>/use-cases/<use_case>/{prompt.md,evaluate_rules.py}`, where repo
   root = the directory of the server's config (`baseDir = dirname(config…yaml)`),
   **not your agent working directory**. So your CWD, relative paths, and
   `~/.openclaw/workspace` are irrelevant — never create business files there.
   Run the lint checklist below before registering.

   The resulting directory layout is the repo convention: `elder_wakeup/` carries
   `prompt.md` + `evaluate_rules.py` (custom path); `child_safety/` and
   `parking_safety/` carry `prompt.md` only (default path). On the default path do
   **not** pass `evaluate_rules_text`; a leftover `evaluate_rules.py` in your own
   workspace is ignored (the server only reads the repo-root path), so it will not
   pollute the registration.

  Because `register_task` writes `prompt.md` to the repo root, **step 2
  (`action=register`) may then OMIT `prompt_text`** — the server auto-reads it from
  that file. This is the intended two-step flow: send the large `prompt_text` once in
  step 1, keep step 2 small. (Passing `prompt_text` inline to `register` still works
  as a one-shot fallback.)
5. Register in two steps with `smartbuilding_use_case_register`:
  - **Step 1 — `action=register_task`**: pass `prompt_text` (and `evaluate_rules_text`
    on the custom path). This runs the consistency gate, POSTs the VLM task, and writes
    the artifacts. `prompt_text` must not contain Markdown code fences.
  - **Step 2 — `action=register` (`persist=true`)**: pass `description` etc.,
    **omit `prompt_text`** (auto-read from disk). This applies the schema, injects
    `use_case_dict`, and writes `config.yaml`. Retry per the gate diff until `ok:true`.
  - **`schema_extensions` is optional in both steps** — the Final Schema is inferred
    from the prompt's `## 输出格式` `KEY:` lines (the prompt is the source of truth).
    Pass it only to force a non-text column type (integer/real). Authoring the correct
    `KEY:` lines (P2/P3) is what decides the schema, not a separate argument.
6. On the **custom rule path** (schema extended in Q2, or custom alert behavior
  beyond warn/critical), pass the Python source as
  `evaluate_rules_text`; the tool writes it to
  `use-cases/<use_case>/evaluate_rules.py` and registers that path. The script
  must accept parsed fields on argv[1] and print an AlertOutcome object or
  `null`. The script must be generated from the LOCAL_PROMPT output fields and
  the Final Schema (base + extensions). For severity/event prompts
  with an extension zone field, use this pattern:

  ```python
  import json, sys

  SEVERITY_ORDER = {"info": 0, "warn": 1, "critical": 2}

  def main():
      fields = json.loads(sys.argv[1])
      event = fields.get("event", "")
      severity = fields.get("severity", "info").lower()
      desc = fields.get("desc", "")
      zone = fields.get("zone_id", "unknown")
      excluded = {"no_incident", "normal_event"}
      should_alert = event not in excluded and SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER["warn"]
      outcome = {
          "alertType": event or "alert",
          "severity": severity,
          "description": f"{desc} (zone={zone})",
      } if should_alert else None
      print(json.dumps(outcome))

  if __name__ == "__main__":
      main()
  ```

  For boolean-style prompts, use a boolean parser only when the user explicitly
  requested boolean schema extensions and LOCAL_PROMPT / `schema_extensions`
  declare exactly those boolean fields. Never choose this path from behavior
  names alone:

  ```python
  import json, sys

  def truthy(value) -> bool:
      if isinstance(value, bool):
          return value
      return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

  def main():
      fields = json.loads(sys.argv[1])
      should_alert = truthy(fields.get("<risk_field>"))
      outcome = {
          "alertType": "<event_name>",
          "severity": "warn",
          "description": "<human-readable alert>",
      } if should_alert else None
      print(json.dumps(outcome))

  if __name__ == "__main__":
      main()
  ```

7. Prefer registering through MCP (two calls to `smartbuilding_use_case_register` —
   `action: "register_task"` then `action: "register"`). Common arguments:
   - tool: `smartbuilding_use_case_register`
   - `use_case: <use_case>`
   - `description: <one-line ENGLISH summary>` — this is management metadata stored
     in `use_case_dict`; keep it English for consistency with the built-in use cases
     **even when the user's request is in Chinese**. This is separate from the prompt
     body language above: LOCAL/GLOBAL prompt text follows the user's language, but
     the `description` field stays English.
   - `schema_extensions` — **optional; normally omit it.** The Final Schema is inferred
     from the prompt's `## 输出格式` `KEY:` lines, so the correctly-authored prompt already
     decides it. Pass it only to declare a non-text column type (integer/real); when you
     do, list only the extra fields the user explicitly requested (e.g. `zone_id`) — never
     LLM-generated fields derived from event names or detection goals, and register still
     adds `severity/event/desc` internally. If the user pasted a failed payload whose
     `schema_extensions` are behavior names or boolean risk flags, drop them (fix the
     prompt's `KEY:` lines instead) rather than reusing the failed list.
   - `persist: true`
   - `overwrite: false` unless the user explicitly asks to update

   **Pass `prompt_text` to step 1 (`register_task`), not step 2.** `register_task`
   persists that text to `<repo-root>/use-cases/<use_case>/prompt.md`, where
   `<repo-root>` is `dirname(--config)` from the running MCP server; step 2
   (`register`) then auto-reads it. Do not pre-create the file in
   `~/.openclaw/workspace`.
   - `evaluate_rules_text` is passed to `register_task` only on the custom/extended-schema
     path; the server persists it to `<repo-root>/use-cases/<use_case>/evaluate_rules.py`.
   - On the default path, omit `evaluate_rules_text`; the built-in
     `defaultRuleEvaluator` is used.
    Therefore, if no `evaluate_rules.py` is generated, LOCAL_PROMPT must output
    `severity`, `event`, and `desc` so the default evaluator can fire.
   - `summarize` / `reports` / `video_summary_task` fall back to the defaults above.
   - Pass any of these explicitly only to override the convention.

   **register is the consistency HARD GATE — this is the validation loop.** Before any
   side effect (no ALTER, no VLM POST, no config write) it checks: `schema_extensions`
   ↔ LOCAL_PROMPT `## 输出格式` are the exact same set, LOCAL does not request JSON /
   reserved tokens, and the rule path is coherent (default path needs
   `severity`/`event`/`desc` in schema; a custom `evaluate_rules.py` may only read
   declared fields). On a mismatch it returns `ok:false` with a `steps.consistency`
   diff (`missing_in_prompt` / `extra_in_prompt` / `format_violations` /
   `default_path_missing_fields` / `rule_fields_not_in_schema`) and applies **zero**
   changes. When that happens, FIX the offending file (`prompt.md` or
   `evaluate_rules.py`) per the diff and call register again (≤3 attempts). Do NOT
   move on to monitor registration until register returns `ok:true`. (You do not call
   `use_case_validate` first — the pre-registration consistency check lives inside
   register; `use_case_validate` is only a post-registration self-check.)
8. If MCP is unavailable and the user only asked for a video-summary task, use
   the `/v1/tasks` curl recipes below. Do not claim the Smart Building use case
   is registered unless `smartbuilding_use_case_register` succeeds.
9. **Register the monitor (only when the user gave a stream URL).** After the use
   case is registered, bind the camera with `smartbuilding_monitor_ctl
   action=register_source`:
  When `source_url` is provided, monitor registration is part of the default
  workflow; do not stop after registering only the use case.
   - `monitor_id`: **omit it** — register_source defaults it to `cam_<use_case>`.
     Only pass it to add a second camera on the same use case, and it MUST start
     with `cam_`. **NEVER pass the
     `video_summary_task` name (`<use_case>_monitor`) as `monitor_id`** — that
     conflates the monitor id with the VLM task name; register_source now rejects it.
   - `name`: a short **ENGLISH** display name,
     consistent with the built-ins — even when the request is in Chinese.
   - `source_url`: the RTSP/HTTP/... URL the user gave; `use_case`: the key just
     registered.
   - `persist: true` so the monitor is written back to `monitors.yaml` and survives
     an MCP restart (its `pipeline_config` is not stored in the DB).

---

## Phase 4 — Final Configuration Report

After register returns `ok:true` (and the monitor is bound, if a stream URL was
given), you **MUST** emit a final report. It has **two mandatory parts**:
**(A) the new use case**, and **(B) the system inventory**.

**Part A — New use case.** Summarize what was registered:
- Use Case: `<use_case>`  ·  VLM task: `<use_case>_monitor`
- Events: `<...>`  ·  Alerting: `enabled` / `report-only`  ·  Reports: `daily`
- Schema: `severity, event, desc` (+ `<extensions>` on the custom path)
- Rule path: `defaultRuleEvaluator` (no `evaluate_rules.py`) **or**
  `evaluate_rules.py` (custom path)
- Monitor: `cam_<use_case>` → `<source_url>` (omit if no stream URL was given)

**Part B — System inventory (MUST include counts + lists).** Always show the
whole system, not just the new entry:
- **Monitor Count** + the monitor list
- **Use Case Count** + the registered use-case list

There is no single MCP tool that returns both, so gather them from two sources:

- **Monitors** — MCP `smartbuilding_monitor_ctl` `action=list` (or read the
  `smartbuilding://monitors` resource). List each `monitor_id` (and its
  `use_case`).
- **Registered use cases** — read the `use_case_dict` keys from the booted
  config (there is no list-use-case MCP tool):

  ```bash
  if [[ -f config.yaml ]]; then CFG=config.yaml; else CFG=config.yaml.example; fi
  if command -v yq >/dev/null 2>&1; then
    yq '.use_case_dict | keys' "$CFG"
  else
    # yq-free fallback: print the 2-space-indented keys directly under
    # `use_case_dict:` (use case ids), stopping at the next top-level key.
    awk '
      /^use_case_dict:/ { inblk=1; next }
      inblk && /^[^[:space:]#]/ { inblk=0 }
      inblk && /^  [A-Za-z0-9_]+:/ { sub(/:.*/, ""); gsub(/ /, ""); print }
    ' "$CFG"
  fi
  ```

Render it compactly with counts, e.g.:

```text
System Inventory
  Monitor Count:  3
  Monitors:       cam_child_safety, cam_fridge, cam_pet_safety
  Use Case Count: 5
  Use Cases:      child_safety, elder_wakeup, fridge, parking_safety, pet_safety
```

If `smartbuilding_monitor_ctl action=list` is unreachable, still report the use
case count/list from config and say the monitor list could not be fetched — do not
silently drop Part B.

---

## Prerequisites

```bash
: "${VIDEO_SUMMARY_BASE_URL:=http://localhost:8192}"
export VIDEO_SUMMARY_BASE_URL
curl -fsS "$VIDEO_SUMMARY_BASE_URL/v1/health" | jq .
```

### Where things live / known dead-ends (don't hunt or improvise)

A real failed run wasted many steps guessing at plumbing. It works like this:

- **`smartbuilding_use_case_register` does everything**: it applies the schema,
  **auto-registers the VLM task** (`POST /v1/tasks` internally, PATCH on 409),
  injects `use_case_dict`, and (with `persist=true`) writes `config.yaml` +
  `use-cases/<uc>/{prompt.md,evaluate_rules.py}`. You do **not** register the VLM
  task by hand.
- **Use-case config is in `config.yaml.example`** (this environment has no
  `config.yaml`) under `use_case_dict` — **not** in the database. There is **no**
  `config_yaml` or `use_cases` SQL table; `smartbuilding_video_db` is only for
  reading runtime data (alerts, monitors, tasks), not config.
- **Do not** manually `POST /v1/tasks`, write task JSON files, web-search, or read
  other skills to "figure out registration." The path is: draft → register →
  read the gate diff → fix the named file → register again.

---

## Read The Output Schema (before drafting)

Always read schema first, then draft prompts. Field names in
`schema.video_summary_tasks.extensions` are consumed downstream by
`parseSummaryFields`; the model must emit those exact field names as
`field_name: value` lines, or extraction/rules can silently miss.

The Smart Building runtime is **not** a JSON parser for summary output. It scans
plain text for one field per line. For alert use cases, the LOCAL output must end
with structured text lines such as:

```text
SEVERITY: warn
EVENT: restricted_entry
DESC: actor is moving toward a restricted area
ZONE_ID: entrance
```

Do not ask the VLM to output JSON like `{ "severity": "warn", ... }`; those keys
will remain inside `summary_text` and the parser will not populate the `event`,
`severity`, `desc`, or optional extension columns needed by the rule engine.

1. Prefer workspace runtime config: `config.yaml`
2. Fallback: `config.yaml.example`

Suggested extraction flow:

```bash
if [[ -f config.yaml ]]; then
  CFG=config.yaml
else
  CFG=config.yaml.example
fi

yq '.schema.video_summary_tasks.extensions // []' "$CFG"
```

Build a working field list before writing prompt text:
- `required=true` fields: must appear as one line each in output contract.
- `required=false` fields: emit only when detectable in the clip.
- Keep original lowercase field names from schema (no renaming/translation in key).

---

## Writing the 4 Sections — What Each Is For

The four prompts do **different jobs**; scope and detail differ accordingly.

### LOCAL_PROMPT — seconds granularity; the VLM sees raw frames

**This is the only section where perceptual detail enters the system.** If a
hazard is not captured in LOCAL, it will not appear in MACRO or GLOBAL.

Must contain:
- Domain-focus heading
- Time line using `{st_tm}` and `{end_tm}`
- Priority-ordered **focus list** (3–5 items for monitoring use cases):
  1. Actor presence + appearance (clothing / age / location)
  2. Hazardous objects in hand or nearby
  3. Hazardous actions (climbing / falling / ingesting / ...)
  4. Guardian / operator presence & intervention
  5. Safe activity — 1–2 sentences only
- Output rules:
  - 2–5 sentences total
  - **Tag every hazard with a severity keyword: `critical` / `warn` / `info` / `normal`**
  - On-screen text: original + parenthetical translation
  - If no actor visible, describe the scene truthfully; no hallucination
  - No `[` `]` characters; no echo of the time lines
  - **Do not output JSON/YAML/Markdown tables. The final structured part must be plain text lines.**
  - After narrative, append structured lines for schema extraction:
    - One line per required field: `<field_name>: <value>`
    - Optional fields: include only when detected
    - Field names must exactly match schema declarations
  - If hierarchy has levels > 1 and a field is intentionally cross-window,
    place the field line in GLOBAL output contract instead of LOCAL

Spend ~50% of drafting effort here.

### MACRO_CHUNK_PROMPT — minutes granularity; LLM sees micro summaries joined by `>|<`

A **compression pass**. Must contain:
- Merge-goal heading
- Time line with `{st_tm}` / `{end_tm}`
- **Promote critical/warn events to the front, verbatim**
- **Collapse consecutive safe periods into a single sentence**
- Keep actor identity consistent via appearance features
- Do not carry earlier objects/scenes forward unless they still appear
- No `[` `]`, no echo of time lines

### GLOBAL_PROMPT — whole-video summary; the final deliverable

A **narrative pass**, not a ledger. Must contain:
- Product heading ("safety-oriented summary", "daily report", ...)
- **A parseable opening-line convention** — critical triggers a fixed warning
  token so downstream code can detect it:
  - English: start with `ALERT:` when critical, else "Overall safe." /
    "N warn-level events occurred."
  - Chinese: start with `【注意】` when critical, else "整体安全" /
    "出现 N 次 warn 级别事件"
- **No timestamps in the prose**
- Statistics to report (domain-specific): actor count, hazard-type list,
  intervention count, ...
- Do not fabricate beyond macro summaries
- Optional `{question}` — weave in if present

Keep GLOBAL ≤ 5 short paragraphs.

### T_MINUS_1_PROMPT — previous-window context envelope

Small templated section. Must contain:
- Context heading + "this is prior context; do not copy into output"
- Domain-specific continuity note (was the hazard still present? did it
  end?)
- The bracketed envelope:
  ```
  [
  <time line with {st_tm} / {end_tm}>
  {past_summary}
  ]
  ```

---

## Markdown prompt.md Template For Smart Building

When writing `use-cases/<use_case>/prompt.md`, use Markdown sections instead of
Python constants. `smartbuilding_use_case_register` accepts this format through
`prompt_text` and converts it for the video-summary service.

```text
## GLOBAL_PROMPT
## 任务:
生成面向 <domain> 的安全摘要。
- 如果出现 critical 事件，以「【注意】<最严重事件>」开头。
- 如果只有 warn 事件，以「出现 N 次 warn 级别事件」开头。
- 如果没有风险，以「整体安全」开头。
- 按事件类型总结风险、干预和恢复情况，不要编造未出现在 MACRO 摘要中的内容。
- 不要在正文中输出时间戳。
用户问题: {question}

## MACRO_CHUNK_PROMPT
## 任务:
合并本时间窗内的片段摘要，优先保留 critical 和 warn 事件。
Start time: {st_tm}s
End time: {end_tm}s
## 指南:
- 将连续安全或无活动片段压缩成一句话。
- 保持同一对象身份一致，例如根据外观、位置或动作描述区分。
- 不要把已经消失的对象、动作或风险延续到后续描述中。
- 不要使用方括号，不要复述时间行。
用户问题: {question}

## LOCAL_PROMPT
## 任务:
分析这段短视频中与 <domain> 相关的活动，并输出可解析的结构化字段。
Start time: {st_tm}s
End time: {end_tm}s
## 重点关注的内容:
1. <actor> 是否出现、所在位置、外观或状态。
2. 周围是否有危险物、边界、出口、禁区或异常环境。
3. 是否发生 <event_1>、<event_2>、<event_3> 等风险行为。
4. 是否有人干预、风险是否解除。
5. 正常活动或无事件情况只用 1-2 句说明。
## 输出规则:
- 先用 2-5 句自然语言描述观察结果。
- 每个风险都必须带 severity 关键词: critical、warn、info 或 normal。
- 如果没有相关对象出现，如实说明，不要臆测。
- 不要使用方括号，不要复述时间行。
- 不要输出 JSON、YAML、Markdown 表格或代码块；结构化部分必须是纯文本 `字段名: 值` 行。
## 输出格式:
SEVERITY: critical/warn/info
EVENT: <event_1>/<event_2>/<safe_event>/no_incident
DESC: <一句话描述>
<OPTIONAL_FIELD>: <只在用户显式请求该 schema 扩展且画面可见时输出>
## 禁止事项:
- 不要输出 JSON 格式
- 不要加 markdown 符号或方括号
- 不要写分析过程或逐条排查
- 只输出 schema 要求的字段行,无其他内容

## T_MINUS_1_PROMPT
## 上下文:
下面是前 {dur}s 的历史摘要，只能作为连续性参考，不要复制到当前输出。
观察 <domain> 风险是否仍然存在、是否已经解除、对象是否仍在同一区域。
[
Start time: {st_tm}s
End time: {end_tm}s
{past_summary}
]
```

Before saving, replace placeholders such as `<domain>`, `<actor>`, `<event_1>`,
and `<OPTIONAL_FIELD>` with concrete domain terms. Remove optional field lines
when no optional schema field is inferred.

---

## Skeleton (English; translate into the user's language as needed)

Draft each section, concatenate into one `content.text` string, then POST.
Only the placeholder names in braces are literal; everything else is prose.

```text
GLOBAL_PROMPT = '''
## Task:
<product name, e.g. "safety-oriented summary of <domain>">.
- Start with "Overall safe." / "N warn-level events occurred." / "ALERT: <critical hazard>".
- Use "ALERT:" as the fixed opening token whenever any critical event occurs.
- Expand event details grouped by category; NO timestamps in the prose.
- Report statistics: <actor-count, hazard-type list, intervention count, ...>.
- Do not fabricate content not present in the macro summaries.
User question: {question}
'''

MACRO_CHUNK_PROMPT = '''
## Task:
Merge sub-chunks into a concise narrative for this window. Critical / warn events first.
Start time: {st_tm}s
End time: {end_tm}s
## Guidelines:
- Collapse consecutive safe/inactive periods into one sentence.
- Keep actor identity consistent via appearance features (e.g. "the girl in a red dress").
- Do not carry earlier objects/scenes forward unless they still appear.
- No "[" or "]"; no echo of the time lines.
User question: {question}
'''

LOCAL_PROMPT = '''
## Task:
Describe activity in this short clip for <domain>.
Start time: {st_tm}s
End time: {end_tm}s
## Focus (priority order):
1. <actor presence and appearance>
2. <hazardous objects in hand or nearby>
3. <hazardous actions>
4. <guardian / operator presence & intervention>
5. <safe activity — 1–2 sentences only>
## Guidelines:
- 2–5 sentences total.
- Tag every hazard with a severity keyword: critical / warn / info / normal.
- On-screen text: original + parenthetical translation.
- If no actor visible, describe truthfully; no hallucination.
- No "[" or "]"; no echo of the time lines.
'''

T_MINUS_1_PROMPT = '''
## Context:
The previous {dur}s video summary is below in brackets.
**Important** Use it only as context; do not copy into the current output.
Watch for continuity of <actor position / action / contact with hazards>.
If the previous window's state has ended (e.g. the hazard has been resolved), say so explicitly.
[
Start time: {st_tm}s
End time: {end_tm}s
{past_summary}
]
'''
```

When the user writes in Chinese, keep the same structure but write the
prose in Chinese: `##任务:` / `##重点关注的内容:` / `##指南:` / `##上下文:`,
opening-line token `【注意】`, etc. Placeholder names stay in English.

---

## Lint checklist (self-check before POST)

Run this checklist on the final prompt text before POST/PATCH. These checks
mirror the removed MCP prompt-lint behavior and should be enforced inline.

1. `missing_local_prompt`
Symptom: no `## LOCAL_PROMPT` section header.
Fix: add a real `## LOCAL_PROMPT` section; do not hide LOCAL rules elsewhere.

2. `code_fence`
Symptom: contains triple-backtick code fence.
Fix: remove all fences; keep plain text/indented examples only.

3. `missing_event`
Symptom: expected event names do not appear in prompt text.
Fix: add each event name explicitly in LOCAL guidance/examples.

4. `missing_required_schema_field`
Symptom: required schema field name not present in prompt text.
Fix: add the missing field name verbatim (case-insensitive substring check is
the acceptance rule; exact key spelling is still strongly recommended).

5. `pipe_enum`
Symptom: `A | B | C` pipe-style enums appear.
Fix: rewrite as bullet lists or explicit sentence rules; no pipe enums.

6. `think_block`
Symptom: `<think>` markup remains from model output.
Fix: strip all `<think>...</think>` blocks before submission.

7. `json_summary_output`
Symptom: LOCAL_PROMPT asks for JSON/YAML/arrays/tables, or examples show
`{"severity": ...}` instead of line-oriented `SEVERITY: ...` output.
Fix: rewrite the output contract as plain text with one schema field per line,
for example `SEVERITY: warn`, `EVENT: restricted_entry`, `DESC: ...`.

The authoritative schema↔prompt↔rules consistency gate runs **inside
`smartbuilding_use_case_register`** before any side effect (see the register step
above); this lint checklist is the pre-flight so your first register call passes.
After a successful register, `smartbuilding_use_case_validate` is available as a
post-registration self-check (the VLM task exists and its LOCAL_PROMPT covers the
required schema fields) — it is NOT the pre-registration consistency authority.

---

## Curl Recipes

```bash
# List all tasks (built-in + dynamic)
curl -sS "$VIDEO_SUMMARY_BASE_URL/v1/tasks" | jq .

# Inspect one task (built-in or dynamic) — returns `{name, source, description,
# content}` where `content` is a single round-trip-safe string with all four
# anchor sections concatenated. Copy it, edit, and re-submit as `content.text`.
curl -sS "$VIDEO_SUMMARY_BASE_URL/v1/tasks/<name>" | jq .

# Delete a dynamic task (built-ins are 403).
curl -sS -X DELETE "$VIDEO_SUMMARY_BASE_URL/v1/tasks/<name>" -w "%{http_code}\n"
```

### Register full-mode (the primary workflow)

Write the body to a file so shell-quoting doesn't interfere:

```bash
cat > /tmp/body.json <<'JSON'
{
  "task_name": "<task_name>",
  "mode": "full",
  "description": "<natural language use case description>",
  "content": {
    "text": "<<< the 4-anchor content string, with literal \\n between lines >>>"
  }
}
JSON

curl -sS -X POST "$VIDEO_SUMMARY_BASE_URL/v1/tasks" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/body.json | jq .
```

### PATCH variants (rename / replace content / edit description)

```bash
# Rename only
curl -sS -X PATCH "$VIDEO_SUMMARY_BASE_URL/v1/tasks/<name>" \
  -H 'Content-Type: application/json' \
  -d '{"new_task_name": "<new>"}' | jq .

# Replace all four sections (same body shape as register, plus "mode":"full")
curl -sS -X PATCH "$VIDEO_SUMMARY_BASE_URL/v1/tasks/<name>" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/body.json | jq .

# Description only
curl -sS -X PATCH "$VIDEO_SUMMARY_BASE_URL/v1/tasks/<name>" \
  -H 'Content-Type: application/json' \
  -d '{"description": "<new>"}' | jq .
```

### Autogen mode (fallback, lower quality)

Use only if drafting a full prompt is not feasible. Quality depends on the
model the service is configured with via `LLM_MODEL_NAME` / `LLM_BASE_URL`.

```bash
curl -sS -X POST "$VIDEO_SUMMARY_BASE_URL/v1/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"task_name":"<name>","mode":"autogen","description":"<natural language use case>"}' | jq .
```

---

## Error Handling

| Status | Code | Fix |
|---|---|---|
| 201 | (success) | Show the four sections to the user |
| 422 | `missing_anchors` | Read `missing` + `reference_template`; add the anchors, retry |
| 422 | `missing_placeholders` | Section names a required `{foo}`; reply with `section` + `missing` |
| 422 | `autogen_empty_output` | Service LLM returned nothing; retry once, else switch to `mode=full` |
| 400 | `parse_error` | Content malformed (unbalanced `'''`, stray token); compare with `reference_template` |
| 400 | `duplicate_anchor` | Same anchor twice; keep one |
| 400 | `invalid_name` | `task_name` doesn't match `^[a-z][a-z0-9_]{1,63}$` |
| 400 | `banned_token` | Contains triple-backtick fence or `<<<`; remove |
| 400 | `invalid_url` | Non-HTTPS or private-network URL |
| 409 | `builtin_conflict` | Name matches a built-in; pick a different name |
| 409 | `already_registered` | Name used by another dynamic task; pick different or PATCH |
| 403 | `builtin_immutable` | Tried to PATCH / DELETE a built-in; register a new one instead |
| 404 | `not_found` | Typo or never registered; list first |

Retry budget: ≤ 2 attempts on 4xx. On the third failure, surface the server's
`detail` + `reference_template` to the user and ask for guidance.

---

## Intent Mapping

| User utterance (sample) | Action |
|---|---|
| "Create/register a use case named `<use_case>` that detects `<events>`" | Phase 1: ask Q1 (alerting?) then Q2 (extend schema?) → Phase 2: draft `prompt_text` (4 Markdown sections) and `evaluate_rules_text` **only on the custom/extended-schema path**, without writing files locally → Phase 3: `smartbuilding_use_case_register` twice — `action=register_task` (pass `prompt_text` + `evaluate_rules_text` → server POSTs the VLM task and writes repo artifacts), then `action=register` (`persist=true`, omit `prompt_text` → auto-read from disk, schema + `use_case_dict` + config) → Phase 4: final report incl. all monitors & registered use cases |
| "Preview the prompt for `<use_case>`; do not register yet" | Run Phase 1 (Q1/Q2) → draft the prompt → show events/schema/path summary → do not call registration until confirmed |
| "Overwrite and re-register the `<use_case>` prompt" | Read existing prompt if present → rewrite/refine → save with overwrite intent → call `smartbuilding_use_case_register` with `overwrite=true` |
| "Add a video monitoring task for `<description>`" | If Smart Building MCP is available, use the generate + register workflow; otherwise draft 4 sections in the user's language → POST `/v1/tasks` mode=full |
| "List all video summary tasks" / "列一下任务" | GET `/v1/tasks` |
| "Show me the `<task_name>` prompt" | GET `/v1/tasks/<task_name>` |
| "Make `<task_name>`'s local prompt stricter" | GET the task → edit `content` → confirm with user → PATCH mode=full |
| "Delete `<task_name>`" | Confirm → DELETE `/v1/tasks/<task_name>` |
| "Use the LLM to draft a prompt for me" | Prefer `mode=full` (draft via this SKILL); use `mode=autogen` only for a throwaway first cut |

---

## Notes

- **Persistence**: dynamic tasks live under the service's
  `VIDEO_SUMMARY_CACHE` dir (default `~/.cache/.multilevel-video-understanding`
  on the host). They survive container restarts.
- **Round-trip editing**: the `content` field returned by GET is ready to
  POST/PATCH back — no reformatting needed.
- **URL content**: `content.url` (HTTPS only, ≤ 256 KB, public hosts) is an
  alternative to `content.text` for loading the four-section string from a
  remote file.
