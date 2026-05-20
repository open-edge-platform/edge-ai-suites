#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Bring up (or tear down) the Federal Aerospace blueprint and the vippet stack.
#
# Usage: ./run.sh [up|down|logs]

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLUEPRINT_COMPOSE="${HERE}/handheld-multi-modal/docker-compose.yml"
VIPPET_COMPOSE="${HERE}/vippet/compose.yml"

action="${1:-up}"

require_file() {
  if [[ ! -f "$1" ]]; then
    echo "error: required compose file not found: $1" >&2
    exit 1
  fi
}

require_file "${BLUEPRINT_COMPOSE}"
require_file "${VIPPET_COMPOSE}"

case "${action}" in
  up)
    docker compose -f "${BLUEPRINT_COMPOSE}" up -d
    docker compose -f "${VIPPET_COMPOSE}" up -d
    ;;
  down)
    docker compose -f "${VIPPET_COMPOSE}" down || true
    docker compose -f "${BLUEPRINT_COMPOSE}" down || true
    ;;
  logs)
    docker compose -f "${BLUEPRINT_COMPOSE}" logs -f --tail=100 &
    BP_PID=$!
    docker compose -f "${VIPPET_COMPOSE}" logs -f --tail=100 &
    VP_PID=$!
    trap 'kill ${BP_PID} ${VP_PID} 2>/dev/null || true' EXIT
    wait
    ;;
  *)
    echo "usage: $0 [up|down|logs]" >&2
    exit 2
    ;;
esac
