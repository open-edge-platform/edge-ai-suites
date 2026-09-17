#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Container entrypoint for the Smart Community MCP server. The container IS the
# process (no nohup / pidfile / port-poll scaffolding): we exec node in the
# foreground and let Docker manage its lifecycle.
#
#   1. Initialise $SMART_COMMUNITY_DATA_DIR/{config,monitors}.yaml from the bundled
#      templates when missing (the bind-mounted data dir usually already has them).
#   2. Register the bundled video-summary use cases with multilevel-video-understanding.
#   3. exec the MCP server in the foreground.
set -euo pipefail

DATA_DIR="${SMART_COMMUNITY_DATA_DIR:-$HOME/.mcp-smart-community}"
mkdir -p "$DATA_DIR"
DATA_DIR="$(cd "$DATA_DIR" && pwd)"
CONFIG="$DATA_DIR/config.yaml"
MONITORS="$DATA_DIR/monitors.yaml"
PROMPTS_DIR="/app/demo/prompts"

# 1. Seed config/monitors from the image templates only when absent. Compose
#    (or the demo prep script) usually populates the data dir beforehand.
if [[ ! -f "$CONFIG" ]]; then
  cp -- /app/config.yaml.example "$CONFIG"
  echo "initialized $CONFIG from bundled config.yaml.example"
fi
if [[ ! -f "$MONITORS" ]]; then
  cp -- /app/monitors.yaml.example "$MONITORS"
  echo "initialized $MONITORS from bundled monitors.yaml.example"
fi

# 2. Register bundled use cases with multilevel-video-understanding before the MCP
#    server loads their declarations from config.yaml.
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

register_use_cases() {
  local existing
  existing="$(curl -fsS --max-time 5 "$SUMMARY_URL/v1/tasks" | jq -r '.tasks[].name')" || return 1
  local task prompt_file
  for task in fridge_monitor child_safety_monitor elder_wakeup_monitor; do
    prompt_file="$PROMPTS_DIR/$task.txt"
    [[ -f "$prompt_file" ]] || { echo "missing prompt file: $prompt_file" >&2; return 1; }
    if grep -qxF "$task" <<<"$existing"; then
      echo "  = $task (already registered — skipping)"
      continue
    fi
    echo "  → $task"
    jq -Rs --arg name "$task" '{task_name: $name, mode: "full", content: {text: .}}' "$prompt_file" \
      | curl -fsS "$SUMMARY_URL/v1/tasks" -H "Content-Type: application/json" --data-binary @- >/dev/null \
      || { echo "failed to register $task" >&2; return 1; }
  done
}

echo "registering bundled use cases at $SUMMARY_URL…"
for attempt in $(seq 1 10); do
  if register_use_cases; then
    break
  fi
  echo "  use-case registration not ready (attempt $attempt/10) — retrying in 3s…" >&2
  sleep 3
done

# 3. Run the MCP server in the foreground so the container manages its lifecycle.
echo "starting mcp-server (config: $CONFIG, monitors: $MONITORS)"
cd /app
exec node packages/mcp-server/dist/index.js --http --config "$CONFIG" --monitors "$MONITORS"
