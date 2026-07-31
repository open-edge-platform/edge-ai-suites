#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Silently start the SmartBuilding MCP server as a HOST process (Streamable-HTTP on
# :3100 + events webhook on :3101) — like OpenClaw, it runs on the host, not in a
# container. Backgrounded via nohup; pid + logs live under /tmp/smartbuilding-<uid>/.
#
#   scripts/mcp-server/start.sh                                # use data-dir config
#   scripts/mcp-server/start.sh <config-path> [monitors-path]  # import then start
#   scripts/mcp-server/stop.sh                                 # stop
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROMPTS_DIR="$REPO_DIR/demo/prompts"
DATA_DIR="${SMARTBUILDING_DATA_DIR:-$HOME/.mcp-smartbuilding}"
LOG_DIR="/tmp/smartbuilding-$(id -u)"
PID_FILE="$LOG_DIR/mcp-server.pid"
LOG_FILE="$LOG_DIR/mcp-server.log"
mkdir -p "$LOG_DIR"

command -v md5sum >/dev/null || { echo "md5sum not found in PATH" >&2; exit 1; }
mkdir -p "$DATA_DIR"
DATA_DIR="$(cd "$DATA_DIR" && pwd)"
CONFIG="$DATA_DIR/config.yaml"
MONITORS="$DATA_DIR/monitors.yaml"

# With no arguments, use the active files in the data directory. Explicit
# source paths are imported before startup (used by the demo launcher).
CONFIG_SOURCE="${1:-$CONFIG}"
MONITORS_SOURCE="${2:-}"
[[ "$CONFIG_SOURCE" != /* ]] && CONFIG_SOURCE="$REPO_DIR/$CONFIG_SOURCE"
[[ -n "$MONITORS_SOURCE" && "$MONITORS_SOURCE" != /* ]] && MONITORS_SOURCE="$REPO_DIR/$MONITORS_SOURCE"
[[ -f "$CONFIG_SOURCE" ]] || { echo "config file not found: $CONFIG_SOURCE (initialize it from config.yaml.example before starting)" >&2; exit 1; }
[[ -z "$MONITORS_SOURCE" || -f "$MONITORS_SOURCE" ]] || { echo "monitors file not found: $MONITORS_SOURCE" >&2; exit 1; }

# Already running?
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
  echo "mcp-server already running (pid $(cat "$PID_FILE")) — logs: $LOG_FILE"
  exit 0
fi
rm -f "$PID_FILE"

sync_config_file() {
  local source="$1"
  local target="$2"
  local backup

  [[ ! -L "$target" ]] || { echo "refusing to overwrite symbolic link: $target" >&2; return 1; }
  [[ ! -e "$target" || -f "$target" ]] || { echo "refusing to overwrite non-regular file: $target" >&2; return 1; }
  if [[ -e "$target" && "$source" -ef "$target" ]]; then
    return
  fi
  if [[ -f "$target" ]] && [[ "$(md5sum "$source" | awk '{print $1}')" == "$(md5sum "$target" | awk '{print $1}')" ]]; then
    return
  fi
  if [[ -f "$target" ]]; then
    backup="$target.$(date '+%Y%m%d-%H%M%S').bak"
    [[ ! -e "$backup" && ! -L "$backup" ]] || { echo "backup already exists: $backup" >&2; return 1; }
    cp -- "$target" "$backup"
    echo "backed up ${target} to ${backup}"
  fi
  cp -- "$source" "$target"
  echo "updated $target from $source"
}

sync_config_file "$CONFIG_SOURCE" "$CONFIG"
if [[ -n "$MONITORS_SOURCE" ]]; then
  sync_config_file "$MONITORS_SOURCE" "$MONITORS"
elif [[ -L "$MONITORS" ]]; then
  echo "refusing to initialize through symbolic link: $MONITORS" >&2
  exit 1
elif [[ ! -f "$MONITORS" ]]; then
  cat >"$MONITORS" <<'YAML'
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
monitors: {}
YAML
  echo "initialized empty monitor configuration at $MONITORS"
fi

# Fresh log per launch — truncate instead of appending so it doesn't grow unbounded.
: >"$LOG_FILE"

cd "$REPO_DIR"

# Install dependencies and build the workspace before using its YAML parser.
command -v node >/dev/null || { echo "node not found in PATH" >&2; exit 1; }
command -v npm >/dev/null || { echo "npm not found in PATH" >&2; exit 1; }
command -v curl >/dev/null || { echo "curl not found in PATH" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq not found in PATH" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg not found in PATH (required for RTSP live preview)" >&2; exit 1; }
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

echo "starting mcp-server (config: $CONFIG, monitors: $MONITORS)"
nohup node packages/mcp-server/dist/index.js --http --config "$CONFIG" --monitors "$MONITORS" >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

# Wait for the HTTP port to bind (or the process to die).
for _ in $(seq 1 40); do
  if ss -tln 2>/dev/null | grep -q ':3100 '; then
    echo "mcp-server up (pid $(cat "$PID_FILE"))"
    echo "  UI:     http://localhost:3100/"
    echo "  MCP:    http://localhost:3100/mcp"
    echo "  events: http://localhost:3101/events"
    echo "  logs:   $LOG_FILE"
    exit 0
  fi
  kill -0 "$(cat "$PID_FILE")" 2>/dev/null || { echo "mcp-server exited during startup — see $LOG_FILE"; rm -f "$PID_FILE"; exit 1; }
  sleep 0.3
done
echo "mcp-server started but :3100 not up yet — check $LOG_FILE"
