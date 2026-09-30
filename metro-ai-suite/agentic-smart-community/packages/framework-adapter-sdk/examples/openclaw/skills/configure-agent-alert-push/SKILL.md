---
name: configure-agent-alert-push
description: "Configure real-time Smart Community monitor alerts for a specified OpenClaw agent. Use when a user asks to bind, route, subscribe, or push one monitor's alerts to an agent session. Requires an agent ID and monitor ID, and always targets session agent:{agent-id}:{monitor-id}."
---

<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configure Agent Alert Push

Configure the `smart-community-alerts` OpenClaw adapter so one Smart Community
monitor pushes new alerts into a specified agent's dedicated monitor session.

The resulting route must always have this shape:

```json
{
  "agentId": "<agent-id>",
  "sessionKey": "agent:<agent-id>:<monitor-id>",
  "deliver": false
}
```

`deliver: false` is required for this workflow: the adapter injects alerts into
the OpenClaw session without an LLM call or external-channel delivery.

## Required inputs

Collect both values before changing configuration:

- `agent-id`: an existing OpenClaw agent ID.
- `monitor-id`: an existing Smart Community monitor ID.

Do not infer either value from a display name. If one is missing, ask the user.

## Workflow

1. Verify that `agent-id` exists in OpenClaw.
2. Call `smart_community_monitor_ctl` with `action: list` and verify an exact
   `monitor_id` match. Stop and report the problem if the monitor does not exist.
3. Read the active `plugins.entries.smart-community-alerts` configuration from
   OpenClaw. Do not rely on a repository example as the live configuration.
4. Preserve the existing `mcpServer`, `cursorFile`, `pollFallbackMs`, monitor
   entries, and alert routes.
5. Under
   `plugins.entries.smart-community-alerts.config.monitors.<monitor-id>.alerts`,
   upsert this route:

   ```json
   {
     "agentId": "<agent-id>",
     "sessionKey": "agent:<agent-id>:<monitor-id>",
     "deliver": false
   }
   ```

   If that monitor already has a route for the same `agentId`, update that route
   to the required `sessionKey` instead of adding a duplicate. Keep routes for
   other agents unchanged.
6. Ensure `plugins.entries.smart-community-alerts.enabled` is `true`.
7. Write the merged configuration through OpenClaw's structured configuration
   interface. Never replace the complete `monitors` object with only the new
   monitor and never edit JSON with string substitution.
8. Run `openclaw config validate`. If validation fails, report the error and do
   not restart the gateway.
9. After successful validation, run `openclaw gateway restart` so the adapter
   opens the new monitor subscription.

## Configuration example

For `agent-id = child-safety-agent` and `monitor-id = cam_child`, merge:

```json
{
  "plugins": {
    "entries": {
      "smart-community-alerts": {
        "enabled": true,
        "config": {
          "mcpServer": {
            "url": "http://localhost:3100/mcp"
          },
          "monitors": {
            "cam_child": {
              "alerts": [
                {
                  "agentId": "child-safety-agent",
                  "sessionKey": "agent:child-safety-agent:cam_child",
                  "deliver": false
                }
              ]
            }
          }
        }
      }
    }
  }
}
```

The example is illustrative. Preserve all unrelated live configuration when
applying it. If the plugin has not been configured yet, ask for the Smart
Community MCP URL rather than assuming the example URL.

## Verification

After restart:

1. Confirm the gateway log has no `[sb-alerts] invalid plugin config` or adapter
   startup error.
2. Confirm the adapter subscribed to
   `smart-community://monitor/<monitor-id>/alerts`.
3. When the next alert is created, confirm it is appended to
   `agent:<agent-id>:<monitor-id>`.
4. Confirm the monitor cursor advances in the configured `cursorFile`, or in the
   default `<OPENCLAW_HOME>/smart-community-alerts-cursor.json`.

Report the exact monitor ID, agent ID, session key, validation result, and gateway
restart result. Never claim delivery succeeded until an alert has actually been
observed in the target session.
