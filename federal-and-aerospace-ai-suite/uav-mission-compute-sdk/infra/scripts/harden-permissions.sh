#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Git only tracks executable/non-executable (755/644) — it cannot store the
# tighter modes below, so this script must be re-run after every fresh clone
# (wired into `make init`) to actually enforce them on disk.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# Scripts: owner rwx, group can read+execute, others get nothing.
chmod 750 \
    infra/px4-sim/start_px4.sh \
    infra/px4-sim/start_px4_multicam.sh \
    infra/scripts/deploy_remote.sh \
    infra/scripts/test_api.sh \
    mcp-server/setup.sh \
    sample-apps/edge-ai-showcase/run-local.sh \
    sample-apps/helpers/vision-processor/entrypoint.sh

# Secrets: owner read/write only, no execute, no group/other access.
[ -f .env ] && chmod 600 .env
chmod 600 .env.example

# Simulation world/model assets: owner read/write, group read-only, no other access.
chmod 640 \
    infra/px4-sim/worlds/detection_zone.sdf \
    infra/px4-sim/worlds/baylands_multicam.sdf \
    infra/px4-sim/worlds/baylands_detection.sdf \
    infra/px4-sim/models/mono_cam/model.sdf

echo "Permissions hardened: *.sh -> 750, .env* -> 600, sim worlds/models -> 640"
