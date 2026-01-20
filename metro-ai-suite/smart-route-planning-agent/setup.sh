#!/bin/bash

# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Setting variables for directories used as volume mounts
SOURCE="src"
SECRETS_DIR="${SOURCE}/secrets"
DOCKER_DIR="docker"
COMPOSE_MAIN="${DOCKER_DIR}/compose.yaml"

# Function to show help
show_help() {
    echo -e "${BLUE}Smart-Route-Planning-Agent Setup Script${NC}"
    echo -e "${YELLOW}USAGE: ${GREEN}source setup.sh ${BLUE}[COMMAND]${NC}"
    echo -e "-----------------------------------------------------------------"
    echo ""
    echo -e "${BLUE}Available Commands:${NC}"
    echo -e "  ${GREEN}setup${NC}         Build and start the Smart-Route-Planning-Agent container"
    echo -e "  ${GREEN}build${NC}         Build the Smart-Route-Planning-Agent Docker container"
    echo -e "  ${GREEN}up${NC}            Start the Smart-Route-Planning-Agent container"
    echo -e "  ${GREEN}down${NC}          Stop the running container"
    echo -e "  ${GREEN}restart${NC}       Restart the Smart-Route-Planning-Agent container"
    echo -e "  ${GREEN}help${NC}          Show this help message"
    echo ""
    echo -e "${BLUE}Quick Start:${NC}"
    echo -e "  ${YELLOW}source setup.sh setup${NC}    # Build and start the container"
    echo -e "  ${YELLOW}source setup.sh build${NC}    # Build the container"
    echo -e "  ${YELLOW}source setup.sh up${NC}       # Start the container"
    echo -e "-----------------------------------------------------------------"
}

# Function to check if Docker Compose is available
check_docker_compose() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
        return 1
    fi
    
    if ! docker compose version &> /dev/null; then
        echo -e "${RED}Error: Docker Compose is not available${NC}"
        return 1
    fi
}

# Handle help and argument validation
if [ "$#" -eq 0 ] || [ "$1" = "help" ]; then
    show_help
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 0; else return 0; fi
fi

# Check for valid arguments
if [ "$#" -gt 1 ]; then
    echo -e "${RED}ERROR: Too many arguments provided.${NC}"
    echo -e "${YELLOW}Use 'help' for usage information${NC}"
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
fi



# Export all environment variables
# Base configuration
export HOST_IP=$(ip route get 1 2>/dev/null | awk '{print $7}')  # Fetch the host IP
# Fallback to localhost if HOST_IP is empty
if [[ -z "$HOST_IP" ]]; then
    export HOST_IP="127.0.0.1"
    echo -e "${YELLOW}Warning: Could not detect host IP, using fallback: ${HOST_IP}${NC}"
fi
# Add HOST_IP to no_proxy only if not already present
[[ $no_proxy != *"${HOST_IP}"* ]] && export no_proxy="${no_proxy},${HOST_IP}"
export TAG=${TAG:-latest}
export REGISTRY_URL=${REGISTRY_URL:-intel}
export PROJECT_NAME=${PROJECT_NAME:-}

# Construct registry path properly to avoid double slashes
if [[ -n "$REGISTRY_URL" && -n "$PROJECT_NAME" ]]; then
    # Both are set, combine with single slash
    export REGISTRY="${REGISTRY_URL%/}/${PROJECT_NAME%/}/"
elif [[ -n "$REGISTRY_URL" ]]; then
    # Only registry URL is set
    export REGISTRY="${REGISTRY_URL%/}/"
elif [[ -n "$PROJECT_NAME" ]]; then
    # Only project name is set
    export REGISTRY="${PROJECT_NAME%/}/"
else
    # Neither is set, use empty registry
    export REGISTRY=""
fi
echo -e "${GREEN}Using registry: ${YELLOW}$REGISTRY ${NC}"

# Traffic Analysis Configuration
export TRAFFIC_BUFFER_DURATION=${TRAFFIC_BUFFER_DURATION:-60}
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export DATA_RETENTION_HOURS=${DATA_RETENTION_HOURS:-24}

# Health Check Configuration
export HEALTH_CHECK_INTERVAL=${HEALTH_CHECK_INTERVAL:-30s}
export HEALTH_CHECK_TIMEOUT=${HEALTH_CHECK_TIMEOUT:-10s}
export HEALTH_CHECK_RETRIES=${HEALTH_CHECK_RETRIES:-3}
export HEALTH_CHECK_START_PERIOD=${HEALTH_CHECK_START_PERIOD:-10s}

# AI Route Planner Configuration
export AI_ROUTE_PLANNER_PORT=${AI_ROUTE_PLANNER_PORT:-7864}
export AI_ROUTE_PLANNER_DIR=${AI_ROUTE_PLANNER_DIR:-ai-route-planner}

echo -e "${GREEN}Environment variables set:${NC}"
echo -e "  HOST_IP: ${YELLOW}$HOST_IP${NC}"
echo -e "  TAG: ${YELLOW}$TAG${NC}"
echo -e "  REGISTRY: ${YELLOW}$REGISTRY${NC}"

# Function to build Docker images
build_images() {
    echo -e "${BLUE}==> Building Smart-Route-Planning-Agent Docker container...${NC}"
    
    docker compose -f $COMPOSE_MAIN build
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Docker container built successfully${NC}"
    else
        echo -e "${RED}Failed to build Docker container${NC}"
        return 1
    fi
}

# Function to start the service
start_service() {
    echo -e "${BLUE}==> Starting Smart-Route-Planning-Agent container...${NC}"
    
    docker compose -f $COMPOSE_MAIN up -d
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Smart-Route-Planning-Agent container started successfully!${NC}"
        echo -e "${BLUE}AI Route Planner UI: ${YELLOW}http://${HOST_IP}:${AI_ROUTE_PLANNER_PORT}${NC}"
        echo ""
        echo -e "${BLUE}To follow logs in real-time, run:${NC}"
        echo -e "${YELLOW}docker compose -f docker/compose.yaml logs -f${NC}"
    else
        echo -e "${RED}Failed to start Smart-Route-Planning-Agent container${NC}"
        return 1
    fi
}


# Check Docker Compose availability
check_docker_compose
if [ $? -ne 0 ]; then
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
fi

# Main logic based on command
case "$1" in
    "setup")
        echo -e "${BLUE}==> Running full setup (build and start)...${NC}"
        build_images
        if [ $? -eq 0 ]; then
            start_service
        else
            echo -e "${RED}Setup failed during build step${NC}"
            if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
        fi
        ;;
    "build")
        build_images
        ;;
    "up")
        start_service
        ;;
    "down")
        echo -e "${YELLOW}Stopping Smart-Route-Planning-Agent container...${NC}"
        docker compose -f $COMPOSE_MAIN down
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Smart-Route-Planning-Agent container stopped successfully.${NC}"
        else
            echo -e "${RED}Failed to stop container${NC}"
            if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
        fi
        ;;
    "restart")
        echo -e "${BLUE}==> Restarting Smart-Route-Planning-Agent container...${NC}"
        docker compose -f $COMPOSE_MAIN down
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Container stopped successfully${NC}"
            start_service
        else
            echo -e "${RED}Failed to stop container${NC}"
            if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
        fi
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo -e "${YELLOW}Use 'help' for usage information${NC}"
        if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
        ;;
esac

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Done!${NC}"
else
    echo -e "${RED}Operation failed. Check the logs above for details.${NC}"
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
fi