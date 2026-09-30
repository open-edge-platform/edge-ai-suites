#!/usr/bin/env bash

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# deploy_remote.sh — copy infra/px4-sim/ to the FC machine and start it
set -euo pipefail

REMOTE_IP="${1:-}"
if [[ -z "$REMOTE_IP" ]]; then
  echo "Usage: $0 <FC_IP> [remote_user]"
  echo "  FC_IP   — IP address of the FC machine (e.g. 192.168.1.100)"
  exit 1
fi
REMOTE_USER="${2:-user}"
REMOTE_DIR="/home/${REMOTE_USER}/px4-sim"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)/px4-sim"

echo "================================================================"
echo "  Deploy PX4 + mavlink-router to ${REMOTE_USER}@${REMOTE_IP}"
echo "================================================================"
echo ""

read -rp "Run scp + ssh now? [y/N] " ans
[[ "${ans,,}" != "y" ]] && { echo "Aborted."; exit 0; }

echo ""
echo "[1/2] Copying infra/px4-sim/ to ${REMOTE_IP}:${REMOTE_DIR} ..."
# shellcheck disable=SC2029
ssh "${REMOTE_USER}@${REMOTE_IP}" "mkdir -p ${REMOTE_DIR}"
scp -r "${LOCAL_DIR}/." "${REMOTE_USER}@${REMOTE_IP}:${REMOTE_DIR}/"

echo "[2/2] Building and starting on remote..."
# Auto-detect the GPU card (card0 / card1 / etc.) on the remote machine
# shellcheck disable=SC2029
ssh "${REMOTE_USER}@${REMOTE_IP}" "
  set -euo pipefail
  cd '${REMOTE_DIR}'
  DETECTED_CARD=\$(ls /dev/dri/card* 2>/dev/null | head -1 | xargs -I{} basename {} 2>/dev/null || echo 'card0')
  echo \"Auto-detected GPU: /dev/dri/\$DETECTED_CARD\"
  GPU_CARD=\$DETECTED_CARD docker compose up -d --build
  docker compose ps
"

echo ""
echo "Done. mavlink-router is routing on ${REMOTE_IP}:14541"
echo "Start the stack: FC_IP=${REMOTE_IP} make up-ethernet"
