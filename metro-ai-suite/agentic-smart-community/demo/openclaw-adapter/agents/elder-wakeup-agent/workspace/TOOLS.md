# TOOLS.md — Environment Info

## Monitors

| monitor_id | use_case | Location | What it watches |
|---|---|---|---|
| `cam_elder_bedroom` | `elder_wakeup` | Elder's bedroom | Bed: get-up time vs. still-in-bed |

`cam_elder_bedroom` is your default. There may be **more than one** elder-bedroom camera
(e.g. `cam_elder_bedroom_2`). To see what's actually registered, call
`smartbuilding_monitor_ctl action=list` and filter by `use_case: elder_wakeup`; if several
match, ask the family which one before querying.

All camera access, VLM calls, database reads, and report generation go through the
`smartbuilding_*` MCP tools, provided by the **`smart-community`** MCP server (registered
in OpenClaw as `mcp.servers.smart-community`; verify with `openclaw mcp probe
smart-community`). See the **smartbuilding-toolkit** skill for the tool reference. You don't address
services, ports, or file paths directly. Wakeup alerts are raised automatically by the
pipeline; you read them with `smartbuilding_alert_query`.
