#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_DIR="${SCRIPT_DIR}"

get_local_ip() {
  if command -v ip >/dev/null 2>&1; then
    ip -4 addr show scope global | awk '/inet / {sub(/\/.*/, "", $2); if ($2 != "127.0.0.1") {print $2; exit}}'
    return
  fi

  if command -v hostname >/dev/null 2>&1; then
    hostname -I 2>/dev/null | awk '{print $1}'
    return
  fi
}

SERVER_HOST="${SERVER_HOST:-}"
if [ -z "${SERVER_HOST}" ]; then
  SERVER_HOST="$(get_local_ip)"
  echo "Detected local IP address: ${SERVER_HOST}"
else
  echo "Using SERVER_HOST from environment: ${SERVER_HOST}"
fi

if [ -z "${SERVER_HOST}" ]; then
  echo "Unable to detect SERVER_HOST automatically. Please export SERVER_HOST=<your-server-ip> first." >&2
  exit 1
fi

UI_PORT="${UI_PORT:-7000}"
STATS_API_PORT="${STATS_API_PORT:-8000}"
CHATBOT_WS_PORT="${CHATBOT_WS_PORT:-18789}"
AUTH_TOKEN="${AUTH_TOKEN:-}"

if [ -z "${AUTH_TOKEN}" ]; then
  echo "AUTH_TOKEN is not set. Please export AUTH_TOKEN=<your-auth-token> first." >&2
  exit 1
fi

export SERVER_HOST
export VITE_API_BASE_URL="/"
export VITE_CHATBOT_WS_PORT="${CHATBOT_WS_PORT}"
export VITE_CHATBOT_URL="ws://localhost:${CHATBOT_WS_PORT}/"
export VITE_AUTH_TOKEN="${AUTH_TOKEN}"
export VITE_DEV_STATS_API_TARGET="http://${SERVER_HOST}:${STATS_API_PORT}"

echo "UI URL: http://${SERVER_HOST}:${UI_PORT}"

cd "${UI_DIR}"
exec npm run dev -- --host 0.0.0.0 --port "${UI_PORT}"
