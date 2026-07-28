# Register a New Use Case

The three demo monitors are only examples — the platform is use-case-agnostic, so you add a new use case **by conversation**: no code, no restart. You describe it to a connected agent (e.g. OpenClaw), and the [`video-summary-prompt-studio`](../../../skills/video-summary-prompt-studio/SKILL.md) skill turns your description into a registered, running use case.

**Prerequisites:** an agent host is connected (see [Connect an agent host (zero-code)](../get-started.md#connect-an-agent-host-zero-code)) and the skills are imported (OpenClaw [Step 3](../get-started.md#openclaw)).

> **Tip — use a capable cloud model for registration.** Registering a use case is the most model-demanding flow on the platform: the agent must infer events and schema, draft a four-section VLM prompt, and pass the server-side consistency gate. We recommend switching the agent to a strong cloud model for this conversation — e.g. in OpenClaw, pick a MiniMax model from the model selector — rather than a small local model. This only affects the **authoring** step; once the use case is registered, day-to-day monitoring runs on the on-device VLM/LLM stack, independent of which model the agent used.

## How it works

1. **Describe the use case in chat.** Give the agent a name (lowercase snake_case) and a short natural-language description of what to watch for — optionally the RTSP stream to bind it to:

   > *[smart-community] Create a use case `pet_safety`: monitor the pet camera for escape, trapped, or aggressive behavior. Stream: `rtsp://localhost:8554/live/pet`.*

2. **Answer two questions.** Before generating anything, the skill asks exactly two questions (skipping any your description already answers):
   - **Q1 — Alerting?** *No* → a report-only use case (no alert schema, no rules). *Yes* → alerting via the built-in rule evaluator on the base schema `severity, event, desc` (alerts fire on `severity = warn | critical`).
   - **Q2 — Extend the schema?** *(only if Q1 = yes)* *No* → **default rule path**: the schema stays `severity, event, desc`, no custom code. *Yes* → **custom rule path**: the extra fields you name (e.g. `zone_id`, `risk_area`) are added on top of the base schema, and a per-use-case `evaluate_rules.py` is generated to decide alerts from them.

3. **Confirm the final schema.** The agent echoes the decision for your approval before registering:

   ```
   Final Schema: severity, event, desc      (+ <extensions> only if you asked in Q2)
   Rule Path:    defaultRuleEvaluator        (or evaluate_rules.py on the custom path)
   ```

4. **The agent registers it.** It drafts the four-section VLM prompt (plus `evaluate_rules.py` on the custom path), then calls `smartbuilding_use_case_register` in two steps — `action=register_task` (POSTs the video-summary task to `multilevel-video-understanding` and writes `use-cases/<name>/prompt.md`), followed by `action=register` with `persist=true` (applies the schema, updates `use_case_dict`, and writes `config.yaml`). A built-in consistency gate validates prompt ↔ schema and rejects the registration with a diff if they mismatch, so the agent fixes and retries instead of leaving a half-wired use case.

5. **Bind a camera (optional).** If you supplied a stream URL, the agent registers the monitor (`smartbuilding_monitor_ctl register_source`) as part of the flow; otherwise add one later — see step 2 in [Run a clean, use-case-free server](../get-started.md#run-a-clean-use-case-free-server).

When registration finishes, the agent reports the new use case's configuration along with the full list of monitors and registered use cases. The use case is live immediately — alerts start flowing to any client subscribed to `smartbuilding://monitor/<monitor_id>/alerts`.

> **Tip:** Things to *detect* (escape, trapped, aggressive behavior, …) are event **values**, not schema fields — describe what to watch for, and only name extra schema fields in Q2 when you truly need them persisted and queryable.

For the full authoring rules the agent follows (prompt anchors, schema invariants, retry behavior), see the [`video-summary-prompt-studio` skill](../../../skills/video-summary-prompt-studio/SKILL.md) and the [`use_case_register` tool reference](./mcp_tools_list.md#8-smartbuilding_use_case_register).
