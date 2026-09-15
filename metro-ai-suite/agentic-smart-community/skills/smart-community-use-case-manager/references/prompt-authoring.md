# Prompt Authoring Contract

Read this reference before drafting or revising any use-case prompt. It is the
single authority for Detection Contract design, runtime prompt usage, the
four-section authoring template, semantic lint, and behavior validation.

## Runtime execution matrix

The Skill authors all four sections so the same task works for realtime clips
and reports. The VLM service requires `GLOBAL_PROMPT` and `LOCAL_PROMPT`; it can
auto-fill omitted `MACRO_CHUNK_PROMPT` and `T_MINUS_1_PROMPT`, but Skill-authored
use cases provide all four to avoid generic defaults.

| Runtime path | Sections that affect the result |
|---|---|
| Realtime clip, default `SIMPLE`, `levels=1` | `LOCAL_PROMPT` only |
| Daily/weekly subtitle aggregation | `MACRO_CHUNK_PROMPT`, then `GLOBAL_PROMPT` |
| Explicit non-`SIMPLE` history mode | `T_MINUS_1_PROMPT` may provide prior-window context |
| Default rule evaluator | Parsed `LOCAL_PROMPT` fields |
| Custom rule evaluator | Parsed `LOCAL_PROMPT` Final Schema fields |

Realtime classification defects must be fixed in LOCAL. MACRO/GLOBAL wording
cannot repair a wrong realtime `EVENT`, and T_MINUS rules do not affect the
default `SIMPLE`, `levels=1` path.

## Output modes

### Structured alerting

- Final Schema is `severity, event, desc` plus only extensions requested through
  Q2.
- LOCAL emits exactly one `KEY: value` line per Final Schema field.
- Every clip emits exactly one primary `EVENT`; secondary observations may be
  included in `DESC` but are not independently queryable or alertable.
- Base schema uses `defaultRuleEvaluator`.
- Any extended schema requires `evaluate_rules.py` generated from the complete
  Final Schema. It must not fall back to the default evaluator.

### Report-only narrative

- Final Schema and evaluator are both absent.
- LOCAL emits concise factual prose and no UPPER_SNAKE `KEY:` output lines.
- LOCAL may mention multiple simultaneous findings because it does not persist
  a scalar `EVENT`.
- Detection evidence, exclusions, uncertainty, identity, and temporal rules
  still apply.
- Reports aggregate completed `video_summary_tasks`, not alerts.

## Detection Contract

After the explicit Q1/Q2 reply, resolve the proposed contract from the initial
request, those answers, and the conservative defaults in `SKILL.md`. Display the
proposed Final Schema, Rule Path, and compact Detection Contract, then stop and
wait for the mandatory final approval described in `SKILL.md`. Do not write
prompt prose until a later user message explicitly approves that displayed
design.

In this reference, `resolved` means derived for the proposal; `approved` means
the user explicitly accepted the displayed proposal in a later turn. Defaults
may resolve a detail, but neither defaults nor the Q1/Q2 reply can approve a
design that had not yet been displayed. All authoring rules below operate on the
approved contract. A contract contains:

1. A closed vocabulary of alerting, non-alerting baseline, absence, and—when
   operationally useful—uncertainty events.
2. For every event, minimum sufficient visible evidence, common look-alikes or
   exclusions, and one fixed severity from `critical`, `warn`, or `info`.
3. One uncertainty policy for the complete contract.
4. One deterministic primary-event business priority for structured alerting.

Event definitions should be mutually exclusive where practical, but multiple
conditions may be visually true. The priority determines which one is persisted.
A prompt that merely asks whether an object/event/violation exists is invalid.

### Observe before classifying

For each relevant actor or object, establish in order:

1. visible presence and appearance;
2. position or region;
3. motion or state transition;
4. interaction with other actors/objects;
5. positive evidence for the selected event.

`DESC` must cite visible evidence instead of only repeating the event label.
Never infer identity, intent, authorization, medical state, or compliance that
cannot be grounded in visible proxies.

### Visual decision boundaries

- Object/apparel/PPE/tool/vehicle tasks: define observable target
  characteristics and common visually similar non-targets.
- Action/state-transition tasks: define the visible temporal change and similar
  benign actions that must not trigger.
- Environmental phenomena: define appearance, motion/persistence, and similar
  non-targets.
- Non-alerting baseline states require positive evidence. Failure to recognize
  an alert is not proof of a baseline state.
- An absence event requires confirmed absence of the relevant actor/object or
  activity. Poor visibility is not absence.

### Severity and priority

Use only `critical`, `warn`, and `info`.

- `critical`: visible immediate/severe harm, inability to self-resolve, or a
  business-defined highest-priority violation.
- `warn`: visible unsafe/abnormal condition that may escalate without currently
  showing immediate severe harm.
- `info`: non-alerting baseline, absence, or non-alerting uncertainty.

Do not assign severity from an event name alone. For structured safety use
cases, default to severity-first priority (`critical > warn > info`) and then
the resolved tie-break order. For occupancy, workflow, asset state, or other
objectives, use the resolved business priority.

### Baseline, absence, and uncertainty

Choose event names that match the business semantics:

- Safety may use `<domain>_normal` and `no_incident`.
- Occupancy/activity may use `no_relevant_activity`.
- Object-state classification may use user-named baseline states and
  `target_absent` when absence is meaningful and visible.

If a relevant actor/object is present but the decisive attribute is not visible
because of occlusion, distance, scale, angle, sampling, or image quality, never
select a positive baseline or absence event.

Add `<domain>_uncertain` with `severity=info` when uncertainty is frequent,
material to alert/audit interpretation, or must be queryable. For incidental
uncertainty, omit a dedicated event only when the confirmed vocabulary already
has a non-alerting indeterminate event; describe the visibility limitation in
`DESC`. Report-only LOCAL may describe uncertainty directly in prose.

## Section-writing rules

### LOCAL_PROMPT

LOCAL is the realtime decision surface. Include:

- actor/object observation checklist;
- explicit event decision rules;
- uncertainty policy;
- deterministic priority (structured mode);
- output contract.

For structured alerting, output only Final Schema lines. Put all narrative in
`DESC`; do not add prose before or after the lines. Optional extension fields
may be omitted only when their output-contract line says `optional` / `可选`.

### MACRO_CHUNK_PROMPT

Merge repeated LOCAL findings into event episodes:

- same actor + same unresolved/unchanged event across consecutive clips = one
  episode;
- start a new episode after visible resolution/change, actor change, or a
  distinct recurrence;
- an uncertain clip proves neither continuation nor resolution;
- same event before/after an uncertain gap is one episode only when identity
  continuity is strong and no resolution evidence appears;
- otherwise keep separate episodes and state that continuity is uncertain.

Episode counts are semantic estimates based on visible identity and summaries,
not deterministic tracking metrics. Exact counts require identity/episode data.

### GLOBAL_PROMPT

Use the resolved opening convention and summarize only MACRO evidence. Any
count `N` means deduplicated semantic event episodes, not LOCAL clip count or
repeated mentions. Safety use cases may use critical/warn/overall-safe wording;
state or workflow use cases should report the current business state.

### T_MINUS_1_PROMPT

History is continuity context only:

- current visible evidence overrides history;
- do not copy an old event when current identity is uncertain;
- an uncertain current clip proves neither continuation nor resolution unless
  the contract explicitly defines another mapping.

## Structured alerting template

The fence below delimits this reference template only. Never copy the fence into
`prompt_text`. Replace every angle-bracket placeholder and expand the event
block once per allowed event. Add extension output lines only for Q2-requested
Final Schema extensions.

```text
## GLOBAL_PROMPT
## 任务:
生成面向 <domain> 的视频分析摘要。
- 按已确认的业务优先级组织开头。
- 任何 N 次事件均表示 MACRO 去重后的语义事件段数量，不是 LOCAL 片段数。
- 只总结 MACRO 中保留的事件、状态变化和恢复情况，不要编造。
用户问题: {question}

## MACRO_CHUNK_PROMPT
## 任务:
合并本时间窗内的片段摘要，按已确认的业务优先级保留重要事件或状态。
Start time: {st_tm}s
End time: {end_tm}s
## 指南:
- 连续的同一对象、同一未解除或未改变事件只算一个事件段。
- 仅在明确解除/改变后再次发生、对象改变或出现独立新事件时重新计数。
- 不确定片段既不证明事件持续，也不证明事件解除。
- 不确定间隔前后同一事件仅在身份连续且没有解除证据时合并。
- 不要延续已消失的对象、动作或状态，不要复述时间行。
用户问题: {question}

## LOCAL_PROMPT
## 任务:
分析这段短视频中与 <domain> 相关的可见活动，并输出结构化字段。
Start time: {st_tm}s
End time: {end_tm}s
## 观察顺序:
1. <actor_or_object> 是否出现及其可见外观。
2. 所在位置、区域或状态。
3. 动作、状态变化和交互证据。
4. 支持非告警基线状态的正向证据。
## 事件判定契约:
- 事件 <event_name>
  - 判定条件: <minimum visible evidence>。
  - 排除条件: <look-alikes or near-misses>。
  - 固定严重程度: <critical、warn、info 中的一个值>。
- 对其余所有允许事件重复上述完整条目。
## 不确定性策略:
- <resolved uncertainty policy>。
## 事件优先级:
- <resolved primary-event business order>。
- 同时满足多个事件时只输出一个 EVENT，次要发现只写入 DESC。
## 输出规则:
- 只输出 Final Schema 字段行，不要在字段前后输出正文。
- SEVERITY 只能是 critical、warn 或 info。
- DESC 用 1-2 句简洁描述支持判定的可见证据。
- 不要输出 JSON、YAML、数组、表格、代码块或分析过程。
## 输出格式:
SEVERITY: <与所选事件对应的一个值>
EVENT: <按优先级选出的一个事件名>
DESC: <1-2句可见证据>
<在此添加每个已确认扩展字段的大写 KEY 行；无扩展则不添加>

## T_MINUS_1_PROMPT
## 上下文:
下面是前 {dur}s 的历史摘要，只能用于连续性参考，不要复制到当前输出。
- 当前片段的可见证据优先。
- 当前对象身份不确定时，不要复制历史事件。
- 当前片段不确定时，不确认事件持续或解除。
[
Start time: {st_tm}s
End time: {end_tm}s
{past_summary}
]
```

## Report-only LOCAL variant

Keep GLOBAL/MACRO/T_MINUS continuity rules, but replace structured LOCAL output
with concise factual prose. Do not include UPPER_SNAKE `KEY:` lines. The
narrative may mention multiple simultaneous visible findings, but each must
follow the confirmed evidence, exclusion, identity, and uncertainty rules.

## Semantic lint

Before registration, reject the draft when any check fails:

1. Missing any Skill-required section or required runtime placeholder.
2. Generated prompt contains triple-backtick fences or literal `<<<`.
3. Expected business events/decision rules are absent.
4. Structured LOCAL output keys differ from Final Schema.
5. Structured LOCAL asks for JSON/YAML/arrays/tables, repeated `EVENT:`, or
   slash-separated event values.
6. Severity includes values outside `critical/warn/info`.
7. Structured mode mixes free prose with schema lines, or report-only declares
   schema keys.
8. An event lacks visible evidence, exclusions, or fixed severity; or the
   contract lacks uncertainty and priority.
9. Baseline/absence is selected merely because no alert was recognized.
10. Event rules use generic phrases such as “whether X occurs/is present/is
    worn” without concrete visual boundaries.
11. LOCAL weakens, omits, changes, or invents any confirmed contract rule.
12. Any authoring placeholder such as `<domain>` or `<event_name>` remains.

The registration consistency gate proves structural alignment only; it does not
prove items 6–12 or behavior quality.

## Behavior validation

Do not call a use case behaviorally validated from registration success or one
positive clip. When representative ground truth is available:

- For each alerting/business-critical event: one clear positive, one common
  look-alike negative, and one difficult/occluded sample.
- Per use case: at least one clear baseline and, when applicable, one confirmed
  absence sample.
- Difficult samples must follow uncertainty policy, never silently baseline.
- Temporal/state-transition events need one full triggering sequence and one
  visually similar non-triggering sequence.
- For every mismatch, compare persisted `EVENT`/`SEVERITY`/`DESC` to ground
  truth, refine the use-case prompt, overwrite, and rerun the same set.

Without labeled or directly inspectable media, report the use case as
**registered but behaviorally unvalidated**.
