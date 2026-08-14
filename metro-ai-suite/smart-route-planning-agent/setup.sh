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
DOCKER_DIR="src"
COMPOSE_MAIN="${DOCKER_DIR}/compose.yaml"

# Function to show help
show_help() {
    echo -e "${BLUE}Smart-Route-Planning-Agent Setup Script${NC}"
    echo -e "${YELLOW}USAGE: ${GREEN}source setup.sh ${BLUE}[COMMAND]${NC}"
    echo -e "-----------------------------------------------------------------"
    echo ""
    echo -e "${BLUE}Available Commands:${NC}"
    echo -e "  ${GREEN}--setup${NC}       Build and start the Smart-Route-Planning-Agent container"
    echo -e "  ${GREEN}--build${NC}       Build the Smart-Route-Planning-Agent Docker container"
    echo -e "  ${GREEN}--run${NC}         Start the Smart-Route-Planning-Agent container"
    echo -e "  ${GREEN}--stop${NC}        Stop the running container"
    echo -e "  ${GREEN}--restart${NC}     Restart the Smart-Route-Planning-Agent container"
    echo -e "  ${GREEN}--clean${NC}       Remove containers, volumes, and networks"
    echo -e "                    • ${GREEN}--all${NC}  Remove containers, volumes, networks, and images"
    echo -e "  ${GREEN}--help${NC}        Show this help message"
    echo ""
    echo -e "${BLUE}Quick Start:${NC}"
    echo -e "  ${YELLOW}source setup.sh --setup${NC}    # Build and start the container"
    echo -e "  ${YELLOW}source setup.sh --build${NC}    # Build the container"
    echo -e "  ${YELLOW}source setup.sh --run${NC}      # Start the container"
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

# Handle --help and argument validation
if [ "$#" -eq 0 ] || [ "$1" = "--help" ]; then
    show_help
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 0; else return 0; fi
fi

# Check for valid arguments
if [ "$#" -gt 2 ]; then
    echo -e "${RED}ERROR: Too many arguments provided.${NC}"
    echo -e "${YELLOW}Use '--help' for usage information${NC}"
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
fi

if [ "$#" -eq 2 ]; then
    if [ "$1" != "--clean" ] || [ "$2" != "--all" ]; then
        echo -e "${RED}ERROR: Invalid arguments: $1 $2${NC}"
        echo -e "${YELLOW}Only '--clean --all' accepts a second argument.${NC}"
        echo -e "${YELLOW}Use '--help' for usage information${NC}"
        if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
    fi
fi


# Base configuration
HOST_IP=$(ip route get 1 2>/dev/null | awk '{print $7}')  # Fetch the host IP
# Fallback to localhost if HOST_IP is empty
[[ -z "$HOST_IP" ]] && HOST_IP="127.0.0.1"
export HOST_IP

# Add HOST_IP to no_proxy only if not already present
[[ $no_proxy != *"${HOST_IP}"* ]] && export no_proxy="${no_proxy},${HOST_IP}"

export TAG=${TAG:-latest}
# Construct registry path properly to avoid double slashes
if [[ -n "$REGISTRY" ]]; then
    export REGISTRY="${REGISTRY%/}/"
fi
PROJECT_NAME="srpa"

# Traffic Analysis Configuration
export TRAFFIC_BUFFER_DURATION=${TRAFFIC_BUFFER_DURATION:-60}
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export DATA_RETENTION_HOURS=${DATA_RETENTION_HOURS:-24}

# AI Route Planner Configuration
export AI_ROUTE_PLANNER_PORT=${AI_ROUTE_PLANNER_PORT:-7864}

# Reasoning Model Configuration (optional)
export REASONING_MODEL_NAME=${REASONING_MODEL_NAME:-}
if [[ -n "$REASONING_MODEL_NAME" ]]; then
    export COMPOSE_PROFILES="reasoning"
else
    unset COMPOSE_PROFILES
fi

echo -e "${GREEN}Environment variables set:${NC}"
echo -e "  HOST_IP: ${YELLOW}$HOST_IP${NC}"
echo -e "  TAG: ${YELLOW}$TAG${NC}"
echo -e "  REGISTRY: ${YELLOW}$REGISTRY${NC}"


# Function to build Docker images
build_images() {
    echo -e "${BLUE}==> Building Smart-Route-Planning-Agent Docker container...${NC}"

    if docker build -t "${REGISTRY}smart-route-planning-agent:${TAG}" -f ./src/Dockerfile ./src/; then
        echo -e "${GREEN}Docker image ${YELLOW}${REGISTRY}smart-route-planning-agent:${TAG}${GREEN} built successfully!${NC}"
        return 0
    else
        echo -e "${RED}Failed to build Docker container!${NC}"
        return 1
    fi
}

# Function to start the service
start_service() {
    echo -e "${BLUE}==> Starting Smart-Route-Planning-Agent container...${NC}"

    if [[ -n "$REASONING_MODEL_NAME" ]]; then
        echo -e "  Route planning mode: ${YELLOW}AI reasoning${NC}"
        echo -e "  REASONING_MODEL_NAME: ${YELLOW}$REASONING_MODEL_NAME${NC}"
        echo -e "${YELLOW}Note: Model is downloaded if not already present/cached and can take several minutes.${NC}"
    else
        echo -e "  Route planning mode: ${YELLOW}rule based${NC}"
        echo -e "${BLUE}Tip: export REASONING_MODEL_NAME=<hf-org/model> before sourcing this script to enable AI reasoning.${NC}"
    fi

    if docker compose -f "$COMPOSE_MAIN" -p "$PROJECT_NAME" up -d; then
        echo -e "${GREEN}Smart-Route-Planning-Agent container started successfully!${NC}"
        echo -e "${BLUE}AI Route Planner UI: ${YELLOW}http://${HOST_IP}:${AI_ROUTE_PLANNER_PORT}${NC}"
    else
        echo -e "${RED}Failed to start Smart-Route-Planning-Agent container!${NC}"
        return 1
    fi
}


# Check Docker Compose availability
if ! check_docker_compose; then
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
fi

# Main logic based on command
case "$1" in
    "--setup")
        echo -e "${BLUE}==> Running full setup (build and start)...${NC}"
        if build_images; then
            start_service
        else
            echo -e "${RED}Setup failed during build step${NC}"
            if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
        fi
        ;;
    "--build")
        build_images
        ;;
    "--run")
        start_service
        ;;
    "--stop")
        echo -e "${YELLOW}Stopping Smart-Route-Planning-Agent container...${NC}"
        if COMPOSE_PROFILES="reasoning" docker compose -f "$COMPOSE_MAIN" -p "$PROJECT_NAME" down; then
            echo -e "${GREEN}Smart-Route-Planning-Agent container stopped successfully.${NC}"
        else
            echo -e "${RED}Failed to stop container${NC}"
            if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
        fi
        ;;
    "--restart")
        echo -e "${BLUE}==> Restarting Smart-Route-Planning-Agent container...${NC}"
        if COMPOSE_PROFILES="reasoning" docker compose -f "$COMPOSE_MAIN" -p "$PROJECT_NAME" down; then
            echo -e "${GREEN}Container stopped successfully${NC}"
            start_service
        else
            echo -e "${RED}Failed to stop container${NC}"
            if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
        fi
        ;;
    "--clean")
        echo -e "${YELLOW}Cleaning up Smart-Route-Planning-Agent resources...${NC}"

        # Stop and remove containers.
        echo -e "${YELLOW}Stopping and removing containers...${NC}"
        COMPOSE_PROFILES="reasoning" docker compose -f "$COMPOSE_MAIN" -p "$PROJECT_NAME" down 2>/dev/null || true
        echo -e "${GREEN}Containers stopped and removed.${NC}"

        # Remove project volumes
        echo -e "${YELLOW}Removing volumes...${NC}"
        docker volume ls --format '{{.Name}}' | grep "$PROJECT_NAME" | xargs -r docker volume rm 2>/dev/null || true
        echo -e "${GREEN}Volumes removed.${NC}"

        # Remove project networks
        echo -e "${YELLOW}Removing networks...${NC}"
        docker network ls --format '{{.Name}}' | grep "$PROJECT_NAME" | xargs -r docker network rm 2>/dev/null || true
        echo -e "${GREEN}Networks removed.${NC}"

        # Remove project-related images only with --all
        if [ "$2" = "--all" ]; then
            echo -e "${YELLOW}Removing container image for Smart Route Planning Agent ...${NC}"
            docker rmi -f "${REGISTRY}smart-route-planning-agent:${TAG}" 2>/dev/null || true
            echo -e "${GREEN}Images removed.${NC}"
        fi

        echo -e "${GREEN}Clean up completed successfully.${NC}"
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo -e "${YELLOW}Use '--help' for usage information${NC}"
        if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then exit 1; else return 1; fi
        ;;
esac
