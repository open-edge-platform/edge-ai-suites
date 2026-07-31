#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# One-shot demo launcher: push user-provided clips as RTSP streams, then start
# the MCP server with the matching subset of the demo monitor bundle.
#
#   demo/scripts/start-demo.sh          # start streams + demo MCP server
#   demo/scripts/stop-demo.sh           # stop both
#
# For a clean, use-case-free server instead, use scripts/mcp-server/start.sh.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROMPTS_DIR="$REPO_DIR/demo/prompts"
DATA_DIR="${SMARTBUILDING_DATA_DIR:-$HOME/.mcp-smartbuilding}"

# Service endpoints (must match config.yaml.example).
SUMMARY_URL="${SUMMARY_URL:-http://localhost:8192}"      # multilevel-video-understanding
ANALYTICS_URL="${ANALYTICS_URL:-http://localhost:8999}"  # videostream-analytics

command -v curl >/dev/null || { echo "curl not found in PATH" >&2; exit 1; }
command -v jq   >/dev/null || { echo "jq not found in PATH"   >&2; exit 1; }
command -v md5sum >/dev/null || { echo "md5sum not found in PATH" >&2; exit 1; }

# 0. Pre-requisites must be healthy before we register tasks or process clips.
#    Note the two services expose DIFFERENT health paths.
echo "checking prerequisites…"

# multilevel-video-understanding — GET /v1/health
curl -fsS --max-time 5 "$SUMMARY_URL/v1/health" >/dev/null 2>&1 \
  || { echo "prerequisite not healthy: multilevel-video-understanding — expected GET $SUMMARY_URL/v1/health to succeed (override with SUMMARY_URL)." >&2; exit 1; }
echo "  ok: multilevel-video-understanding ($SUMMARY_URL)"

# videostream-analytics — GET /health
curl -fsS --max-time 5 "$ANALYTICS_URL/health" >/dev/null 2>&1 \
  || { echo "prerequisite not healthy: videostream-analytics — expected GET $ANALYTICS_URL/health to succeed (override with ANALYTICS_URL)." >&2; exit 1; }
echo "  ok: videostream-analytics ($ANALYTICS_URL)"

# 1. Restore any bundled task that was removed while the MCP server is already
#    running. The main launcher performs the same registration for new servers.
echo "checking bundled use cases…"
existing="$(curl -fsS "$SUMMARY_URL/v1/tasks" | jq -r '.tasks[].name')" \
  || { echo "failed to list tasks at $SUMMARY_URL/v1/tasks" >&2; exit 1; }
for task in fridge_monitor child_safety_monitor elder_wakeup_monitor; do
  prompt_file="$PROMPTS_DIR/$task.txt"
  [[ -f "$prompt_file" ]] || { echo "missing prompt file: $prompt_file" >&2; exit 1; }
  if grep -qxF "$task" <<<"$existing"; then
    echo "  = $task (already registered)"
    continue
  fi
  echo "  → restoring $task"
  jq -Rs --arg name "$task" '{task_name: $name, mode: "full", content: {text: .}}' "$prompt_file" \
    | curl -fsS "$SUMMARY_URL/v1/tasks" -H "Content-Type: application/json" --data-binary @- >/dev/null \
    || { echo "failed to register $task" >&2; exit 1; }
done

# 2. Push the demo RTSP streams (backgrounded + idempotent inside the script).
echo "starting demo RTSP streams…"
bash "$REPO_DIR/demo/videos/start-streams.sh"

# 3. Generate a monitor bundle matching only the streams that started.
ACTIVE_STREAMS_FILE="$REPO_DIR/demo/videos/.run/active-streams.txt"
FILTERED_MONITORS="$(mktemp)"
trap 'rm -f "$FILTERED_MONITORS"' EXIT

"$REPO_DIR/demo/videos/.venv/bin/python" - \
  "$REPO_DIR/demo/monitors.demo.yaml" \
  "$ACTIVE_STREAMS_FILE" \
  "$FILTERED_MONITORS" <<'PY'
import sys

import yaml

monitors_path, active_path, output_path = sys.argv[1:]
with open(active_path, encoding="utf-8") as active_file:
  active_streams = {line.strip() for line in active_file if line.strip()}
with open(monitors_path, encoding="utf-8") as monitors_file:
  monitors_config = yaml.safe_load(monitors_file) or {}

monitors = monitors_config.get("monitors") or {}
monitors_config["monitors"] = {}
for monitor_id, monitor in monitors.items():
  if monitor_id not in active_streams:
    continue
  monitor = dict(monitor)
  monitor["enabled"] = True
  monitors_config["monitors"][monitor_id] = monitor
with open(output_path, "w", encoding="utf-8") as output_file:
  yaml.safe_dump(monitors_config, output_file, sort_keys=False)

print(f"  registering {len(monitors_config['monitors'])} monitor(s) for active streams")
PY

# 4. Persist the demo config and active monitor subset before starting the server.
mkdir -p "$DATA_DIR"
DATA_DIR="$(cd "$DATA_DIR" && pwd)"
ACTIVE_CONFIG="$DATA_DIR/config.yaml"
ACTIVE_MONITORS="$DATA_DIR/monitors.yaml"

persist_demo_config() {
  local source="$1"
  local target="$2"
  local backup

  [[ ! -L "$target" ]] || { echo "refusing to overwrite symbolic link: $target" >&2; return 1; }
  [[ ! -e "$target" || -f "$target" ]] || { echo "refusing to overwrite non-regular file: $target" >&2; return 1; }
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

persist_demo_config "$REPO_DIR/demo/config.demo.yaml" "$ACTIVE_CONFIG"
persist_demo_config "$FILTERED_MONITORS" "$ACTIVE_MONITORS"
rm -f "$FILTERED_MONITORS"
trap - EXIT

exec "$REPO_DIR/scripts/mcp-server/start.sh" "$ACTIVE_CONFIG" "$ACTIVE_MONITORS"
