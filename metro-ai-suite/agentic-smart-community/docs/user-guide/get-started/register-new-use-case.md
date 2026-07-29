# Register a New Use Case

With the MCP server running, add a new use case **by conversation**: no code and no restart. You describe it to a connected agent (for example, OpenClaw), and the [`video-summary-prompt-studio`](../../../skills/video-summary-prompt-studio/SKILL.md) skill turns your description into a registered, running use case.

**Prerequisites:** an agent host is connected (see [Connect an agent host (zero-code)](../get-started.md#step-3---connect-an-agent-host)) and the skills are imported (OpenClaw [Step 3](../get-started.md#openclaw)).

> **Tip — use a capable cloud model for registration.** Registering a use case is the most model-demanding flow on the platform: the agent must infer events and schema, draft a four-section VLM prompt, and pass the server-side consistency gate. We recommend switching the agent to a strong cloud model for this conversation — e.g. in OpenClaw, pick a MiniMax model from the model selector — rather than a small local model. This only affects the **authoring** step; once the use case is registered, day-to-day monitoring runs on the on-device VLM/LLM stack, independent of which model the agent used.

## How it works

1. **Describe the use case in chat.** Give the agent a name (lowercase snake_case) and a short natural-language description of what to watch for — optionally the RTSP stream to bind it to:

   > *[smart-community] Create a use case `pet_safety`: monitor the pet camera for escape, trapped, or aggressive behavior. Stream: `rtsp://localhost:8554/live/pet`.*

2. **Answer the gating questions.** The skill first checks that one primary event per clip can represent the request, then asks Q1/Q2 (skipping anything your description already answers). It may ask one compact boundary question when visual evidence, event priority, or uncertainty remains ambiguous:
   - **Q1 — Alerting?** *No* → a report-only use case (no alert schema, no rules). *Yes* → alerting via the built-in rule evaluator on the base schema `severity, event, desc` (alerts fire on `severity = warn | critical`).
   - **Q2 — Extend the schema?** *(only if Q1 = yes)* *No* → **default rule path**: the schema stays `severity, event, desc`, no custom code. *Yes* → **custom rule path**: the extra fields you name (e.g. `zone_id`, `risk_area`) are added on top of the base schema, and a per-use-case `evaluate_rules.py` is generated to decide alerts from them.

3. **Confirm the mode, final schema, and rule path.** The agent echoes the applicable decision before registering:

   ```
  Report-only:      schema none; rule none
  Base alerting:    severity, event, desc; defaultRuleEvaluator
  Extended alerting: severity, event, desc + extensions; evaluate_rules.py
   ```

4. **The agent registers it.** It drafts the four-section VLM prompt (plus `evaluate_rules.py` for every extended schema or custom alert policy), then calls `smartbuilding_use_case_register` in two steps — `action=generate_task` (POSTs the video-summary task to `multilevel-video-understanding` and writes `use-cases/<name>/prompt.md`), followed by `action=register` with `persist=true` (applies the schema, updates `use_case_dict`, and writes `config.yaml`). A built-in consistency gate validates prompt ↔ schema ↔ rules and rejects mismatches before side effects.

5. **Bind a camera (optional).** If you supplied a stream URL, the agent registers the monitor (`smartbuilding_monitor_ctl register_source`) as part of the flow; otherwise add one later through the connected agent.

When registration finishes, the agent reports the new use case's configuration along with the full list of monitors and registered use cases. The use case is live immediately — alerts start flowing to any client subscribed to `smartbuilding://monitor/<monitor_id>/alerts`.

> **Tip:** Things to *detect* (escape, trapped, aggressive behavior, …) are event **values**, not schema fields — describe what to watch for, and only name extra schema fields in Q2 when you truly need them persisted and queryable.

For the full authoring rules the agent follows (prompt anchors, schema invariants, retry behavior), see the [`video-summary-prompt-studio` skill](../../../skills/video-summary-prompt-studio/SKILL.md) and the [`use_case_register` tool reference](./mcp_tools_list.md#8-smartbuilding_use_case_register).
