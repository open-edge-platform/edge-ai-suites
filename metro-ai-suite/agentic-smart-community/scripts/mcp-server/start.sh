#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Silently start the SmartBuilding MCP server as a HOST process (Streamable-HTTP on
# :3100 + events webhook on :3101) — like OpenClaw, it runs on the host, not in a
# container. Backgrounded via nohup; pid + logs live under /tmp/smartbuilding-<uid>/.
#
#   scripts/mcp-server/start.sh [config-path]           # start (idempotent)
#   MCP_MONITORS=... start.sh [config-path]             # override monitors path
#   scripts/mcp-server/stop.sh                         # stop
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROMPTS_DIR="$REPO_DIR/demo/prompts"
LOG_DIR="/tmp/smartbuilding-$(id -u)"
PID_FILE="$LOG_DIR/mcp-server.pid"
LOG_FILE="$LOG_DIR/mcp-server.log"
mkdir -p "$LOG_DIR"

# The tracked reference configuration is the default. Pass a path explicitly
# when starting with a customized configuration.
CONFIG="${1:-config.yaml.example}"
[[ "$CONFIG" != /* ]] && CONFIG="$REPO_DIR/$CONFIG"
[[ -f "$CONFIG" ]] || { echo "config file not found: $CONFIG" >&2; exit 1; }

# Monitors are OPTIONAL. The clean core ships none — omit --monitors so the
# server boots with zero cameras (add them at runtime via monitor_ctl /
# monitors_compose). Set MCP_MONITORS (or drop a monitors.yaml at the repo root)
# to auto-register a set at boot. The demo bundle is wired via start-demo.sh.
MONITORS="${MCP_MONITORS:-}"
[[ -z "$MONITORS" && -f "$REPO_DIR/monitors.yaml" ]] && MONITORS="$REPO_DIR/monitors.yaml"

# Already running?
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
  echo "mcp-server already running (pid $(cat "$PID_FILE")) — logs: $LOG_FILE"
  exit 0
fi
rm -f "$PID_FILE"

# Fresh log per launch — truncate instead of appending so it doesn't grow unbounded.
: >"$LOG_FILE"

cd "$REPO_DIR"

# Install dependencies and build the workspace before using its YAML parser.
command -v node >/dev/null || { echo "node not found in PATH" >&2; exit 1; }
command -v npm >/dev/null || { echo "npm not found in PATH" >&2; exit 1; }
command -v curl >/dev/null || { echo "curl not found in PATH" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq not found in PATH" >&2; exit 1; }
echo "building workspace — see $LOG_FILE"
{ npm install && npm run build; } >>"$LOG_FILE" 2>&1

# Register bundled use cases with multilevel-video-understanding before the
# MCP server loads their declarations from config.yaml.
SUMMARY_URL="$(node --input-type=module -e '
  import { readFileSync } from "node:fs";
  import { parse } from "yaml";
  const config = parse(readFileSync(process.argv[1], "utf8"));
  const value = config?.summary_service?.url ?? "http://localhost:8192";
  const url = new URL(value);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("summary_service.url must use http or https");
  }
  process.stdout.write(value.replace(/\/+$/, ""));
' "$CONFIG")"
echo "registering bundled use cases…"
existing="$(curl -fsS "$SUMMARY_URL/v1/tasks" | jq -r '.tasks[].name')" \
  || { echo "failed to list tasks at $SUMMARY_URL/v1/tasks" >&2; exit 1; }
for task in fridge_monitor child_safety_monitor elder_wakeup_monitor; do
  prompt_file="$PROMPTS_DIR/$task.txt"
  [[ -f "$prompt_file" ]] || { echo "missing prompt file: $prompt_file" >&2; exit 1; }
  if grep -qxF "$task" <<<"$existing"; then
    echo "  = $task (already registered — skipping)"
    continue
  fi
  echo "  → $task"
  jq -Rs --arg name "$task" '{task_name: $name, mode: "full", content: {text: .}}' "$prompt_file" \
    | curl -fsS "$SUMMARY_URL/v1/tasks" -H "Content-Type: application/json" --data-binary @- >/dev/null \
    || { echo "failed to register $task" >&2; exit 1; }
done

# Build node argv — only pass --monitors when a monitors file was resolved.
ARGS=(--http --config "$CONFIG")
[[ -n "$MONITORS" ]] && ARGS+=(--monitors "$MONITORS")

echo "starting mcp-server (config: ${CONFIG#"$REPO_DIR"/}, monitors: ${MONITORS:+${MONITORS#"$REPO_DIR"/}}${MONITORS:-<none>})"
nohup node packages/mcp-server/dist/index.js "${ARGS[@]}" >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

# Wait for the HTTP port to bind (or the process to die).
for _ in $(seq 1 40); do
  if ss -tln 2>/dev/null | grep -q ':3100 '; then
    echo "mcp-server up (pid $(cat "$PID_FILE"))"
    echo "  MCP:    http://localhost:3100/mcp"
    echo "  events: http://localhost:3101/events"
    echo "  logs:   $LOG_FILE"
    exit 0
  fi
  kill -0 "$(cat "$PID_FILE")" 2>/dev/null || { echo "mcp-server exited during startup — see $LOG_FILE"; rm -f "$PID_FILE"; exit 1; }
  sleep 0.3
done
echo "mcp-server started but :3100 not up yet — check $LOG_FILE"
