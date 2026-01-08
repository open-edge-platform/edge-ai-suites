#!/bin/bash
# Docker entrypoint script to run both API and UI services

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Traffic Intelligence Services${NC}"
echo "========================================"

# Set default environment variables if not provided
export TRAFFIC_INTELLIGENCE_PORT=${TRAFFIC_INTELLIGENCE_PORT:-8081}
export TRAFFIC_INTELLIGENCE_HOST=${TRAFFIC_INTELLIGENCE_HOST:-0.0.0.0}
export TRAFFIC_INTELLIGENCE_UI_PORT=${TRAFFIC_INTELLIGENCE_UI_PORT:-7860}
export USE_API=${USE_API:-true}
export API_URL=${API_URL:-"http://localhost:${TRAFFIC_INTELLIGENCE_PORT}/api/v1/traffic/current"}

echo "Configuration:"
echo "  Backend API Port: $TRAFFIC_INTELLIGENCE_PORT"
echo "  UI Dashboard Port: $TRAFFIC_INTELLIGENCE_UI_PORT"
echo "  Host: $TRAFFIC_INTELLIGENCE_HOST"
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
echo -e "${GREEN}Starting Backend API on port $TRAFFIC_INTELLIGENCE_PORT...${NC}"
python run.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start the UI dashboard
echo -e "${GREEN}Starting UI Dashboard on port $TRAFFIC_INTELLIGENCE_UI_PORT...${NC}"
cd ui && python app.py &
UI_PID=$!
cd ..

echo -e "${GREEN}Both services started successfully!${NC}"
echo "  Backend API: http://$TRAFFIC_INTELLIGENCE_HOST:$TRAFFIC_INTELLIGENCE_PORT"
echo "  UI Dashboard: http://$TRAFFIC_INTELLIGENCE_HOST:$TRAFFIC_INTELLIGENCE_UI_PORT"
echo "  Health Check: http://$TRAFFIC_INTELLIGENCE_HOST:$TRAFFIC_INTELLIGENCE_PORT/health"
echo "  API Docs: http://$TRAFFIC_INTELLIGENCE_HOST:$TRAFFIC_INTELLIGENCE_PORT/docs"

# Wait for both processes
wait $BACKEND_PID $UI_PID
