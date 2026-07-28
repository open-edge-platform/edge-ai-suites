#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Silently start the SmartBuilding MCP server as a HOST process (Streamable-HTTP on
# :3100 + events webhook on :3101) — like OpenClaw, it runs on the host, not in a
# container. Backgrounded via nohup; pid + logs live under /tmp/smartbuilding-<uid>/.
#
#   scripts/mcp-server/start.sh                        # start (idempotent)
#   MCP_CONFIG=... MCP_MONITORS=... start.sh           # override config/monitors paths
#   scripts/mcp-server/stop.sh                         # stop
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="/tmp/smartbuilding-$(id -u)"
PID_FILE="$LOG_DIR/mcp-server.pid"
LOG_FILE="$LOG_DIR/mcp-server.log"
mkdir -p "$LOG_DIR"

# Config: prefer a local config.yaml if present, else fall back to the tracked
# clean example. Writing to config.yaml (not the .example) lets agent-added use
# cases persist on the host while the .example stays a pristine, use-case-free
# reference.
CONFIG="${MCP_CONFIG:-}"
[[ -z "$CONFIG" ]] && { CONFIG="$REPO_DIR/config.yaml"; [[ -f "$CONFIG" ]] || CONFIG="$REPO_DIR/config.yaml.example"; }

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

# Build the workspace once if the compiled entrypoint is missing.
echo "building workspace (first run) — see $LOG_FILE"
{ npm install && npm run build; } >>"$LOG_FILE" 2>&1

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
