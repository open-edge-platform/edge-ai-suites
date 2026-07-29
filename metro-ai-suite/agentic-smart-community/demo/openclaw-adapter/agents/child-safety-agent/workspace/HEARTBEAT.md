# HEARTBEAT.md

## Scheduled wakeups (defined in ~/.openclaw/cron/jobs.json)

- **child-safety-daily-22** (cron `0 22 * * *`) —
  Auto-generate today's child-safety daily report covering all alerts and
  scene highlights. Routes through `agent:child-safety-agent:main` with
  `sessionTarget: session:child-safety-alert-en`.

## Event-driven wakeups

- **Alert notification**: when the rule engine inserts an alert, the plugin
  notifier pushes an `agentTurn` to `sessionKey: agent:child-safety-agent:main`.
  Payload is the rendered alert text (see rule-engine → renderAlertMessage).
  Lead the reply with the event + time + suggested action.

## Manual triggers

- Parent asks "跑一下告警审计" / "audit today's alerts" → call `rule_eval`.
- Parent asks "孩子现在在哪 / check on the kid" → call `scene_query`.
