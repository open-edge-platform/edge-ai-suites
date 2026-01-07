#!/bin/bash

# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Setting command usage and invalid arguments handling before the actual setup starts
if [ "$#" -eq 0 ] || ([ "$#" -eq 1 ] && [ "$1" = "--help" ]); then
    # If no valid argument is passed, print usage information
    echo -e "-----------------------------------------------------------------"
    echo -e "${YELLOW}USAGE: ${GREEN}source setup.sh ${BLUE}[--setenv | --run | --setup | --restart [agent|prerequisite] | --stop | --clean | --help]"
    echo -e "${YELLOW}"
    echo -e "  --setenv:                Set environment variables without starting any containers"
    echo -e "  --run:                   Start the services"
    echo -e "  --setup:                 Build and run the services (first time setup)"
    echo -e "  --restart [service]:     Restart services with updated environment variables"
    echo -e "                           • agent         - Restart only Scene Intelligence services"
    echo -e "                           • prerequisite  - Restart only prerequisite services (edge-ai-suites)"
    echo -e "                           • (no argument) - Restart all services"
    echo -e "  --stop:                  Stop the services"
    echo -e "  --clean:                 Clean up containers, volumes, and logs"
    echo -e "  --help:                  Show this help message${NC}"
    echo -e "-----------------------------------------------------------------"
    return 0

elif [ "$#" -gt 2 ]; then
    echo -e "${RED}ERROR: Too many arguments provided.${NC}"
    echo -e "${YELLOW}Use --help for usage information${NC}"
    return 1

elif [ "$1" != "--help" ] && [ "$1" != "--setenv" ] && [ "$1" != "--run" ] && [ "$1" != "--setup" ] && [ "$1" != "--restart" ] && [ "$1" != "--stop" ] && [ "$1" != "--clean" ]; then
    # Default case for unrecognized option
    echo -e "${RED}Unknown option: $1 ${NC}"
    echo -e "${YELLOW}Use --help for usage information${NC}"
    return 1

elif [ "$1" = "--restart" ] && [ "$#" -eq 2 ] && [ "$2" != "agent" ] && [ "$2" != "prerequisite" ]; then
    echo -e "${RED}ERROR: Invalid restart argument: $2${NC}"
    echo -e "${YELLOW}Valid options: agent, prerequisite${NC}"
    echo -e "${YELLOW}Use --help for usage information${NC}"
    return 1

elif [ "$1" = "--stop" ]; then
    # If --stop is passed, bring down the Docker containers and stop 
    echo -e "${YELLOW}Stopping Scene Intelligence services... ${NC}"
    
    # Stop Docker services
    docker compose -f docker/compose.yaml down
    if [ $? -ne 0 ]; then
        return 1
    fi
    echo -e "${GREEN}Scene Intelligence services stopped successfully. ${NC}"
    
    # Stop edge-ai-suites services if they exist
    EDGE_AI_SUITES_DIR="edge-ai-suites"
    if [ -d "$EDGE_AI_SUITES_DIR/metro-ai-suite/metro-vision-ai-app-recipe" ]; then
        cd "$EDGE_AI_SUITES_DIR/metro-ai-suite/metro-vision-ai-app-recipe"
        if [ -f "docker-compose.yml" ] || [ -f "compose.yaml" ]; then
            echo -e "${YELLOW}Stopping edge-ai-suites services... ${NC}"
            docker compose down 2>/dev/null
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}edge-ai-suites services stopped successfully. ${NC}"
            else
                echo -e "${YELLOW}Warning: Could not stop edge-ai-suites services${NC}"
            fi
        fi
        cd - > /dev/null
    else
        echo -e "${YELLOW}edge-ai-suites services not found, skipping... ${NC}"
    fi
    
    return 0

elif [ "$1" = "--clean" ]; then
    # If --clean is passed, clean up containers and volumes
    echo -e "${YELLOW}Cleaning up containers and volumes... ${NC}"
    
    docker compose -f docker/compose.yaml down 2>/dev/null || true
    
    echo -e "${YELLOW}Removing scene intelligence volumes... ${NC}"
    docker volume ls | grep scene-intelligence | awk '{ print $2 }' | xargs docker volume rm 2>/dev/null || true
    
    if [ $? -ne 0 ]; then
        return 1
    fi
    echo -e "${GREEN}Docker cleanup completed successfully. ${NC}"
    
    # Clean up the cloned edge-ai-suites repository
    EDGE_AI_SUITES_DIR="edge-ai-suites"
    if [ -d "$EDGE_AI_SUITES_DIR" ]; then
        echo -e "${YELLOW}Cleaning up edge-ai-suites repository... ${NC}"
        
        # Stop docker services in edge-ai-suites if they exist
        if [ -d "$EDGE_AI_SUITES_DIR/metro-ai-suite/metro-vision-ai-app-recipe" ]; then
            cd "$EDGE_AI_SUITES_DIR/metro-ai-suite/metro-vision-ai-app-recipe"
            if [ -f "docker-compose.yml" ] || [ -f "compose.yaml" ]; then
                echo -e "${YELLOW}Stopping edge-ai-suites docker services... ${NC}"
                docker compose down 2>/dev/null || true
                
                echo -e "${YELLOW}Removing metro-vision-ai-app-recipe volumes... ${NC}"
                docker volume ls | grep metro-vision-ai-app-recipe | awk '{ print $2 }' | xargs docker volume rm 2>/dev/null || true
            fi
            cd - > /dev/null
        fi
        
    else
        echo -e "${YELLOW}edge-ai-suites repository not found, skipping... ${NC}"
    fi
    
    echo -e "${GREEN}Full cleanup completed successfully. ${NC}"
    return 0

fi

# ============================================================================
# PREREQUISITES: Setup edge-ai-suites before running the application
# ============================================================================

# Export HOST_IP early so it can be used in prerequisite checks
export HOST_IP=$(ip route get 1 2>/dev/null | awk '{print $7}')
# If HOST_IP is empty, use localhost
if [ -z "$HOST_IP" ]; then
    export HOST_IP="127.0.0.1"
fi
# Function to check if prerequisites are met
check_and_setup_prerequisites() {
    local EDGE_AI_SUITES_DIR="edge-ai-suites"
    local REQUIRED_BRANCH="release-1.2.0"
    
    echo -e "${BLUE}==> Checking prerequisites...${NC}"
    
    # Check if edge-ai-suites directory exists
    if [ ! -d "$EDGE_AI_SUITES_DIR" ]; then
        echo -e "${YELLOW}edge-ai-suites not found. Cloning repository...${NC}"
        
        # Clone the repository with the specific branch (shallow clone, only latest layer)
        git clone --depth 1 --single-branch --branch $REQUIRED_BRANCH https://github.com/open-edge-platform/edge-ai-suites.git
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to clone edge-ai-suites repository${NC}"
            return 1
        fi
        
        echo -e "${GREEN}Successfully cloned edge-ai-suites${NC}"
        
    else
        echo -e "${GREEN}edge-ai-suites directory already exists${NC}"
        
    fi
    
    # Navigate to the metro-vision-ai-app-recipe directory
    local METRO_DIR="$EDGE_AI_SUITES_DIR/metro-ai-suite/metro-vision-ai-app-recipe"
    
    if [ ! -d "$METRO_DIR" ]; then
        echo -e "${RED}Directory $METRO_DIR not found${NC}"
        return 1
    fi
    
    cd "$METRO_DIR"
    
    # Check if install.sh exists
    if [ ! -f "install.sh" ]; then
        echo -e "${RED}install.sh not found in $METRO_DIR${NC}"
        cd - > /dev/null
        return 1
    fi
    
    # Comment out the problematic chown lines in the smart-intersection install.sh
    echo -e "${BLUE}==> Updating install.sh to comment out chown commands...${NC}"
    if [ -f "smart-intersection/install.sh" ]; then
        sed -i 's/^sudo chown -R \$USER:\$USER chart\/files\/secrets$/# &/' smart-intersection/install.sh
        sed -i 's/^sudo chown -R \$USER:\$USER src\/secrets$/# &/' smart-intersection/install.sh
        echo -e "${GREEN}Successfully commented out chown commands in smart-intersection/install.sh${NC}"
    else
        echo -e "${YELLOW}Warning: smart-intersection/install.sh not found, skipping sed modifications${NC}"
    fi
    
    # Run the installation script
    echo -e "${BLUE}==> Running installation script for smart-intersection...${NC}"
    ./install.sh smart-intersection
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to run install.sh for smart-intersection${NC}"
        cd - > /dev/null
        return 1
    fi
    
    echo -e "${GREEN}Installation script completed successfully${NC}"
    
    # Download container images and run with Docker Compose
    echo -e "${BLUE}==> Downloading container images and starting services...${NC}"
    docker compose up -d
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to start services with docker compose${NC}"
        cd - > /dev/null
        return 1
    fi
    
    echo -e "${GREEN}Container images downloaded and services started${NC}"
    
    # Verify running status
    echo -e "${BLUE}==> Verifying running status...${NC}"
    sleep 5  # Give services a moment to start
    
    docker compose ps
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Services are running. Verification completed.${NC}"
    else
        echo -e "${YELLOW}Warning: Could not verify service status${NC}"
    fi
    
    # Return to the original directory
    cd - > /dev/null
    
    echo -e "${GREEN}Prerequisites setup completed successfully!${NC}"
    echo ""
    
    # Display edge-ai-suites service URLs
    echo -e "${BLUE}Edge AI Suites Services:${NC}"
    echo -e "  • SceneScape Web UI: ${YELLOW}https://${HOST_IP}:443${NC}"
    echo -e "  • DLStreamer Pipeline Server API: ${YELLOW}http://${HOST_IP}:8080${NC}"
    echo -e "  • InfluxDB UI: ${YELLOW}http://${HOST_IP}:8086${NC}"
    echo -e "  • Grafana Dashboard: ${YELLOW}http://${HOST_IP}:3000${NC}"
    echo -e "  • Node-RED UI: ${YELLOW}http://${HOST_IP}:1880${NC}"
    echo ""
    
    return 0
}

# Run prerequisites check and setup (skip if only stopping or cleaning)
if [ "$1" != "--stop" ] && [ "$1" != "--clean" ] && [ "$1" != "--help" ] && [ "$1" != "--restart" ]; then
    check_and_setup_prerequisites
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to setup prerequisites. Please check the errors above.${NC}"
        return 1
    fi
fi

# ============================================================================
# END PREREQUISITES
# ============================================================================

# Export required environment variables (HOST_IP already set above)
export TAG=${TAG:-latest}
export REGISTRY=${REGISTRY:-}

# Traffic Intelligence Service Configuration
export TRAFFIC_INTELLIGENCE_PORT=${TRAFFIC_INTELLIGENCE_PORT:-8081}
export TRAFFIC_INTELLIGENCE_UI_PORT=${TRAFFIC_INTELLIGENCE_UI_PORT:-7860}
export REFRESH_INTERVAL=${REFRESH_INTERVAL:-15}

# User and group IDs for containers
export USER_GROUP_ID=$(id -g)
export VIDEO_GROUP_ID=$(getent group video | awk -F: '{printf "%s\n", $3}' 2>/dev/null || echo "44")
export RENDER_GROUP_ID=$(getent group render | awk -F: '{printf "%s\n", $3}' 2>/dev/null || echo "109")

# Traffic Analysis Configuration
export TRAFFIC_BUFFER_DURATION=${TRAFFIC_BUFFER_DURATION:-60}
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export DATA_RETENTION_HOURS=${DATA_RETENTION_HOURS:-24}

# VLM Service Configuration
export VLM_SERVICE_PORT=${VLM_SERVICE_PORT:-9764}
export VLM_MODEL_NAME=${VLM_MODEL_NAME:-microsoft/Phi-3.5-vision-instruct}
export VLM_TIMEOUT_SECONDS=${VLM_TIMEOUT_SECONDS:-300}
export VLM_MAX_COMPLETION_TOKENS=${VLM_MAX_COMPLETION_TOKENS:-1500}
export VLM_TEMPERATURE=${VLM_TEMPERATURE:-0.1}
export VLM_TOP_P=${VLM_TOP_P:-0.1}

# VLM OpenVINO Configuration
export VLM_DEVICE=${VLM_DEVICE:-CPU}
export VLM_COMPRESSION_WEIGHT_FORMAT=${VLM_COMPRESSION_WEIGHT_FORMAT:-int8}
export VLM_SEED=${VLM_SEED:-42}
export VLM_WORKERS=${VLM_WORKERS:-1}
export VLM_LOG_LEVEL=${VLM_LOG_LEVEL:-info}
export VLM_ACCESS_LOG_FILE=${VLM_ACCESS_LOG_FILE:-/dev/null}

# Automatically adjust VLM settings for GPU
if [[ "$VLM_DEVICE" == "GPU" ]]; then
    export VLM_COMPRESSION_WEIGHT_FORMAT=int4
    export VLM_WORKERS=1  # GPU works best with single worker
fi

# Health Check Configuration
export HEALTH_CHECK_INTERVAL=${HEALTH_CHECK_INTERVAL:-30s}
export HEALTH_CHECK_TIMEOUT=${HEALTH_CHECK_TIMEOUT:-10s}
export HEALTH_CHECK_RETRIES=${HEALTH_CHECK_RETRIES:-3}
export HEALTH_CHECK_START_PERIOD=${HEALTH_CHECK_START_PERIOD:-10s}

# Proxy settings
export no_proxy_env=${no_proxy}

# Function to build and start the services
build_and_start_service() {
    echo -e "${BLUE}==> Building and Starting Scene Intelligence Services...${NC}"
    
    # Build and start the services
    docker compose -f docker/compose.yaml up -d --build 2>&1 1>/dev/null
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Scene Intelligence Services built and started successfully!${NC}"
        
        echo ""
        echo -e "${BLUE}Services:${NC}"
        echo -e "  • Traffic Intelligence API Docs: ${YELLOW}http://${HOST_IP}:${TRAFFIC_INTELLIGENCE_PORT}/docs${NC}"
        echo -e "  • Traffic Intelligence UI: ${YELLOW}http://${HOST_IP}:${TRAFFIC_INTELLIGENCE_UI_PORT}${NC}"
        echo -e "  • VLM Service API Docs: ${YELLOW}http://${HOST_IP}:${VLM_SERVICE_PORT}/docs${NC}"
        echo ""
        echo -e "${BLUE}To view logs:${NC}"
        echo -e "  ${YELLOW}docker compose -f docker/compose.yaml logs -f${NC}"
        echo -e "${BLUE}To stop the services:${NC}"
        echo -e "  ${YELLOW}source setup.sh --stop${NC}"
    else
        echo -e "${RED}Failed to build and start Scene Intelligence Services${NC}"
        return 1
    fi
}

# Function to start the services
start_service() {
    echo -e "${BLUE}==> Starting Scene Intelligence Services...${NC}"
    
    # Start the services
    docker compose -f docker/compose.yaml up -d
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Scene Intelligence Services started successfully!${NC}"
        
        echo ""
        echo -e "${BLUE}Services:${NC}"
        echo -e "  • Traffic Intelligence API: ${YELLOW}http://${HOST_IP}:${TRAFFIC_INTELLIGENCE_PORT}${NC}"
        echo -e "  • Traffic Intelligence UI: ${YELLOW}http://${HOST_IP}:${TRAFFIC_INTELLIGENCE_UI_PORT}${NC}"
        echo -e "  • VLM Service: ${YELLOW}http://${HOST_IP}:${VLM_SERVICE_PORT}${NC}"
        echo ""
        echo -e "${BLUE}To view logs:${NC}"
        echo -e "  ${YELLOW}docker compose -f docker/compose.yaml logs -f${NC}"
        echo -e "${BLUE}To stop the services:${NC}"
        echo -e "  ${YELLOW}source setup.sh --stop${NC}"
    else
        echo -e "${RED}Failed to start Scene Intelligence Services${NC}"
        return 1
    fi
}

# Function to restart the services (for env var changes)
restart_service() {
    local SERVICE_TYPE="${1:-all}"
    
    case "$SERVICE_TYPE" in
        agent)
            echo -e "${BLUE}==> Restarting Scene Intelligence Services with updated environment variables...${NC}"
            
            # Stop the Scene Intelligence services
            docker compose -f docker/compose.yaml down
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to stop Scene Intelligence services${NC}"
                return 1
            fi
            
            # Start with force-recreate to ensure env vars are picked up
            docker compose -f docker/compose.yaml up -d --force-recreate
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}Scene Intelligence Services restarted successfully with updated configuration!${NC}"
                
                echo ""
                echo -e "${BLUE}Services:${NC}"
                echo -e "  • Traffic Intelligence API: ${YELLOW}http://${HOST_IP}:${TRAFFIC_INTELLIGENCE_PORT}${NC}"
                echo -e "  • Traffic Intelligence UI: ${YELLOW}http://${HOST_IP}:${TRAFFIC_INTELLIGENCE_UI_PORT}${NC}"
                echo -e "  • VLM Service: ${YELLOW}http://${HOST_IP}:${VLM_SERVICE_PORT}${NC}"
                echo ""
                echo -e "${BLUE}To view logs:${NC}"
                echo -e "  ${YELLOW}docker compose -f docker/compose.yaml logs -f${NC}"
            else
                echo -e "${RED}Failed to restart Scene Intelligence Services${NC}"
                return 1
            fi
            ;;
            
        prerequisite)
            echo -e "${BLUE}==> Restarting Prerequisite Services (edge-ai-suites)...${NC}"
            
            local METRO_DIR="edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe"
            
            if [ ! -d "$METRO_DIR" ]; then
                echo -e "${RED}Directory $METRO_DIR not found${NC}"
                echo -e "${YELLOW}Please run 'source setup.sh --setup' first to set up prerequisites${NC}"
                return 1
            fi
            
            cd "$METRO_DIR"
            
            # Stop the prerequisite services
            echo -e "${BLUE}==> Stopping prerequisite services...${NC}"
            docker compose down
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to stop prerequisite services${NC}"
                cd - > /dev/null
                return 1
            fi
            
            # Start with force-recreate to ensure env vars are picked up
            echo -e "${BLUE}==> Starting prerequisite services with updated configuration...${NC}"
            docker compose up -d --force-recreate
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}Prerequisite Services restarted successfully with updated configuration!${NC}"
                
                echo ""
                echo -e "${BLUE}Edge AI Suites Services:${NC}"
                echo -e "  • SceneScape Web UI: ${YELLOW}https://${HOST_IP}:443${NC}"
                echo -e "  • DLStreamer Pipeline Server API: ${YELLOW}http://${HOST_IP}:8080${NC}"
                echo -e "  • InfluxDB UI: ${YELLOW}http://${HOST_IP}:8086${NC}"
                echo -e "  • Grafana Dashboard: ${YELLOW}http://${HOST_IP}:3000${NC}"
                echo -e "  • Node-RED UI: ${YELLOW}http://${HOST_IP}:1880${NC}"
                echo ""
            else
                echo -e "${RED}Failed to restart Prerequisite Services${NC}"
                cd - > /dev/null
                return 1
            fi
            
            cd - > /dev/null
            ;;
            
        all)
            echo -e "${BLUE}==> Restarting All Services with updated environment variables...${NC}"
            
            # Restart prerequisite services first
            local METRO_DIR="edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe"
            
            if [ -d "$METRO_DIR" ]; then
                cd "$METRO_DIR"
                
                echo -e "${BLUE}==> Restarting prerequisite services...${NC}"
                docker compose down
                docker compose up -d --force-recreate
                
                if [ $? -eq 0 ]; then
                    echo -e "${GREEN}Prerequisite Services restarted successfully!${NC}"
                else
                    echo -e "${RED}Failed to restart Prerequisite Services${NC}"
                    cd - > /dev/null
                    return 1
                fi
                
                cd - > /dev/null
            else
                echo -e "${YELLOW}Prerequisite services directory not found, skipping...${NC}"
            fi
            
            # Restart Scene Intelligence services
            echo -e "${BLUE}==> Restarting Scene Intelligence Services...${NC}"
            docker compose -f docker/compose.yaml down
            docker compose -f docker/compose.yaml up -d --force-recreate
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}All services restarted successfully with updated configuration!${NC}"
                
                echo ""
                echo -e "${BLUE}Edge AI Suites Services:${NC}"
                echo -e "  • SceneScape Web UI: ${YELLOW}https://${HOST_IP}:443${NC}"
                echo -e "  • DLStreamer Pipeline Server API: ${YELLOW}http://${HOST_IP}:8080${NC}"
                echo -e "  • InfluxDB UI: ${YELLOW}http://${HOST_IP}:8086${NC}"
                echo -e "  • Grafana Dashboard: ${YELLOW}http://${HOST_IP}:3000${NC}"
                echo -e "  • Node-RED UI: ${YELLOW}http://${HOST_IP}:1880${NC}"
                echo ""
                echo -e "${BLUE}Scene Intelligence Services:${NC}"
                echo -e "  • Traffic Intelligence API: ${YELLOW}http://${HOST_IP}:${TRAFFIC_INTELLIGENCE_PORT}${NC}"
                echo -e "  • Traffic Intelligence UI: ${YELLOW}http://${HOST_IP}:${TRAFFIC_INTELLIGENCE_UI_PORT}${NC}"
                echo -e "  • VLM Service: ${YELLOW}http://${HOST_IP}:${VLM_SERVICE_PORT}${NC}"
                echo ""
            else
                echo -e "${RED}Failed to restart Scene Intelligence Services${NC}"
                return 1
            fi
            ;;
    esac
}

# if only base environment variables are to be set without deploying application, exit here
if [ "$1" = "--setenv" ]; then
    echo -e "${BLUE}Done setting up all environment variables. ${NC}"
    return 0
fi

# Main logic based on command
case $1 in
    --setup)
        build_and_start_service
        ;;
    --restart)
        restart_service "$2"
        ;;
    --run|*)
        start_service
        ;;
esac

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Done!${NC}"
else
    echo -e "${RED}Setup failed. Check the logs above for details.${NC}"
    return 1
fi
