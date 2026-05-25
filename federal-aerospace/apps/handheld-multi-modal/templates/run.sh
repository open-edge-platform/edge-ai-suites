#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Convenience wrapper for the Federal Aerospace handheld multi-modal stack.
# vippet is included in this package; make deploy handles the full deployment.
#
# Usage: ./run.sh [up|down|logs]

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${HERE}/handheld-multi-modal"

action="${1:-up}"

case "${action}" in
  up)
    make -C "${APP_DIR}" deploy
    ;;
  down)
    make -C "${APP_DIR}" down
    ;;
  logs)
    docker compose -f "${APP_DIR}/docker-compose.yml" logs -f --tail=100
    ;;
  *)
    echo "usage: $0 [up|down|logs]" >&2
    exit 2
    ;;
esac
