# MCP Tools and Resources API Reference

The MCP server exposes Smart Community operations as MCP tools and read-only data as MCP
resources over Streamable HTTP.

| Item | Value |
| ---- | ----- |
| Endpoint | `http://<mcp-host>:3100/mcp` |
| Protocol | MCP over Streamable HTTP with JSON-RPC 2.0 |
| Authentication | None; restrict the endpoint to loopback or a trusted private network |
| Bind address | `127.0.0.1`, hardcoded and not configurable — this endpoint and the dashboard are local-only by design. The container runs with `network_mode: host`, so this is the host's own loopback. For off-host access, forward the port over SSH: `ssh -N -L 3100:127.0.0.1:3100 user@host`. |
| Required request headers | `Content-Type: application/json` and `Accept: application/json, text/event-stream` |
| Session header | `mcp-session-id` after initialization |

Tool and resource results contain JSON serialized inside an MCP text-content field. For a tool,
parse `result.content[0].text`; for a resource, parse `result.contents[0].text`.

## Start an MCP session

Every Streamable HTTP client must initialize a session before calling tools or reading resources.

```bash
export MCP_URL=http://localhost:3100/mcp

SID=$(curl -fsS -D - -o /tmp/mcp-initialize.json -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smart-community-api-client","version":"1.0"}}}' \
  | awk 'tolower($1) == "mcp-session-id:" {gsub("\r", "", $2); print $2}')

test -n "$SID" || { echo "MCP server did not return mcp-session-id" >&2; exit 1; }

curl -fsS -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
```

Include `mcp-session-id: $SID` on every subsequent request. To inspect the server-advertised
interfaces, call `tools/list`, `resources/list`, and `resources/templates/list`:

```bash
curl -fsS -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | jq
```

Replace `tools/list` with `resources/list` or `resources/templates/list` to inspect resources.

## Call a tool

All tools use the same JSON-RPC method. Replace `TOOL_NAME` and `ARGUMENTS` in this envelope:

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "TOOL_NAME",
    "arguments": {}
  }
}
```

The following shell helper makes the examples in this section concise:

```bash
mcp_tool_call() {
  local tool_name=$1
  local arguments=$2
  jq -nc --arg name "$tool_name" --argjson arguments "$arguments" \
    '{jsonrpc:"2.0",id:10,method:"tools/call",params:{name:$name,arguments:$arguments}}' \
  | curl -fsS -X POST "$MCP_URL" \
      -H "Content-Type: application/json" \
      -H "Accept: application/json, text/event-stream" \
      -H "mcp-session-id: $SID" \
      --data-binary @- \
  | jq -r 'if .result.isError then error(.result.content[0].text) else .result.content[0].text end | fromjson'
}
```

### `smart_community_alert_query`

Query or acknowledge alerts for one monitor.

| Argument | Type | Required | Notes |
| -------- | ---- | -------- | ----- |
| `monitor_id` | string | Yes | Monitor ID |
| `action` | enum | Yes | `latest`, `by_date`, `ack`, or `stats` |
| `limit` | number | No | Maximum rows for `latest`; default 20 |
| `start_date`, `end_date` | string | For `by_date` | Inclusive dates in `YYYY-MM-DD` form; optional for `stats` |
| `alert_id`, `ack_by` | number, string | For `ack` | Alert ID and acknowledging user |

```bash
mcp_tool_call smart_community_alert_query \
  '{"monitor_id":"cam_child","action":"latest","limit":20}'
```

### `smart_community_plan_ctl`

Manage arbitrary per-monitor JSON plans used by rule evaluators.

| Argument | Type | Required | Notes |
| -------- | ---- | -------- | ----- |
| `monitor_id` | string | Yes | Monitor ID |
| `action` | enum | Yes | `list`, `upsert`, or `delete` |
| `name` | string | For `upsert`, `delete` | Unique plan name within the monitor |
| `plan` | object | For `upsert` | Arbitrary plan data |
| `plan_date` | string | No | Optional `YYYY-MM-DD` metadata |
| `active_only` | boolean | No | `list` defaults to active plans only |

```bash
mcp_tool_call smart_community_plan_ctl \
  '{"monitor_id":"cam_elder_bedroom","action":"upsert","name":"morning-check","plan_date":"2026-07-29","plan":{"expected_wakeup":"07:30"}}'
```

### `smart_community_scene_query`

Analyze the monitor's current `latest.jpg` frame with the configured VLM.

| Argument | Type | Required | Notes |
| -------- | ---- | -------- | ----- |
| `monitor_id` | string | Yes | Monitor ID |
| `prompt` | string | No | Overrides the default scene-description prompt |
| `vlm_url` | string | No | Overrides `vlmService.url` |
| `model` | string | No | Overrides `vlmService.model` |
| `max_edge_px` | number | No | Maximum frame edge sent to the VLM |

```bash
mcp_tool_call smart_community_scene_query \
  '{"monitor_id":"cam_fridge","prompt":"List the visible food items."}'
```

### `smart_community_generate_report`

Generate and store a report using the monitor's use-case report configuration.

| Argument | Type | Required | Notes |
| -------- | ---- | -------- | ----- |
| `monitor_id` | string | Yes | Monitor ID |
| `type` | enum | No | `daily`, `weekly`, `monthly`, or `custom` |
| `period_start`, `period_end` | string | For `custom` | Inclusive `YYYY-MM-DD` or `YYYY-MM-DD HH:MM` values |
| `data_source` | enum | No | `events`, `alerts`, or `video_summary_tasks` |
| `filter` | object | No | Exact column/value filters for the selected data source |

```bash
mcp_tool_call smart_community_generate_report \
  '{"monitor_id":"cam_child","type":"daily"}'
```

### `smart_community_monitor_ctl`

Manage one monitor across the database, videostream-analytics, and video worker.

| Argument | Type | Required | Notes |
| -------- | ---- | -------- | ----- |
| `action` | enum | Yes | `list`, `status`, `start`, `stop`, `register_source`, or `unregister` |
| `monitor_id` | string | Except `list` | Defaults to `cam_<use_case>` only for `register_source` |
| `source_url` | string | For `register_source` | Any source protocol supported by videostream-analytics |
| `use_case` | string | For `register_source` | Key in `config.yaml` `use_case_dict` |
| `name` | string | No | Display name |
| `pipeline_config` | object | No | Overrides the default analytics pipeline configuration |
| `persist` | boolean | No | Mirrors lifecycle changes into the booted `monitors.yaml`; default true |

List all monitors:

```bash
mcp_tool_call smart_community_monitor_ctl '{"action":"list"}'
```

Register and persist a source:

```bash
mcp_tool_call smart_community_monitor_ctl \
  '{"action":"register_source","monitor_id":"cam_child","name":"Child Safety Camera","source_url":"rtsp://localhost:8555/live/test","use_case":"child_safety","persist":true}'
```

### `smart_community_monitors_compose`

Validate or apply all monitor declarations in a `monitors.yaml` file.

| Argument | Type | Required | Notes |
| -------- | ---- | -------- | ----- |
| `action` | enum | Yes | `validate`, `up`, `down`, `restart`, or `ps` |
| `file` | string | Yes | Absolute path or path relative to the MCP server working directory |
| `monitor_id` | string | No | Restrict the action to one declared monitor |

```bash
mcp_tool_call smart_community_monitors_compose \
  '{"action":"ps","file":"demo/quick-start/monitors.demo.yaml"}'
```

### `smart_community_video_db`

Run a parameterized, read-only SQLite query. Only `SELECT` statements are accepted.

| Argument | Type | Required | Notes |
| -------- | ---- | -------- | ----- |
| `query` | string | Yes | A `SELECT` statement |
| `params` | array | No | Values for positional `?` placeholders |

```bash
mcp_tool_call smart_community_video_db \
  '{"query":"SELECT id, status, use_case FROM monitors WHERE id = ?","params":["cam_child"]}'
```

### `smart_community_use_case_validate`

Validate the config entry, VLM task registration, and prompt/schema consistency for a use case.

| Argument | Type | Required |
| -------- | ---- | -------- |
| `use_case` | string | Yes |

```bash
mcp_tool_call smart_community_use_case_validate '{"use_case":"child_safety"}'
```

### `smart_community_use_case_register`

Manage a use case at runtime. New use cases normally use `generate_task` first,
then `register` after the prompt and final schema have been confirmed.

| Argument | Type | Required | Notes |
| -------- | ---- | -------- | ----- |
| `action` | enum | Yes | `generate_task`, `register`, `unregister`, or `list` |
| `use_case` | string | Except for `list` | Must match `^[a-z][a-z0-9_]{1,63}$` |
| `video_summary_task` | string | No | Defaults to `<use_case>_monitor` |
| `description` | string | No | Human-readable task description |
| `prompt_text` | string | For `generate_task` | Full four-section prompt text without Markdown code fences |
| `evaluate_rules_path` | string | For extended schema or custom alert behavior | Path to a Python rule override to stage and validate |
| `schema_extensions` | array | No | Extra fields `{name, type, required}`; normally inferred from `LOCAL_PROMPT`, so pass only to set a non-text type or override `required` |
| `reports`, `summarize` | object | No | Use-case report and per-clip summary configuration |
| `overwrite` | boolean | No | Replace an existing use-case entry; default false |
| `persist` | boolean | No | Mirror the mutation into the booted `config.yaml`; default true |

Step 1, register the VLM task and save its prompt:

```bash
mcp_tool_call smart_community_use_case_register \
  '{"action":"generate_task","use_case":"door_watch","description":"Door activity monitoring","prompt_text":"## GLOBAL_PROMPT\nSummarize door activity over the full period.\n## MACRO_CHUNK_PROMPT\nSummarize notable door activity in this chunk.\n## LOCAL_PROMPT\nReturn exactly:\nSEVERITY: <text>\nEVENT: <text>\nDESC: <text>\n## T_MINUS_1_PROMPT\nUse the previous chunk only as context for the current observation."}'
```

Step 2, apply the schema and persist the use case:

```bash
mcp_tool_call smart_community_use_case_register \
  '{"action":"register","use_case":"door_watch","persist":true}'
```

### `smart_community_rule_eval`

Re-run a rule against a completed summary task. The default is a dry run.

| Argument | Type | Required | Notes |
| -------- | ---- | -------- | ----- |
| `monitor_id` | string | Yes | Monitor ID |
| `task_id` | number | No | Defaults to the monitor's latest completed task |
| `create_alert` | boolean | No | Persist an alert when the rule fires; default false |

```bash
mcp_tool_call smart_community_rule_eval \
  '{"monitor_id":"cam_child","create_alert":false}'
```

## Read a resource

Use `resources/read` with the resource URI:

```json
{
  "jsonrpc": "2.0",
  "id": 20,
  "method": "resources/read",
  "params": {
    "uri": "smart-community://monitors"
  }
}
```

This helper reads and parses the JSON text returned by any Smart Community resource:

```bash
mcp_resource_read() {
  local uri=$1
  jq -nc --arg uri "$uri" \
    '{jsonrpc:"2.0",id:20,method:"resources/read",params:{uri:$uri}}' \
  | curl -fsS -X POST "$MCP_URL" \
      -H "Content-Type: application/json" \
      -H "Accept: application/json, text/event-stream" \
      -H "mcp-session-id: $SID" \
      --data-binary @- \
  | jq -r '.result.contents[0].text | fromjson'
}
```

| Resource URI | Content |
| ------------ | ------- |
| `smart-community://monitors` | `{ monitors }`: every registered monitor and its database status |
| `smart-community://monitor/{id}/latest-frame` | Placeholder frame response; currently returns `frame: null` until analytics frame integration is implemented |
| `smart-community://monitor/{id}/stats` | `{ monitorId, events, alerts }`: today's event and alert counts |
| `smart-community://monitor/{id}/alerts` | `{ monitorId, latestId, alerts }`: latest 20 delivered alerts |
| `smart-community://monitor/{id}/alerts{?since}` | Up to 200 delivered alerts whose IDs are greater than the cursor; call it as `smart-community://monitor/{id}/alerts?since={alert_id}` |

```bash
mcp_resource_read 'smart-community://monitors'
mcp_resource_read 'smart-community://monitor/cam_child/stats'
mcp_resource_read 'smart-community://monitor/cam_child/alerts'
mcp_resource_read 'smart-community://monitor/cam_child/alerts?since=42'
```

The alerts resources exclude audit rows suppressed by cooldown. Use
`smart_community_alert_query` when the full alert audit trail is required. For an incremental read,
save the returned `latestId` and pass it as the next `since` cursor. The cursor must be a
non-negative integer.

## Subscribe to a resource

Alert resources support subscriptions. Subscribe after initialization, then keep an SSE `GET`
open with the same session ID.

```bash
curl -fsS -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":30,"method":"resources/subscribe","params":{"uri":"smart-community://monitor/cam_child/alerts"}}'

curl -fsS -N -X GET "$MCP_URL" \
  -H "Accept: text/event-stream" \
  -H "mcp-session-id: $SID"
```

When a delivered alert is created, the SSE connection receives:

```text
event: message
data: {"jsonrpc":"2.0","method":"notifications/resources/updated","params":{"uri":"smart-community://monitor/cam_child/alerts"}}
```

The notification does not contain the alert. Call `resources/read` with the last `latestId` as
the `since` cursor to retrieve it. Unsubscribe with:

```bash
curl -fsS -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":31,"method":"resources/unsubscribe","params":{"uri":"smart-community://monitor/cam_child/alerts"}}'
```

## Errors and state-changing calls

- JSON-RPC protocol errors appear in the top-level `error` object.
- Tool execution errors return `result.isError: true` and explanatory text in
  `result.content[0].text`.
- Resource input errors, such as a negative alert cursor, return an MCP resource-read error.
- Confirm intent before `monitor_ctl` `stop` or `unregister`, `monitors_compose` `down` or
  `restart`, `plan_ctl` `delete`, `alert_query` `ack`, `use_case_register` mutations, or
  `rule_eval` with `create_alert: true`.
- `smart_community_video_db` is read-only and rejects non-`SELECT` SQL.

## See also

- [MCP Tools Guide](../how-to-guides/mcp-tools.md)
- [MCP Subscription Reference](./api-reference-mcp-subscription.md)
- [MCP Webhook Event API](./api-reference-mcp-webhook-event.md)
