#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
BUILD_DIR="${SCRIPT_DIR}/build"
JOBS=$(command -v nproc >/dev/null 2>&1 && nproc || echo 8)

set +u
if [[ "${SETVARS_COMPLETED:-0}" != "1" ]]; then
	source /opt/intel/oneapi/setvars.sh
fi
source /opt/intel/openvino/setupvars.sh
set -u
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"
cmake ..
cmake --build . --parallel "${JOBS}"