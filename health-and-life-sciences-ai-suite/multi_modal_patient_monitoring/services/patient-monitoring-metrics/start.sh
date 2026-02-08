#!/usr/bin/env bash

# Start the existing metrics collectors (supervisord in base image)
# and then run the HTTP metrics API.

# Clean previous metrics from the shared metrics directory on container start.
# This corresponds to the host ./metrics folder mounted at /tmp/results.
METRICS_DIR=${METRICS_DIR:-/tmp/results}
mkdir -p "${METRICS_DIR}"
rm -rf "${METRICS_DIR}"/* || true

# Run supervisord in the background to start GPU/NPU/platform collectors
/usr/bin/supervisord -c /supervisord.conf &

# Start the lightweight Python HTTP server exposing /metrics on port 9000
exec python3 /app/app.py
