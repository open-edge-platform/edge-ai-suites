#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Run the functional pytest suite for industrial-edge-insights-multimodal.
#
# Usage: run-functional-tests.sh <docker|helm> [gpu|npu]
#
set -euo pipefail

MODE="${1:-}"
HW="${2:-cpu}"

usage() {
  echo "Usage: $0 <docker|helm> [gpu|npu]" >&2
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

case "$MODE-$HW" in
  docker-cpu)
    pytest -v -s --html=docker_multimodal_report.html test_docker_deployment_multimodal.py
    ;;
  docker-gpu)
    pytest -v -s -m gpu --html=gpu_docker_multimodal_report.html test_GPU_docker_multimodal.py
    ;;
  docker-npu)
    pytest -v -s --html=npu_docker_multimodal_report.html test_NPU_docker_multimodal.py
    ;;
  helm-cpu)
    pytest -v -s --html=helm_multimodal_report.html test_helm_deployment_multimodal.py
    ;;
  helm-gpu)
    pytest -v -s -m gpu --html=gpu_helm_multimodal_report.html test_GPU_helm_multimodal.py
    ;;
  helm-npu)
    pytest -v -s --html=npu_helm_multimodal_report.html test_NPU_helm_multimodal.py
    ;;
  *)
    usage
    ;;
esac
