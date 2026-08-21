#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# One-shot demo launcher: push user-provided clips as RTSP streams, write the demo
# config + the matching subset of the monitor bundle into the data dir, then bring
# the whole stack up (reusing an already-warm model serving). The MCP server now
# runs as a container in docker/compose.yaml, so `setup_docker.sh --light` starts
# it alongside multilevel-video-understanding + videostream-analytics. The bundled
# use cases are registered by the MCP container entrypoint once it is healthy.
#
#   demo/quick-start/start-demo.sh      # streams + demo config, then start the stack
#   demo/quick-start/stop-demo.sh       # stop streams + app tier (vllm stays warm)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="${SMART_COMMUNITY_DATA_DIR:-$HOME/.mcp-smart-community}"

command -v md5sum >/dev/null || { echo "md5sum not found in PATH" >&2; exit 1; }

# 1. Push the demo RTSP streams (backgrounded + idempotent inside the script).
echo "starting demo RTSP streams…"
bash "$REPO_DIR/demo/videos/start-streams.sh"

# 2. Generate a monitor bundle matching only the streams that started.
ACTIVE_STREAMS_FILE="$REPO_DIR/demo/videos/.run/active-streams.txt"
FILTERED_MONITORS="$(mktemp)"
trap 'rm -f "$FILTERED_MONITORS"' EXIT

"$REPO_DIR/demo/videos/.venv/bin/python" - \
  "$SCRIPT_DIR/monitors.demo.yaml" \
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

print(f"  prepared {len(monitors_config['monitors'])} monitor(s) for active streams")
PY

# 3. Persist the demo config and active monitor subset into the data dir. The MCP
#    container reads these at startup (identity bind mount, same absolute path).
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

persist_demo_config "$SCRIPT_DIR/config.demo.yaml" "$ACTIVE_CONFIG"
persist_demo_config "$FILTERED_MONITORS" "$ACTIVE_MONITORS"
rm -f "$FILTERED_MONITORS"
trap - EXIT

# 4. Bring up the stack, reusing an already-warm vllm-ipex-serving. If the app tier
#    is already running, bounce it first (--light-down then --light) so the MCP
#    server restarts and reloads the demo config written above. --light-down stops
#    only the app tier (mcp + multilevel + videostream-analytics) and leaves
#    vllm-ipex-serving running, so its 3-20 min recompile is never repaid.
# shellcheck disable=SC1091
source "$REPO_DIR/docker/set_env.sh"
if [ -n "$(docker compose -f "$REPO_DIR/docker/compose.yaml" ps -q \
    smart-community-mcp-server multilevel-video-understanding videostream-analytics 2>/dev/null)" ]; then
  echo "app tier already running — bouncing it (--light-down) to reload the demo config…"
  bash "$REPO_DIR/setup_docker.sh" --light-down
fi
echo "starting the stack (setup_docker.sh --light)…"
bash "$REPO_DIR/setup_docker.sh" --light
