# Demo Overview — Three Validated Use Cases

This bundle provides reference configurations for three Agentic Smart Community demos: **Fridge Manager**, **Child Safety**, and **Elder Get-Up**. Supply your own loopable video inputs to exercise the full pipeline — motion detection, NPU pre-filtering, VLM video understanding, rule evaluation, and agent-facing alerts/reports — on a single Intel Core Ultra machine with no cloud dependency.

## At a glance

| Item | Value |
|---|---|
| Purpose | Multi-camera, local-first smart-community video-understanding reference implementation |
| Compute platform | Intel Core Ultra (XPU runs the VLM, NPU runs YOLO pre-filtering) |
| Inference path | Fully local — no cloud dependency |
| Implemented use cases | Fridge Manager / Child Safety / Elder Get-Up |
| Demo channels | Up to four RTSP streams (`fridge` / `child` / `elder` / `elder2`) when their video paths are supplied |
| Integration | MCP (Model Context Protocol) — any MCP-capable agent can drive the demo |

## How the demo runs

Two configuration files drive the bundle:

- [config.demo.yaml](quick-start/config.demo.yaml) — service endpoints plus the `use_case_dict` (each use case declares its Video Summary task, DB schema extensions, summarize tuning, and report policy).
- [monitors.demo.yaml](quick-start/monitors.demo.yaml) — the per-camera monitors that reference those use cases, with their RTSP source and pipeline config (motion / prefilter / ROI / recording).

Start and stop the demo with the bundled scripts (the MCP server itself now runs
as a container in [docker/compose.yaml](../docker/compose.yaml); `start-demo.sh`
pushes the RTSP streams, writes the demo config/monitors, then brings the stack up
via `setup_docker.sh --light`):

```bash
demo/quick-start/start-demo.sh   # push RTSP streams + write demo config, then start the stack
demo/quick-start/stop-demo.sh    # stop streams + app tier (vllm stays warm)
```

For video-path variables, automatic stream skipping, and the full installation sequence, see [Ready-to-Run Demo](../docs/user-guide/get-started/ready-to-run-demo.md).

---

## Demo 1 — Fridge Manager (`cam_fridge`)

**What it does.**
The fridge camera treats each door open/close as a motion event.
The Video Summary service narrates what happened at open / take-out / close granularity and stores it, so the fridge's contents are tracked over time.
A scheduled daily report aggregates the day's activity and turns it into staple-shortage reminders (milk, eggs, meat, …), dietary-structure suggestions, and lifestyle tips.

**Pipeline.**
Report-only use case — the summary task emits no severity/event lines, so no alert columns are parsed.
Motion detection is on; the NPU pre-filter is off (see [monitors.demo.yaml](quick-start/monitors.demo.yaml)); reports are built from the `events` data source (`fridge` use case in [config.demo.yaml](quick-start/config.demo.yaml)).

**Try these questions (ask the agent in order).**

1. *"Generate today's fridge daily report."* → runs the daily-report flow (generate raw → polish with the user profile → store → push).
2. *"Given my weight-loss goal, is the food in my fridge reasonable?"* → pulls the latest fridge frame and runs the local VLM (`scene_query`) against the user's health goals.
3. *"Any other slimming tips? Where nearby is good to exercise?"* → diet suggestions plus a web search for nearby facilities based on the home address.

---

## Demo 2 — Child Safety (`cam_child`)

**What it does.**
The child camera watches for dangerous behaviour and raises an immediate alert on the parent's chat session.
Typical events: playing with scissors (critical), playing with a lighter near curtains (critical), climbing a window sill (critical), falling (warn), jumping on the sofa (warn).
An end-of-day report aggregates the day's danger events by type (e.g. "played with fire 6×, climbed 4×, played with a knife 5×") together with childproofing advice — no proactive push on a day with zero events.

**Pipeline.**
Two-stage gating keeps the VLM cheap: lightweight motion detection first, then an NPU YOLO11s pre-filter on `target_classes: [person, knife, scissors, bottle]` (min confidence 0.4).
Only clips that pass both stages reach the Video Summary service, and an ROI crop sends just the region of interest.
The rule engine parses `severity` / `event` / `desc` and alerts on `warn`/`critical` via the default evaluator.

**Try these questions.**

- *"How many dangerous events happened this week?"*
- *"How should I childproof the living room?"*

---

## Demo 3 — Elder Get-Up (`cam_elder_bedroom`)

**What it does.**
The bedroom camera tracks the elder's daily get-up time and compares it against a baseline.
When wake-up is overdue — later than the expected time plus a grace window — it raises a `late_wakeup` alert.
An end-of-week report summarizes get-up times and on-time vs. late days.

**Pipeline.**
Motion detection plus an NPU YOLO pre-filter (person class) feed the Video Summary service, which reports whether the elder is up and at what time.
This is a time-based use case: a custom rule adapter (`demo/prompts/elder_wakeup_evaluate_rules.py`) judges by `event` + `wakeup_time` rather than a severity threshold, and reports are weekly, filtered to `event: wakeup` (`elder_wakeup` use case in [config.demo.yaml](quick-start/config.demo.yaml)).

**Two-camera design (optional second channel).**
A second monitor, `cam_elder_bedroom_2` (disabled by default in [monitors.demo.yaml](quick-start/monitors.demo.yaml)), reuses the same use case on a separate RTSP path, SQLite scope, and notification channel.
It is meant to run continuously as a persistent alert-demo channel, while the primary bedroom camera can be configured to pause once the elder is confirmed up — mirroring a real household that stops watching after wake-up.

**Try these questions.**

- *"What time did Dad get up this week?"*
- *"Anything unusual today?"*

---

## Video inputs

Videos are user-provided and excluded from release artifacts. [quick-start/streams.yaml](quick-start/streams.yaml) maps each environment variable to its RTSP path; an unavailable input is warned about and skipped.

| Use case | Stream path | Environment variable |
|---|---|---|
| Fridge Manager | `live/fridge` | `SMART_COMMUNITY_DEMO_FRIDGE_VIDEO` |
| Child Safety | `live/child` | `SMART_COMMUNITY_DEMO_CHILD_VIDEO` |
| Elder Get-Up | `live/elder` | `SMART_COMMUNITY_DEMO_ELDER_VIDEO` |
| Elder Get-Up (second input) | `live/elder2` | `SMART_COMMUNITY_DEMO_ELDER_2_VIDEO` |
