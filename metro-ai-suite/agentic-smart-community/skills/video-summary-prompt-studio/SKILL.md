---
name: video-summary-prompt-studio
description: "Use when: creating or registering a new Smart Building video analytics use case, generating `use-cases/<name>/prompt.md`, generating `use-cases/<name>/evaluate_rules.py` when custom alert logic is needed, adding scenarios such as pet_safety/elder fall/parking safety, refining prompts, or managing multilevel-video-understanding `/v1/tasks`. From a use case name plus natural-language description, infer events/schema, draft the four-section prompt (GLOBAL / MACRO / LOCAL / T_MINUS_1), save prompt.md and any needed evaluate_rules.py, then register through `smartbuilding_use_case_register` when MCP is available; otherwise use `/v1/tasks` curl recipes."
homepage: https://github.com/open-edge-platform/edge-ai-libraries
metadata:
  {
    "openclaw":
      {
        "emoji": "✍️",
        "requires": { "env": ["VIDEO_SUMMARY_BASE_URL"] }
      }
  }
---

# Video Summary Prompt Studio

Manages runtime prompts for the video summary service. A task is a bundle of
four prompts that drive a multi-level hierarchy: **LOCAL** (per micro-chunk)
→ **MACRO** (per macro-chunk) → **GLOBAL** (whole video) + a **T_MINUS_1**
context envelope for continuity.

Pure skill, no plugin. In Smart Building use-case creation, the agent authors
`use-cases/<use_case>/prompt.md` and, when the default severity rule is not
enough, `use-cases/<use_case>/evaluate_rules.py`. It should call the MCP tool
`smartbuilding_use_case_register` with `prompt_text` and `evaluate_rules_path`
when available. For direct video-summary task management without the Smart
Building MCP server, use `bash` + `curl` against `/v1/tasks`.

---

## Hard Invariants (check before every POST/PATCH)

| Rule | Value |
|---|---|
| Anchor names (**CASE-SENSITIVE, literal match**) | `GLOBAL_PROMPT`, `MACRO_CHUNK_PROMPT`, `LOCAL_PROMPT`, `T_MINUS_1_PROMPT` |
| Required placeholders — `LOCAL`, `MACRO` | `{st_tm}`, `{end_tm}` |
| Required placeholders — `T_MINUS_1` | `{dur}`, `{st_tm}`, `{end_tm}`, `{past_summary}` |
| Optional placeholder — `GLOBAL`, `MACRO`, `LOCAL` | `{question}` |
| `task_name` regex | `^[a-z][a-z0-9_]{1,63}$` (lowercase ASCII + underscore) |
| Name suffix convention | `_zh` or `_en` (`pet_guard_zh`, `warehouse_ppe_en`) |
| Smart Building parser output | `LOCAL_PROMPT` must require plain line-oriented text with schema fields as `KEY: value` lines. Never ask for JSON, YAML, Markdown tables, arrays, or code blocks as the VLM output. |
| Schema field keys — **ENGLISH, verbatim** | The structured output lines MUST use the English schema field names as keys (`EVENT:`, `SEVERITY:`, `DESC:`, and any extension like `PET_ZONE:`). **Never translate the key** (no `事件:` / `严重性:`) — the runtime validates by case-insensitive substring, so a Chinese-only prompt with no literal `event` / `desc` substring FAILS `use_case_validate`. Values may be in any language; keys stay English. |
| Banned tokens anywhere in any section | Triple-backtick code fences, and the literal string `<<<` |
| Built-in names (never shadow, never modify, never delete) | `summary`, `engine_valves_sop`, `refrigerator_monitor`, `daily_report`, `daily_report_en`, `refrigerator_monitor_en`, `child_safety_monitor` |
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
video analytics use case from a name plus description, for example
`pet_safety -- 检测宠物逃跑、受困、攻击性行为`.

### Inputs

Minimum input:
- `use_case`: lowercase snake_case identifier, e.g. `pet_safety`
- `description`: natural-language event description in the user's language

Optional input:
- explicit event names and severity mapping
- schema fields such as `pet_zone`, `parking_zone`, or `motion_direction`
- custom alert behavior such as excluded events, zone filters, time windows,
  custom alert messages, or preview-before-register

### Defaults

- `use_case` must match `^[a-z][a-z0-9_]{1,63}$`; ask for a corrected name if
  it does not.
- `video_summary_task` defaults to `<use_case>_monitor`.
- Prompt file path defaults to `use-cases/<use_case>/prompt.md` under the
  Smart Building repo root.
- Default action is generate + register. If the user asks to preview, or if
  event/schema inference is ambiguous, show a concise draft summary before
  registration.
- Default rule behavior for simple alert-style use cases is the built-in
  `defaultRuleEvaluator`: alert when parsed `severity` is `warn` or `critical`.
- If the use case needs event filters, zone filters, custom alert text, or any
  behavior beyond warn/critical severity, generate an `evaluate_rules.py` and
  register it via `evaluate_rules_path`.
- Treat LOCAL_PROMPT's final structured output contract as the source of truth:
  every output field must be declared in `schema_extensions`, and every custom
  `evaluate_rules.py` must read those same parsed fields. Never invent schema
  fields that are not emitted by LOCAL_PROMPT.
- Choose exactly one alert-rule path after the output contract is known:
  - **Default severity rule path**: do not create `evaluate_rules.py`. This path
    requires LOCAL_PROMPT and `schema_extensions` to include `severity`, `event`,
    and `desc`; `defaultRuleEvaluator` alerts on `severity=warn|critical`.
  - **Custom rule path**: create `evaluate_rules.py`. The script must consume the
    schema fields emitted by LOCAL_PROMPT. If LOCAL_PROMPT emits
    `severity/event/desc/pet_zone`, the script must read those fields; if it
    emits boolean fields, the script must read those boolean fields.
- Never create `rules`, `alert_conditions`, `severity_levels`, or
  `cooldown_seconds` fields in `use_case_dict` or MCP register params. There is
  no YAML rule DSL; custom decisions belong in `evaluate_rules.py`.
- Default `summarize` for monitor-alert use cases:
  - `method: "SIMPLE"`
  - `processor_kwargs: { levels: 1, level_sizes: [-1], process_fps: 2 }`
- Default `reports`: `{ data_source: "alerts", default_type: "daily", filter: {} }`

### Infer Events And Fields

Infer event names from the description using lowercase snake_case. Prefer 3-6
events total: the risky events the user named plus safe/no-incident events.

Severity mapping:
- `critical`: immediate injury, trapped/stuck, violent attack, fall, fire,
  drowning, severe intrusion, or a person/animal unable to self-resolve.
- `warn`: escape attempts, abnormal agitation, risk proximity, forbidden-area
  entry, unsafe parking, suspicious behavior, or conditions that may escalate.
- `info`: normal activity, expected activity, no visible actor, no incident.
- `normal`: only use as a severity keyword inside prose when the domain already
  uses it; for structured `SEVERITY` prefer `info` for safe/no-incident rows.

Safe event defaults:
- `<domain>_normal` when the actor is visible and safe.
- `no_incident` when the actor is absent or nothing relevant is happening.

Schema field defaults:
- Derive `schema_extensions` from the exact field names listed in LOCAL_PROMPT's
  output section.
- For severity/event prompts, declare `severity`, `event`, and `desc`; add
  optional context fields such as `pet_zone` only if LOCAL_PROMPT outputs them.
- For boolean-style prompts, declare the boolean-style field names only when
  LOCAL_PROMPT actually outputs them as `field_name: true/false` lines.
- Add at most one optional location/context field when useful for alerts, such
  as `pet_zone`, `parking_zone`, `fall_zone`, or `motion_direction`.
- Schema extension names are lowercase snake_case. Prompt output keys may be
  uppercase (`EVENT:`, `SEVERITY:`, `DESC:`, `PET_ZONE:`) because the runtime
  parser matches schema fields case-insensitively, but include the lowercase
  schema name somewhere in LOCAL guidance so validation can find it.

Example inference for `pet_safety -- 检测宠物逃跑、受困、攻击性行为`:
- If LOCAL_PROMPT outputs `SEVERITY`, `EVENT`, `DESC`, and `PET_ZONE`,
  schema_extensions must be `severity`, `event`, `desc`, and optional
  `pet_zone`.
- If a custom `evaluate_rules.py` is generated for that prompt, it should read
  `event`, `severity`, `desc`, and `pet_zone`, exclude `pet_normal` /
  `no_incident`, alert on warn/critical severity, and append `pet_zone` to the
  message.

### Generate, Save, Register

1. Read the schema before drafting (see `Read The Output Schema`).
2. Draft a complete Markdown `prompt.md` with exactly these top-level section
   headers: `## GLOBAL_PROMPT`, `## MACRO_CHUNK_PROMPT`, `## LOCAL_PROMPT`,
   `## T_MINUS_1_PROMPT`.
3. Run the lint checklist in this skill. Fix all failures before writing or
   registering.
4. Save the prompt to `use-cases/<use_case>/prompt.md` if the user requested a
   Smart Building use case. If the file already exists, do not overwrite unless
   the user explicitly requested replacement.
5. If custom alert behavior is needed, save `use-cases/<use_case>/evaluate_rules.py`.
  It must accept parsed fields on argv[1] and print an AlertOutcome object or
  `null`. The script must be generated from the LOCAL_PROMPT output fields and
  `schema_extensions`. For severity/event prompts with an optional zone field,
  use this pattern:

  ```python
  import json, sys

  SEVERITY_ORDER = {"info": 0, "warn": 1, "critical": 2}

  def main():
      fields = json.loads(sys.argv[1])
      event = fields.get("event", "")
      severity = fields.get("severity", "info").lower()
      desc = fields.get("desc", "")
      zone = fields.get("pet_zone", "unknown")
      excluded = {"no_incident", "pet_normal"}
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

  For boolean-style prompts, use a boolean parser only when LOCAL_PROMPT and
  schema_extensions actually declare those boolean fields:

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

6. Prefer registering through MCP:
   - tool: `smartbuilding_use_case_register`
   - `action: "register"`
   - `use_case: <use_case>`
   - `description: <user description>`
  - `schema_extensions: <LOCAL_PROMPT output fields>` (e.g. `severity`, `event`, `desc`, `pet_zone`)
   - `persist: true`
   - `overwrite: false` unless the user explicitly asks to update

   **You do NOT need to pass `prompt_text` / `evaluate_rules_path` / `summarize` /
   `reports` / `video_summary_task` in the normal flow** — register fills them by
   convention:
   - `prompt_text` is **auto-read from `use-cases/<use_case>/prompt.md`** when omitted.
     So the HARD prerequisite is: **write `use-cases/<use_case>/prompt.md` to disk
     BEFORE calling register** (step 4). If neither `prompt_text` nor that file
     exists, register now **errors out** (no more silent half-registration).
   - `evaluate_rules_path` is auto-picked from `use-cases/<use_case>/evaluate_rules.py`
     when that file exists; otherwise the built-in `defaultRuleEvaluator` is used.
     Therefore, if no `evaluate_rules.py` is generated, `schema_extensions` must
     include `severity`, `event`, and `desc` so the default evaluator can fire.
   - `summarize` / `reports` / `video_summary_task` fall back to the defaults above.
   - Pass any of these explicitly only to override the convention.
7. If MCP is unavailable and the user only asked for a video-summary task, use
   the `/v1/tasks` curl recipes below. Do not claim the Smart Building use case
   is registered unless `smartbuilding_use_case_register` succeeds.

---

## Prerequisites

```bash
: "${VIDEO_SUMMARY_BASE_URL:=http://localhost:8192}"
export VIDEO_SUMMARY_BASE_URL
curl -fsS "$VIDEO_SUMMARY_BASE_URL/v1/health" | jq .
```

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
EVENT: pet_escape
DESC: pet is trying to leave through the balcony door
PET_ZONE: balcony
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
- 最后追加结构化字段，每个字段单独一行，字段名必须和 schema 语义一致:
  SEVERITY: critical/warn/info
  EVENT: <event_1>/<event_2>/<safe_event>/no_incident
  DESC: <一句话描述>
  <OPTIONAL_FIELD>: <只在可见时输出>

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
for example `SEVERITY: warn`, `EVENT: pet_escape`, `DESC: ...`.

After POST/PATCH, optionally run server-side validation via
`smartbuilding_use_case_validate` for a second gate (task registration +
schema consistency).

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
  "task_name": "pet_guard_en",
  "mode": "full",
  "description": "Pet-at-home monitoring; detect abnormal behaviors.",
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
| "创建 use case pet_safety，检测宠物逃跑、受困、攻击性行为" | Infer events/schema → draft `use-cases/pet_safety/prompt.md` with 4 Markdown sections → generate `evaluate_rules.py` only if custom logic is needed → call `smartbuilding_use_case_register` with `persist=true` |
| "先预览 parking_safety 的 prompt，不要注册" | Infer and draft the prompt → show events/schema/path summary → do not call registration until confirmed |
| "覆盖更新 pet_safety prompt 并重新注册" | Read existing prompt if present → rewrite/refine → save with overwrite intent → call `smartbuilding_use_case_register` with `overwrite=true` |
| "Add a pet-at-home monitoring task" / "给视频摘要服务加个宠物看家任务" | If Smart Building MCP is available, use the generate + register workflow; otherwise draft 4 sections in the user's language → POST `/v1/tasks` mode=full |
| "List all video summary tasks" / "列一下任务" | GET `/v1/tasks` |
| "Show me the `child_safety_monitor` prompt" | GET `/v1/tasks/child_safety_monitor` |
| "Make `pet_guard_en`'s local prompt stricter" | GET the task → edit `content` → confirm with user → PATCH mode=full |
| "Delete `pet_guard_en`" | Confirm → DELETE `/v1/tasks/pet_guard_en` |
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
