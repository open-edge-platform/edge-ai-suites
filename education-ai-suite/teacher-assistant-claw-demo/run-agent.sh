#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# run-agent.sh
# Single entry point for Step 4: waits for OVMS to load the model,
# then launches the OpenClaw chat agent.
#
# If the model is not ready in time (or OVMS stopped), it prints exactly
# what to check and rerun, and exits WITHOUT starting chat.

set -euo pipefail

PORT=8000
MODEL_ID="Qwen3-8B-int4-ov"
CONTAINER_NAME="teacher-assistant-ovms"
TIMEOUT_SECONDS=600
INTERVAL_SECONDS=5

model_ready() {
    curl -s "http://localhost:${PORT}/v3/models" | grep -q "${MODEL_ID}"
}

recovery_hint() {
    echo ""
    echo "Check the logs to find the cause:"
    echo "  docker logs --tail 200 ${CONTAINER_NAME}"
    echo "Then restart OVMS (Step 2) and run this script again:"
    echo "  ./setup-ovms.sh"
    echo "  ./run-agent.sh"
}

echo "Waiting for OVMS to load the model (up to $((TIMEOUT_SECONDS / 60)) minutes)..."

elapsed=0
while ! model_ready; do
    # Fail fast if the OVMS container is no longer running.
    if ! docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
        echo ""
        echo "ERROR: OVMS container '${CONTAINER_NAME}' is not running — model setup did not complete."
        recovery_hint
        exit 1
    fi

    if [ "${elapsed}" -ge "${TIMEOUT_SECONDS}" ]; then
        echo ""
        echo "ERROR: Model not ready after $((TIMEOUT_SECONDS / 60)) minutes."
        recovery_hint
        exit 1
    fi

    echo "  still loading... (${elapsed}s / ${TIMEOUT_SECONDS}s)"
    sleep "${INTERVAL_SECONDS}"
    elapsed=$((elapsed + INTERVAL_SECONDS))
done

echo "OVMS model is ready. Starting OpenClaw chat..."
exec openclaw chat
