#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Run the functional pytest suite for industrial-edge-insights-time-series.
#
# Usage: run-functional-tests.sh <docker|helm> [gpu|security|stability|retention]
#
set -euo pipefail

MODE="${1:-}"
SUITE="${2:-default}"

usage() {
  echo "Usage: $0 <docker|helm> [gpu|security|stability|retention]" >&2
  exit 2
}

[ -n "$MODE" ] || usage

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
TESTS_DIR="$APP_ROOT/tests/functional"

[ -d "$TESTS_DIR" ] || { echo "FAIL: $TESTS_DIR not found" >&2; exit 1; }
cd "$TESTS_DIR"

if [ ! -d env ]; then
  echo "Creating virtualenv for functional tests..."
  python3 -m venv env
fi
# shellcheck disable=SC1091
source env/bin/activate
pip3 install -q -r ../requirements.txt

case "$MODE-$SUITE" in
  docker-default)
    pytest -v -s --html=docker_wind_turbine_report.html test_docker_deployment_wind_turbine.py
    ;;
  docker-retention)
    pytest -v -s --html=docker_influxdb_retention_wind_turbine_report.html test_docker_influxdb_retention.py
    ;;
  docker-stability)
    pytest -v -s --html=docker_stability_wind_turbine_report.html test_docker_deployment_stability.py
    ;;
  docker-gpu)
    pytest -v -s -m gpu --html=gpu_docker_report.html test_GPU_docker.py
    ;;
  helm-default)
    pytest -v -s --html=helm_wind_turbine_report.html test_helm_deployment_wind_turbine.py
    ;;
  helm-retention)
    pytest -v -s --html=helm_influxdb_retention_wind_turbine_report.html test_helm_influxdb_retention.py
    ;;
  helm-gpu)
    pytest -v -s -m gpu --html=gpu_helm_report.html test_GPU_helm.py
    ;;
  *-security)
    pytest -v -s --html=security_report.html test_docker_helm_deployment_security.py
    ;;
  *)
    usage
    ;;
esac
