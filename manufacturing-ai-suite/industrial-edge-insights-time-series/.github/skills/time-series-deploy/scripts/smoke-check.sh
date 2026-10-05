#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Smoke-check the Industrial Edge Insights - Time Series sample app.
#
# Usage: smoke-check.sh <docker|helm> [namespace]
#
set -euo pipefail

MODE="${1:-}"
NAMESPACE="${2:-ts-sample-app}"
if [ -z "${GRAFANA_PORT:-}" ] && [ -f .env ]; then
  GRAFANA_PORT="$(sed -n 's/^GRAFANA_PORT=//p' .env | tail -n 1)"
fi
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
MAX_RETRIES=30
SLEEP_SECS=5

usage() {
  echo "Usage: $0 <docker|helm> [namespace]" >&2
  exit 2
}

[ -n "$MODE" ] || usage

wait_for_url() {
  local url="$1"
  local i=0
  until [ "$(curl -sk -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || echo 000)" != "000" ]; do
    i=$((i + 1))
    if [ "$i" -ge "$MAX_RETRIES" ]; then
      echo "FAIL: timed out waiting for $url after $((MAX_RETRIES * SLEEP_SECS))s" >&2
      return 1
    fi
    echo "  not reachable yet ($i/$MAX_RETRIES), retrying in ${SLEEP_SECS}s..."
    sleep "$SLEEP_SECS"
  done
  echo "OK: $url is reachable"
}

case "$MODE" in
  docker)
    echo "== Docker Compose smoke check =="
    if ! docker info >/dev/null 2>&1; then
      echo "FAIL: Docker daemon not reachable" >&2
      exit 1
    fi
    echo "-- Container status --"
    make status || true
    echo "-- Endpoint check --"
    wait_for_url "https://localhost:${GRAFANA_PORT}/"
    ;;
  helm)
    echo "== Helm smoke check (namespace: $NAMESPACE) =="
    if ! kubectl cluster-info >/dev/null 2>&1; then
      echo "FAIL: Kubernetes cluster not reachable" >&2
      exit 1
    fi
    echo "-- Pod status --"
    kubectl get pods -n "$NAMESPACE" -o wide
    echo "-- Waiting for all pods to be Ready --"
    if ! kubectl wait --for=condition=Ready pod --all -n "$NAMESPACE" --timeout=180s; then
      echo "FAIL: not all pods reached Ready in time" >&2
      kubectl get pods -n "$NAMESPACE"
      exit 1
    fi
    echo "-- Endpoint check --"
    wait_for_url "https://localhost:30001/"
    ;;
  *)
    usage
    ;;
esac

echo "Smoke check passed for mode=$MODE"
