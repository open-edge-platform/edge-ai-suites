# Use Case Adapters

Each subdirectory here is a **use case adapter**: the small amount of code and
prompt content that specialises the generic MCP server to a specific scenario
(e.g. `child_safety`, `elder_wakeup`, `fridge`). Directories are wired into the
server via `config.yaml` → `use_case_dict.<name>`.

The framework is designed so that adding a new use case does not require
modifying core components — a new directory plus a `use_case_dict` entry is
enough.

## Directory layout

```
use-cases/
├── README.md                     # this file
├── child_safety/
│   └── prompt.md                 # VLM task prompt (see §2)
├── elder_wakeup/
│   ├── evaluate_rules.py
│   └── prompt.md
└── fridge/
    ├── config.md                 # per-use-case notes
    ├── prompt.md                 # Chinese task prompt
    └── prompt_en.md              # English variant
```

Missing files are legal:

- No `evaluate_rules.py` — the built-in `defaultRuleEvaluator` fires when the
  parsed `severity` field is `critical` or `warn`.
- No `prompt.md` — the VLM task registration step is skipped; monitors of this
  use case rely on prompts registered out of band.

## 1. `evaluate_rules.py` protocol

Invoked by `packages/rule-engine/src/index.ts` (`evaluateWithOverride`) via
`execFile("python3", [<script>, <json>])`.

**Input** — `sys.argv[1]` is a JSON-encoded `RuleContext` object:

```jsonc
{
  "monitorId": "cam_child_01",
  "useCase":   "child_safety",
  "taskId":    42,
  "summaryText": "SEVERITY: critical\nEVENT: child_fall\nDESC: ...",
  "payload": {
    "fields": {                                // parsed by built-in summary parser
      "severity":    "critical",
      "event":       "child_fall",
      "desc":        "child fell from sofa",
      "description": "child fell from sofa"    // legacy alias
    }
  }
}
```

**Output** — a single JSON object on `stdout`:

```jsonc
{
  "should_alert": true,
  "alert_message": "[child_safety] child_fall: critical — child fell from sofa"
}
```

Contract:

| Field | Required | Type | Meaning |
|-------|----------|------|---------|
| `should_alert` | ✅ | `bool` | Whether an alert row should be inserted for this task. |
| `alert_message` | conditional | `string` | Populated when `should_alert` is `true`. Stored verbatim in `alerts.description`. |

If the script exits non-zero, prints invalid JSON, or throws, the caller falls
back to `defaultRuleEvaluator`; the failure is logged at `warn` and does not
abort the task-poller loop.

## 2. `prompt.md` protocol

Declares the VLM task prompt shipped to `multilevel-video-understanding`.

A `prompt.md` file is a plain Markdown document divided by `##` headings, one
heading per prompt section:

```markdown
Free-form intro / rationale for the prompt (optional).

## LOCAL_PROMPT

...per-clip prompt content, including the required output shape...

## GLOBAL_PROMPT

...aggregation prompt used by the report generator...
```

Recognised section names (all optional; only the ones the operator registers
need to be present):

| Section | Purpose |
|---------|---------|
| `LOCAL_PROMPT` | Per-clip prompt used when the video-worker calls `POST /v1/summary` for a single motion segment. Must produce output the built-in `parseSummaryFields` parser can decode (line-oriented `KEY: value`, keys aligned with the DB schema). |
| `GLOBAL_PROMPT` | Aggregation prompt used by the report generator (daily / weekly summary flow). Consumes SRT-style captions built from stored events. |
| `MACRO_CHUNK_PROMPT` | Optional per-macro-chunk prompt for chained summaries. When absent the summary service falls back to `GLOBAL_PROMPT`. |
| `T_MINUS_1_PROMPT` | Optional context prompt for the preceding chunk (used by chained motion segments). |

Everything above the first `##` heading is treated as intro prose and ignored
at runtime.

Both `LOCAL_PROMPT` and `GLOBAL_PROMPT` may reference the following
placeholders, filled by the VLM service at request time:

| Placeholder | Meaning |
|-------------|---------|
| `{question}` | Optional user question forwarded to the VLM. |
| `{st_tm}` | Chunk start time in seconds. |
| `{end_tm}` | Chunk end time in seconds. |
| `{dur}` | Duration of the preceding chunk (used by chained summaries). |
| `{past_summary}` | Summary of the preceding chunk. |

**Format history**: earlier revisions of these adapters shipped `prompt.py`
files whose sole purpose was to hold `NAME = '''...'''` string constants.
Nothing ever executed as Python — the file was read verbatim as text and
POSTed to the VLM `/v1/tasks` endpoint. Switching to Markdown makes that
reality explicit and gives editors syntax highlighting for prose, tables, and
placeholders without the `'''` clutter.

**Runtime loading**: at present, prompt files are registered out of band by
the operator flow; the MCP server does not import them automatically.
`smartbuilding_use_case_validate` continues to work — it fetches the task's
`LOCAL_PROMPT` string from the VLM service and searches for required schema
field names, unchanged by this format switch.

## Scope in Phase 10

The design document's `parse_summary.py` and `on_task_completed.py` per-use-case
Python overrides are **not** implemented. Summary parsing is handled solely by
the built-in schema-aware `parseSummaryFields`, and post-alert side effects
belong on the MCP subscription side (a subscriber reacts to
`notifications/resources/updated`) rather than in a subprocess forked from the
video-worker. The only per-use-case Python override that remains is
`evaluate_rules.py` (wired via `use_case_dict.<uc>.evaluate_rules_path`). See
[docs/use-case-adapter.md](../docs/use-case-adapter.md) for the full recipe.

## Extended use cases (non-default — reference only, not shipped in the example configs)

`high_altitude_safety` and `parking_safety` are **not** part of the default demo
set (fridge / child_safety / elder_wakeup), so they are intentionally kept out of
`config.yaml.example`, `monitors.yaml.example`, and `demo-videos/streams.yaml`.
Their definitions are preserved here — copy the blocks you need into your own
`config.yaml` / `monitors.yaml` / `streams.yaml` to enable them. The built-in
`defaultRuleEvaluator` only handles `severity=warn|critical`; generate an
`evaluate_rules.py` override when you need event, direction, or zone gates.

**`config.yaml` → `schema.video_summary_tasks.extensions`** (add only when enabling these UCs — they are use-case-specific fields):

```yaml
- { name: "motion_direction", type: "text", required: false } # high_altitude_safety: downward | upward | horizontal | none
- { name: "parking_zone", type: "text", required: false }     # parking_safety: fire_lane | entrance | handicapped | double_yellow_line | normal | unknown
```

**`config.yaml` → `use_case_dict`**:

```yaml
high_altitude_safety:
  description: "High-altitude object throwing detection"
  video_summary_task: high_altitude_monitor
  # Add evaluate_rules_path when you need to gate on event=high_altitude_throw
  # and motion_direction=downward instead of using the default severity rule.
  reports:
    data_source: alerts
    default_type: daily
    filter: {}

parking_safety:
  description: "Community parking violation detection (fire lane / entrance / handicapped)"
  video_summary_task: parking_safety_monitor
  # Add evaluate_rules_path when you need to suppress non-violation events,
  # exclude normal zones, or append parking_zone details to the alert message.
  reports:
    data_source: alerts
    default_type: daily
    filter: {}
```

**`monitors.yaml` → `monitors`**:

```yaml
cam_high_altitude:
  enabled: true
  name: "High Altitude Safety Camera"
  source_url: rtsp://localhost:8554/live/high_altitude
  use_case: high_altitude_safety
  pipeline_config:
    motion: { enabled: true, diff_threshold: 25 }
    prefilter: { enabled: false }
    recording: { enabled: false, interval_seconds: 60, retention_days: 1 }
    segment: { max_duration: 10 }

cam_parking:
  enabled: true
  name: "Parking Safety Camera"
  source_url: rtsp://localhost:8554/live/parking
  use_case: parking_safety
  pipeline_config:
    motion: { enabled: true, diff_threshold: 25 }
    prefilter: { enabled: false }
    recording: { enabled: false, interval_seconds: 60, retention_days: 1 }
    segment: { max_duration: 10 }
```

**`demo-videos/streams.yaml` → `streams`** (bring your own clips — `*.mp4` is gitignored, so `cam_ha_test/building-throwing-2.mp4` / `cam_parking/false-parking.mp4` are not shipped in the repo):

```yaml
cam_high_altitude:
  enabled: true
  file: cam_ha_test/building-throwing-2.mp4
  rtsp_url: rtsp://localhost:8554/live/high_altitude
  loop: true

cam_parking:
  enabled: true
  file: cam_parking/false-parking.mp4
  rtsp_url: rtsp://localhost:8554/live/parking
  loop: true
```
