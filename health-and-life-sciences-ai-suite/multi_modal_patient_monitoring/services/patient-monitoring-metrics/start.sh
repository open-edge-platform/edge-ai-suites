#!/usr/bin/env bash

# Start the existing metrics collectors (supervisord in base image)
# and then run the FastAPI metrics API.

# Run supervisord in the background to start GPU/NPU/platform collectors
/usr/bin/supervisord -c /supervisord.conf &

# Start the lightweight Python HTTP server exposing /metrics on port 9000
exec python3 /app/app.py
