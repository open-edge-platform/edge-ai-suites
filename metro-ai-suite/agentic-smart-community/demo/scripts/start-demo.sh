#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# One-shot demo launcher: push the bundled clips as RTSP streams, then start the
# MCP server with the demo bundle (demo/config.demo.yaml + demo/monitors.demo.yaml)
# so the three validated example monitors (fridge / child / elder) come up.
#
#   demo/scripts/start-demo.sh          # start streams + demo MCP server
#   demo/scripts/stop-demo.sh           # stop both
#
# For a clean, use-case-free server instead, use scripts/mcp-server/start.sh.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROMPTS_DIR="$REPO_DIR/demo/prompts"

# Service endpoints (must match demo/config.demo.yaml).
SUMMARY_URL="${SUMMARY_URL:-http://localhost:8192}"      # multilevel-video-understanding
ANALYTICS_URL="${ANALYTICS_URL:-http://localhost:8999}"  # videostream-analytics

command -v curl >/dev/null || { echo "curl not found in PATH" >&2; exit 1; }
command -v jq   >/dev/null || { echo "jq not found in PATH"   >&2; exit 1; }

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

# 1. Register demo tasks to multilevel-video-understanding (see ../prompts/curl_register_task.md).
#    Fetch the current task list once, then POST only the tasks that aren't registered yet.
echo "registering demo tasks…"
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

# 2. Push the demo RTSP streams (backgrounded + idempotent inside the script).
echo "starting demo RTSP streams…"
bash "$REPO_DIR/demo/videos/start-streams.sh"

# 3. Start the MCP server pointed at the demo bundle.
export MCP_CONFIG="$REPO_DIR/demo/config.demo.yaml"
export MCP_MONITORS="$REPO_DIR/demo/monitors.demo.yaml"
exec "$REPO_DIR/scripts/mcp-server/start.sh" "$@"
