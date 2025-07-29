#!/bin/bash
if [ "$MODE" = "ui" ]; then
    echo "Starting in UI mode..."
    cd /app/ui
    exec python main.py
elif [ "$MODE" = "backend" ]; then
    echo "Starting in backend mode..."
    cd /app/backend
    exec uvicorn main:app --host 0.0.0.0 --port 8000
elif [ "$MODE" = "combined" ]; then
    echo "Starting in combined mode (both UI and backend)..."
    cd /app/backend
    uvicorn main:app --host 0.0.0.0 --port 8000 &
    cd /app/ui
    exec python main.py
else
    echo "Unknown mode: $MODE. Valid options are: ui, backend, combined"
    exit 1
fi