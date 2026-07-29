# HEARTBEAT.md

## Scheduled wakeups (defined in ~/.openclaw/cron/jobs.json)

- **elder-wakeup-weekly-22** (cron `0 22 * * 0`, Sun 22:00 Asia/Shanghai) —
  Generate this week's elder wakeup report. Call `daily_report` with a 7-day
  `start_time`/`end_time` covering Mon 00:00 to Sun 23:59 (the plugin
  dispatches on `useCase=elder_wakeup` and aggregates wakeup events +
  late_wakeup/no_wakeup alerts). See AGENTS.md "Weekly Report Workflow".

- **elder-wakeup-fallback-10** (cron `0 10 * * *`) —
  Run `rule_eval` over today's tasks. If no get_up event observed, call
  `scene_query` with the monitor's default prompt; on "bed occupied" emit
  a `no_wakeup` alert. On "bed empty", log only — do not alert.

- **daily-reset-00** (cron `0 0 * * *`) —
  New day: resume stream_monitor + worker if `pauseAfterTargetEvent` paused
  them yesterday, and clear `last_get_up_at`/`last_get_up_date` from
  monitor_state so today starts fresh.

## Event-driven wakeups

- **Alert notification**: when rule engine inserts a `late_wakeup` or
  `no_wakeup` alert, the plugin notifier pushes an `agentTurn` to
  `sessionKey: agent:elder-wakeup-agent:main`.

## Manual triggers

- "现在帮我检查一下 / check now" → `rule_eval`.
- "老人起床时间改一下 / change the baseline" → `state_query` action=`upsert_plan`.
