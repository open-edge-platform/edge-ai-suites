#!/bin/bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

info()    { echo "[INFO] $1"; }
success() { echo "[OK] $1"; }
warning() { echo "[WARNING] $1"; }

XPU_SMI_BRIDGE_PID_FILE="generated/telemetry/xpu-smi.pid"

stop_xpu_smi_bridge() {
    local pid
    if [ ! -f "$XPU_SMI_BRIDGE_PID_FILE" ]; then
        return 0
    fi

    pid=$(cat "$XPU_SMI_BRIDGE_PID_FILE" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        for _ in 1 2 3 4 5; do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi
    rm -f "$XPU_SMI_BRIDGE_PID_FILE"
}

echo "Smart Building Digital Twin - Cleanup"
echo "------------------------------------------------"
echo ""

# Stop host telemetry bridge
info "Stopping host xpu-smi telemetry bridge..."
stop_xpu_smi_bridge
success "Host telemetry bridge stopped"

# Stop and remove all containers
info "Stopping services..."
docker compose down --remove-orphans 2>/dev/null || true
success "Services stopped"

# Remove Docker volumes
info "Removing Docker volumes..."
docker volume rm -f \
    scenescape_vol-media \
    scenescape_vol-db \
    scenescape_vol-migrations \
    scenescape_vol-datasets \
    scenescape_vol-netvlad-models \
    scenescape_vol-dlstreamer-cache \
    2>/dev/null || true
success "Volumes removed"

# Remove generated files
info "Removing generated files..."
rm -rf certs/ generated/ .env config/resolved-uuids.json
success "Generated files removed"

echo ""
echo "Cleanup complete. Run ./setup.sh to redeploy."
