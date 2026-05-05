#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
#
# grafana-monitor.sh — Start the Prometheus exporter and run monitor_stack.py
#                      concurrently, then clean up on exit.
#
# Usage:
#   ./grafana-monitor.sh [OPTIONS]
#
# Options:
#   --remote-ip IP          Remote host to monitor (required)
#   --remote-user USER      SSH user on remote host (default: ubuntu)
#   --duration SECS         Stop monitoring after N seconds (default: until Ctrl-C)
#   --node NAME             Narrow graph discovery to one node name substring
#   --interval SECS         Sampling interval in seconds (default: 1)
#   --algorithm NAME        Group this session under monitoring_sessions/<name>/
#   --domain-id ID          Override ROS_DOMAIN_ID
#   --pid-only              PID-level monitoring only (no thread details)
#   --gpu                   Enable Intel GPU metrics collection
#   --npu                   Enable Intel NPU metrics collection
#   --port PORT             Prometheus exporter port (default: 9092)
#   --sessions-dir DIR      Sessions directory (default: monitoring_sessions)
#   --repeat N              Run N monitoring sessions back-to-back (default: 1)
#   --pause SECS            Pause between repeat runs (default: 5)
#   -h, --help              Show this help and exit
#
# Examples:
#   ./grafana-monitor.sh --remote-ip 192.168.1.100
#   ./grafana-monitor.sh --remote-ip 192.168.1.100 --duration 120 --gpu
#   ./grafana-monitor.sh --remote-ip 192.168.1.100 --repeat 5 --pause 10
#   ./grafana-monitor.sh --remote-ip 192.168.1.100 --pid-only --algorithm slam

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
REMOTE_IP=""
REMOTE_USER="ubuntu"
DURATION=""
NODE=""
INTERVAL=""
ALGORITHM=""
DOMAIN_ID=""
PID_ONLY=0
GPU=0
NPU=0
PORT=9092
SESSIONS_DIR="monitoring_sessions"
REPEAT=1
PAUSE=5

# ── Argument parsing ──────────────────────────────────────────────────────────
usage() {
    sed -n '/^# Usage:/,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \?//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --remote-ip)    REMOTE_IP="$2";    shift 2 ;;
        --remote-user)  REMOTE_USER="$2";  shift 2 ;;
        --duration)     DURATION="$2";     shift 2 ;;
        --node)         NODE="$2";         shift 2 ;;
        --interval)     INTERVAL="$2";     shift 2 ;;
        --algorithm)    ALGORITHM="$2";    shift 2 ;;
        --domain-id)    DOMAIN_ID="$2";    shift 2 ;;
        --pid-only)     PID_ONLY=1;        shift ;;
        --gpu)          GPU=1;             shift ;;
        --npu)          NPU=1;             shift ;;
        --port)         PORT="$2";         shift 2 ;;
        --sessions-dir) SESSIONS_DIR="$2"; shift 2 ;;
        --repeat)       REPEAT="$2";       shift 2 ;;
        --pause)        PAUSE="$2";        shift 2 ;;
        -h|--help)      usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$REMOTE_IP" ]]; then
    echo "Error: --remote-ip is required." >&2
    echo "Run: $0 --help" >&2
    exit 1
fi

# ── Build monitor_stack.py argument list ─────────────────────────────────────
MONITOR_ARGS=(
    --remote-ip "$REMOTE_IP"
    --remote-user "$REMOTE_USER"
)
[[ -n "$DURATION"   ]] && MONITOR_ARGS+=(--duration   "$DURATION")
[[ -n "$NODE"       ]] && MONITOR_ARGS+=(--node        "$NODE")
[[ -n "$INTERVAL"   ]] && MONITOR_ARGS+=(--interval    "$INTERVAL")
[[ -n "$ALGORITHM"  ]] && MONITOR_ARGS+=(--algorithm   "$ALGORITHM")
[[ -n "$DOMAIN_ID"  ]] && MONITOR_ARGS+=(--ros-domain-id "$DOMAIN_ID")
[[ "$PID_ONLY" -eq 1 ]] && MONITOR_ARGS+=(--pid-only)
[[ "$GPU"      -eq 1 ]] && MONITOR_ARGS+=(--gpu)
[[ "$NPU"      -eq 1 ]] && MONITOR_ARGS+=(--npu)

EXPORTER_PID=0

_stop() {
    echo ""
    echo "Stopping exporter (PID $EXPORTER_PID)..."
    kill -- -"$EXPORTER_PID" 2>/dev/null || kill "$EXPORTER_PID" 2>/dev/null || true
    fuser -k "${PORT}/tcp" 2>/dev/null || true
    echo "Done."
}
trap _stop INT TERM

# ── Start exporter ────────────────────────────────────────────────────────────
fuser -k "${PORT}/tcp" 2>/dev/null || true
sleep 0.3

uv run python src/prometheus_exporter.py \
    --mode live \
    --sessions-dir "$SESSIONS_DIR" \
    --port "$PORT" \
    > /tmp/grafana-exporter.log 2>&1 &
EXPORTER_PID=$!

echo "Exporter started (PID $EXPORTER_PID, logs: /tmp/grafana-exporter.log)"
echo "  Metrics : http://localhost:${PORT}/metrics"
echo "  Grafana : http://localhost:30000"
echo ""

# ── Run loop ──────────────────────────────────────────────────────────────────
echo "Running $REPEAT monitoring session(s) (pause=${PAUSE}s between runs)"
echo "  Remote: ${REMOTE_USER}@${REMOTE_IP}"
echo ""

for i in $(seq 1 "$REPEAT"); do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Run $i / $REPEAT"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    uv run python src/monitor_stack.py "${MONITOR_ARGS[@]}"
    SESSION_DIR=$(find "${SESSIONS_DIR}" -maxdepth 2 -type d -name '[0-9]*' 2>/dev/null \
                 | sort -r | head -1)
    echo "  Session saved: $SESSION_DIR"
    if [[ $i -lt $REPEAT ]]; then
        echo "  Pausing ${PAUSE}s before next run..."
        sleep "$PAUSE"
    fi
done

_stop
echo ""
echo "All $REPEAT run(s) complete."
