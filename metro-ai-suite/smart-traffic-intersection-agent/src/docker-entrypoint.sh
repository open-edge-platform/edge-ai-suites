#!/bin/bash
# Docker entrypoint script to run both API and UI services

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Traffic Intersection Agent${NC}"
echo "========================================"

# Set default environment variables if not provided
export TRAFFIC_INTERSECTION_AGENT_PORT=${TRAFFIC_INTERSECTION_AGENT_PORT:-8081}
export TRAFFIC_INTERSECTION_AGENT_HOST=${TRAFFIC_INTERSECTION_AGENT_HOST:-0.0.0.0}
export TRAFFIC_INTERSECTION_AGENT_UI_PORT=${TRAFFIC_INTERSECTION_AGENT_UI_PORT:-7860}
export USE_API=${USE_API:-true}
export API_URL=${API_URL:-"http://localhost:${TRAFFIC_INTERSECTION_AGENT_PORT}/api/v1/traffic/current"}

echo "Configuration:"
echo "  Backend API Port: $TRAFFIC_INTERSECTION_AGENT_PORT"
echo "  UI Dashboard Port: $TRAFFIC_INTERSECTION_AGENT_UI_PORT"
echo "  Host: $TRAFFIC_INTERSECTION_AGENT_HOST"
echo "  Log Level: ${LOG_LEVEL:-INFO}"

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
echo -e "${GREEN}Starting Backend API on port $TRAFFIC_INTERSECTION_AGENT_PORT...${NC}"
python run.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start the UI dashboard
echo -e "${GREEN}Starting UI Dashboard on port $TRAFFIC_INTERSECTION_AGENT_UI_PORT...${NC}"
cd ui && python app.py &
UI_PID=$!
cd ..

echo -e "${GREEN}Both services started successfully!${NC}"
echo "  Backend API: http://$TRAFFIC_INTERSECTION_AGENT_HOST:$TRAFFIC_INTERSECTION_AGENT_PORT"
echo "  UI Dashboard: http://$TRAFFIC_INTERSECTION_AGENT_HOST:$TRAFFIC_INTERSECTION_AGENT_UI_PORT"
echo "  Health Check: http://$TRAFFIC_INTERSECTION_AGENT_HOST:$TRAFFIC_INTERSECTION_AGENT_PORT/health"
echo "  API Docs: http://$TRAFFIC_INTERSECTION_AGENT_HOST:$TRAFFIC_INTERSECTION_AGENT_PORT/docs"
# Wait for both processes
wait $BACKEND_PID $UI_PID
