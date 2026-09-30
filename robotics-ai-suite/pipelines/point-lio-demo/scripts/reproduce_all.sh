#!/usr/bin/env bash
# One-command reproduce: apply Intel patches, build, fetch the UrbanLoco
# sequence configured in env.sh, convert it to a ROS 2 bag (once), set up
# the CycloneDDS+iceoryx shared-memory transport (unless USE_DDS_SHM=false),
# run it, and evaluate RMSE against the documented baseline. Requires
# scripts/install_deps.sh to have been run at least once beforehand
# (one-time host setup, needs sudo).
#
# Usage: ./reproduce_all.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/apply_patches.sh"
"${SCRIPT_DIR}/build.sh"
"${SCRIPT_DIR}/fetch_ulhk.sh"
"${SCRIPT_DIR}/convert_ulhk_to_bag.sh"
"${SCRIPT_DIR}/setup_dds_shm.sh" start
"${SCRIPT_DIR}/run_ulhk.sh"
"${SCRIPT_DIR}/evaluate_rmse.sh"
