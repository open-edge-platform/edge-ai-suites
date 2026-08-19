#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# One-time conversion of the NCLT sequence configured in env.sh into a
# standard ROS 2 bag (scripts/convert_nclt_to_bag.py), so run_nclt.sh can
# replay it with the standard `ros2 bag play` instead of re-parsing NCLT's
# raw binary/CSV files on every run. Safe to re-run: skipped if BAG_DIR
# already exists (pass FORCE_CONVERT=true to redo it).
#
# Usage: ./convert_nclt_to_bag.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

if [[ ! -d "${DATASET_DIR}" ]] || [[ -z "$(find "${DATASET_DIR}" -name velodyne_hits.bin 2>/dev/null)" ]]; then
  echo "NCLT dataset not found at ${DATASET_DIR}. Run ./fetch_nclt.sh first." >&2
  exit 1
fi

# ROS 2's setup.bash references internal ament/colcon trace variables that
# are never exported with a default, so it's incompatible with `set -u`;
# disable nounset just around sourcing it.
set +u
source "/opt/ros/${ROS_DISTRO}/setup.bash"
set -u

FORCE_ARGS=()
if [[ "${FORCE_CONVERT:-false}" == "true" ]]; then
  FORCE_ARGS+=(--force)
fi

echo "==> Converting NCLT ${NCLT_SEQUENCE} into ${BAG_DIR}"
python3 "${SCRIPT_DIR}/convert_nclt_to_bag.py" \
  --dataset-dir "${DATASET_DIR}" \
  --output-bag "${BAG_DIR}" \
  --storage-id "${BAG_STORAGE_ID}" \
  "${FORCE_ARGS[@]}"
