#!/usr/bin/env bash
# start.sh – entrypoint for the metrics-collector container.
#
# Starts the supervisord bundled inside intel/retail-benchmark (which manages
# qmassa, Intel NPU tool, Intel PCM, sar, and free) then runs the HTTP
# metrics server in the foreground so Docker receives SIGTERM correctly.

set -euo pipefail

METRICS_DIR="${METRICS_DIR:-/tmp/results}"
mkdir -p "${METRICS_DIR}"

# Clear stale data from a previous run so all series start fresh.
rm -rf "${METRICS_DIR}"/* 2>/dev/null || true

echo "[metrics-collector] metrics directory: ${METRICS_DIR}"
echo "[metrics-collector] starting supervisord (qmassa / NPU / PCM / sar / free)"

# Start supervisord in the background – this launches all OS-level collectors
# that are pre-configured inside the intel/retail-benchmark base image.
/usr/bin/supervisord -c /supervisord.conf &

# Start the HTTP metrics server in the foreground (PID 1 receives SIGTERM).
exec python3 /app/app.py
