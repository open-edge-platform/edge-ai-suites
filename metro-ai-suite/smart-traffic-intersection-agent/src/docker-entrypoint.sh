#!/bin/bash
# Docker entrypoint script to run both API and UI services

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Smart Traffic Intersection Agent${NC}"
echo "========================================"

# Set default environment variables if not provided
export REFRESH_INTERVAL=${REFRESH_INTERVAL:-15}
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export WEATHER_MOCK=${WEATHER_MOCK:-false}
export VLM_MODEL=${VLM_MODEL:-Qwen/Qwen2.5-VL-3B-Instruct}
export HIGH_DENSITY_THRESHOLD=${HIGH_DENSITY_THRESHOLD:-10}
export USE_API=${USE_API:-true}

echo "Configuration:"
echo "LOG_LEVEL: ${LOG_LEVEL}"
echo "REFRESH_INTERVAL: ${REFRESH_INTERVAL} seconds"
echo "INTERSECTION_NAME: ${INTERSECTION_NAME}"
echo "INTERSECTION_LATITUDE: ${INTERSECTION_LATITUDE}"
echo "INTERSECTION_LONGITUDE: ${INTERSECTION_LONGITUDE}"
echo "WEATHER_MOCK: ${WEATHER_MOCK}"
echo "VLM_MODEL: ${VLM_MODEL}"
echo "HIGH_DENSITY_THRESHOLD: ${HIGH_DENSITY_THRESHOLD}"
echo "========================================"


# Function to cleanup on exit
cleanup() {
    echo -e "${YELLOW}Shutting down services...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $UI_PID 2>/dev/null || true
    exit 0
}

# Set up signal handling
trap cleanup SIGTERM SIGINT

# Start the backend API service
echo -e "${GREEN}Starting Backend API ...${NC}"
python run.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start the UI dashboard
echo -e "${GREEN}Starting UI Dashboard ...${NC}"
cd ui && python app.py &
UI_PID=$!
cd ..

echo -e "${GREEN}Agent Backend and UI services started successfully!${NC}"

# Wait for both processes
wait $BACKEND_PID $UI_PID
