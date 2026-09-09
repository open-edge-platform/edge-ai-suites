#!/bin/bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# ensure_xpu_smi_bridge.sh — idempotent helper to (re)start the xpu-smi
# telemetry bridge and set perf_event_paranoid=0.
#
# Safe to call multiple times: does nothing if the bridge is already running.
# Called by setup.sh and by the analytics container's system_telemetry.py
# when it detects a stale xpu-smi.json.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TELEMETRY_DIR="$REPO_ROOT/generated/telemetry"
PID_FILE="$TELEMETRY_DIR/xpu-smi.pid"
LOG_FILE="$TELEMETRY_DIR/xpu-smi.log"
JSON_FILE="$TELEMETRY_DIR/xpu-smi.json"

_info()    { echo "[INFO] $*"; }
_warning() { echo "[WARNING] $*"; }
_success() { echo "[OK] $*"; }

# ── perf_event_paranoid ────────────────────────────────────────────────────────
# The i915 PMU hardware engine-busy counters are the only accurate GPU
# utilization source on xe-driver platforms (Arrow Lake, Meteor Lake).
# paranoid=0 allows process-level perf_event_open without CAP_PERFMON.
_ensure_perf_paranoid() {
    local current
    current=$(cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null || echo "unknown")
    if [ "$current" = "0" ]; then
        return 0
    fi
    if sudo -n sysctl -w kernel.perf_event_paranoid=0 >/dev/null 2>&1; then
        _info "Set kernel.perf_event_paranoid=0 for i915 PMU GPU telemetry"
    else
        _warning "Could not lower perf_event_paranoid (current=$current); GPU utilization via i915 PMU may be unavailable"
    fi
}

_ensure_rapl_read_access() {
    if [ ! -d /sys/class/powercap ]; then
        return 0
    fi
    if sudo -n sh -c '
        find /sys/class/powercap -path "*/intel-rapl:*/*" \( -name energy_uj -o -name max_energy_range_uj -o -name power_uw -o -name name \) -exec chmod o+r {} + 2>/dev/null || true
    ' >/dev/null 2>&1; then
        _info "Enabled read access for RAPL power telemetry"
    else
        _warning "Could not enable read access for RAPL power telemetry"
    fi
}

# ── bridge process ─────────────────────────────────────────────────────────────
_bridge_alive() {
    local pid
    [ -f "$PID_FILE" ] || return 1
    pid=$(cat "$PID_FILE" 2>/dev/null) || return 1
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null
}

_stop_bridge() {
    local pid
    [ -f "$PID_FILE" ] || return 0
    pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        for _ in 1 2 3 4 5; do
            kill -0 "$pid" 2>/dev/null || break
            sleep 1
        done
        kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
}

_start_bridge() {
    mkdir -p "$TELEMETRY_DIR"
    _stop_bridge

    nohup bash -lc '
        cd "$1"
        while true; do
            python3 scripts/xpu_smi_bridge.py --output "$2"
            sleep 1
        done
    ' _ "$REPO_ROOT" "$JSON_FILE" >>"$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"

    # Give it a moment to either succeed or crash immediately
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        _success "xpu-smi telemetry bridge running (pid $pid)"
    else
        _warning "xpu-smi telemetry bridge did not stay running — check $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# ── main ───────────────────────────────────────────────────────────────────────
if ! command -v xpu-smi >/dev/null 2>&1 && ! command -v turbostat >/dev/null 2>&1; then
    _warning "Neither xpu-smi nor turbostat is installed; host package telemetry unavailable"
    exit 0
fi

_ensure_perf_paranoid
_ensure_rapl_read_access

if _bridge_alive; then
    # Already running — nothing to do
    exit 0
fi

_info "xpu-smi telemetry bridge is not running; (re)starting..."
_start_bridge
