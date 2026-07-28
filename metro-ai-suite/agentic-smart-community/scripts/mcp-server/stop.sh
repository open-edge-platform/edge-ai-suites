#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Stop (pause) the host MCP server started by scripts/mcp-server/start.sh.
set -euo pipefail

LOG_DIR="/tmp/smartbuilding-$(id -u)"
PID_FILE="$LOG_DIR/mcp-server.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "no pidfile at $PID_FILE — mcp-server not running?"
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
  kill "$PID" 2>/dev/null || true
  for _ in $(seq 1 15); do kill -0 "$PID" 2>/dev/null || break; sleep 0.3; done
  kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null || true
  echo "stopped mcp-server (pid $PID)"
else
  echo "mcp-server not running (stale pidfile)"
fi
rm -f "$PID_FILE"
