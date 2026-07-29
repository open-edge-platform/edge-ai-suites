# TOOLS.md — Environment Info

## Monitor

| monitor_id | use_case | Location | What it watches |
|---|---|---|---|
| `cam_fridge` | `fridge` | Kitchen, fridge front | Fridge contents + door open/close activity |

`cam_fridge` is your default. To see what's actually registered right now, call
`smartbuilding_monitor_ctl action=list` and filter by `use_case: fridge`.

All camera access, VLM calls, database reads, and report generation go through the
`smartbuilding_*` MCP tools, provided by the **`smart-community`** MCP server (registered
in OpenClaw as `mcp.servers.smart-community`; verify with `openclaw mcp probe
smart-community`). See the **smartbuilding-toolkit** skill for the tool reference. You don't address
services, ports, or file paths directly.
