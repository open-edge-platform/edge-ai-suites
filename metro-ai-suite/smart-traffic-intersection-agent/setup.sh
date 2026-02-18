#!/bin/bash

# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

export APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export HOST_IP=$(ip route get 1 2>/dev/null | awk '{print $7}')
if [ -z "$HOST_IP" ]; then
    export HOST_IP="localhost"
fi

# Verifiying and reading deployment instance config file and setting config specific to the current instance
DEPLOYMENT_CONFIG="$APP_DIR/src/config/deployment_instance.json"
if [ ! -f "$DEPLOYMENT_CONFIG" ]; then
    echo -e "${RED}Deployment configuration file not found: $DEPLOYMENT_CONFIG${NC}"
    return 1
fi

# set agent instance specific environment variables based on deployment_instance.json 
export INTERSECTION_NAME=$(grep -oP '"name"\s*:\s*"\K[^"]+' "$DEPLOYMENT_CONFIG")
PROJECT_NAME=${INTERSECTION_NAME:-trafficagent}
export INTERSECTION_LATITUDE=$(grep -oP '"latitude"\s*:\s*\K-?[\d.]+(?=,|$)' "$DEPLOYMENT_CONFIG")
export INTERSECTION_LONGITUDE=$(grep -oP '"longitude"\s*:\s*\K-?[\d.]+' "$DEPLOYMENT_CONFIG")
export AGENT_BACKEND_PORT=$(grep -oP '"agent_backend_port"\s*:\s*"\K[^"]+' "$DEPLOYMENT_CONFIG")
export AGENT_UI_PORT=$(grep -oP '"agent_ui_port"\s*:\s*"\K[^"]+' "$DEPLOYMENT_CONFIG")

# Unset port variables if they are empty in config file to allow using ephemeral port in docker-compose
[ "$AGENT_BACKEND_PORT" = "" ] && unset AGENT_BACKEND_PORT
[ "$AGENT_UI_PORT" = "" ] && unset AGENT_UI_PORT


# Setting command usage and invalid arguments handling before the actual setup starts
if [ "$#" -eq 0 ] || ([ "$#" -eq 1 ] && [ "$1" = "--help" ]); then
    # If no valid argument is passed, print usage information
    echo -e "-----------------------------------------------------------------"
    echo -e "${YELLOW}USAGE: ${GREEN}source setup.sh ${BLUE}[--setenv | --setup | --run | --restart [agent|deps|all] | --stop | --clean | --help]"
    echo -e "${YELLOW}"
    echo -e "  --setenv:                 Set environment variables without building image or starting any containers"
    echo -e "  --build:                  Build the service images without starting containers"
    echo -e "  --setup:                  Build and run the services"
    echo -e "  --run:                    Start the services without building image (if already built)"
    echo -e "  --restart [service_type]: Restart services"
    echo -e "                              • agent         - Restart Backend/UI service for Smart Traffic Intersection Agent"
    echo -e "                              • deps          - Restart dependencies (Services required by Smart Intersection RI)"
    echo -e "                              • all           - Restart all services including Backend/UI and dependencies (default if no argument is provided)"
    echo -e "  --stop:                   Stop the services"
    echo -e "  --clean [option]:         Clean up containers, volumes, and logs"
    echo -e "                              • --keep-models - Remove all application volume data except VLM models"
    echo -e "  --help:                   Show this help message${NC}"
    echo -e "-----------------------------------------------------------------"
    return 0

elif [ "$#" -gt 2 ]; then
    echo -e "${RED}ERROR: Too many arguments provided.${NC}"
    echo -e "${YELLOW}Use --help for usage information${NC}"
    return 1

elif [ "$1" != "--help" ] && [ "$1" != "--setenv" ] && [ "$1" != "--run" ] && [ "$1" != "--build" ] && [ "$1" != "--setup" ] && [ "$1" != "--restart" ] && [ "$1" != "--stop" ] && [ "$1" != "--clean" ]; then
    # Default case for unrecognized option
    echo -e "${RED}Unknown option: $1 ${NC}"
    echo -e "${YELLOW}Use --help for usage information${NC}"
    return 1

elif [ "$1" = "--clean" ] && [ "$#" -eq 2 ] && [ "$2" != "--keep-models" ]; then
    echo -e "${RED}ERROR: Invalid option for --clean: $2${NC}"
    echo -e "${YELLOW}Valid options: --keep-models${NC}"
    echo -e "${YELLOW}Use --help for usage information${NC}"
    return 1

elif [ "$1" = "--restart" ] && [ "$#" -eq 2 ] && [ "$2" != "agent" ] && [ "$2" != "deps" ] && [ "$2" != "all" ]; then
    echo -e "${RED}ERROR: Invalid restart argument: $2${NC}"
    echo -e "${YELLOW}Valid options: agent, deps, all${NC}"
    echo -e "${YELLOW}Use --help for usage information${NC}"
    return 1

elif [ "$1" = "--stop" ] || [ "$1" = "--clean" ]; then
    echo -e "${YELLOW}Stopping Smart-Traffic-Intersection-Agent ${RED}${PROJECT_NAME} ${YELLOW}... ${NC}"
    
    # check if ri-compose.yaml exists and run docker compose down accordingly
    if [ -L "${APP_DIR}/docker/ri-compose.yaml" ]; then
        docker compose -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p ${PROJECT_NAME} down 2> /dev/null
    else
        docker compose -f "${APP_DIR}/docker/agent-compose.yaml" -p ${PROJECT_NAME} down 2> /dev/null
    fi

    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to stop Smart-Traffic-Intersection-Agent services. ${NC}"
        return 1
    fi
    echo -e "${GREEN}All containers for Smart-Traffic-Intersection-Agent stopped and removed! ${NC}"

    if [ "$1" = "--clean" ]; then
        echo -e "${YELLOW}Removing volumes for Smart-Traffic-Intersection-Agent ... ${NC}"
        if [ "$2" = "--keep-models" ]; then
            echo -e "${CYAN}Keeping VLM model cache volume (ov-models)...${NC}"
            docker volume ls | grep $PROJECT_NAME | grep -v "ov-models" | awk '{ print $2 }' | xargs docker volume rm 2>/dev/null || true
        else
            docker volume ls | grep $PROJECT_NAME | awk '{ print $2 }' | xargs docker volume rm 2>/dev/null || true
        fi
        echo -e "${YELLOW}Removing secrets for Smart Intersection RI ... ${NC}"
        if [ -d "$RI_DIR" ]; then
            rm -rf "$RI_DIR/src/secrets/browser.auth" "$RI_DIR/chart/files/secrets" 2>/dev/null || true
        fi
        echo -e "${GREEN}Cleanup completed successfully. ${NC}"
    fi

    return 0
fi

# ============================================================================
# Dependencies: Setup Smart Intersection RI before running the agent Backend/UI
# ============================================================================

export SAMPLE_APP="smart-intersection"
SUBMODULE="deps/metro-vision"
SUBMODULE_PATH="$APP_DIR/$SUBMODULE"
export DEPS_DIR="$SUBMODULE_PATH/metro-ai-suite/metro-vision-ai-app-recipe"
export RI_DIR="$DEPS_DIR/$SAMPLE_APP"

# Verify if dependencies are setup; if not setup the required submodules and run install script
check_and_setup_dependencies() {
    echo -e "${BLUE}==> Setting up required submodules ...${NC}"

    if [ ! -d "$DEPS_DIR" ]; then
        # Run git submodule init and update to fetch the dependencies
        echo -e "${YELLOW}Dependencies not found. Initializing and updating git submodules...${NC}"
        git -C $APP_DIR submodule update --init --depth 1 $SUBMODULE
        git -C $SUBMODULE_PATH sparse-checkout init --cone
        git -C $SUBMODULE_PATH sparse-checkout set metro-ai-suite/metro-vision-ai-app-recipe

        # Verify if the git commands were successful
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to initialize and update dependencies${NC}"
            return 1
        fi
    fi

    # Check if install.sh exists
    if [ ! -f "$RI_DIR/install.sh" ]; then
        echo -e "${RED}Installation script not found for dependency : $SAMPLE_APP ${NC}"
        return 1
    fi
    
    # Run the installation script
    echo -e "${BLUE}==> Running installation script for smart-intersection...${NC}"
    cd $RI_DIR && ./install.sh && cd - > /dev/null
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to run install.sh for smart-intersection${NC}"
        cd - > /dev/null
        return 1
    fi
    echo -e "${GREEN}Installation script completed successfully${NC}"

    # Create symbolic link to compose-scenescape.yml in docker dir of agent application
    rm "$APP_DIR/docker/ri-compose.yaml" 2> /dev/null 
    ln -sf "$DEPS_DIR/compose-scenescape.yml" "$APP_DIR/docker/ri-compose.yaml"

    return 0
}

# Verify dependencies and setup (skip if stopping/cleaning services or only showing help or setting env vars)
if [ "$1" != "--help" ] && [ "$1" != "--setenv" ] && [ "$1" != "--build" ] && [ "$1" != "--clean" ] && [ "$1" != "--stop" ]; then
    check_and_setup_dependencies
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to setup dependencies. Please check the errors above.${NC}"
        return 1
    fi
fi

# ============================================================================
# END Dependencies
# ============================================================================

# Export required environment variables (HOST_IP already set above)
export TAG=${TAG:-latest}
# Construct registry path properly to avoid double slashes
if [[ -n "$REGISTRY" ]]; then
    export REGISTRY="${REGISTRY%/}/"
fi

# Traffic Intersection Agent Configuration
export TRAFFIC_INTELLIGENCE_PORT=${TRAFFIC_INTELLIGENCE_PORT:-8081}
export TRAFFIC_INTELLIGENCE_UI_PORT=${TRAFFIC_INTELLIGENCE_UI_PORT:-7860}
# Export environment variables required by application (HOST_IP already set above)
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export REFRESH_INTERVAL=${REFRESH_INTERVAL:-15}
export USER_GROUP_ID=$(id -g)
export VIDEO_GROUP_ID=$(getent group video | awk -F: '{printf "%s\n", $3}' 2>/dev/null || echo "44")
export RENDER_GROUP_ID=$(getent group render | awk -F: '{printf "%s\n", $3}' 2>/dev/null || echo "109")

# VLM Service Configuration
export VLM_MODEL_NAME=${VLM_MODEL_NAME:-microsoft/Phi-3.5-vision-instruct}

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

# Get and print the ports of all running services
print_all_service_host_endpoints() {
    # get the host port of each service using docker ps command and print
    echo -e
    echo -e "${MAGENTA}======================================================="
    echo -e "SERVICE ENDPOINTS"
    echo -e "=======================================================${NC}"
    
    for CONTAINER_NAME in $(docker ps --format '{{.Names}}' | grep $PROJECT_NAME);
    do
        # Set/print service name and the host port based on corresponding container name
        case "$CONTAINER_NAME" in
            *dlstreamer-pipeline-server*)
                SERVICE_NAME="DLStreamer Pipeline Server"
                PORT=$(docker port "$CONTAINER_NAME" 8080 | cut -d: -f2)
                echo -e "${BLUE}Access $SERVICE_NAME -> http://$HOST_IP:$PORT${NC}/pipelines"
                ;;
            *grafana*)
                SERVICE_NAME="Grafana Dashboard"
                PORT=$(docker port "$CONTAINER_NAME" 3000 | cut -d: -f2)
                echo -e "${BLUE}Access $SERVICE_NAME -> http://$HOST_IP:$PORT${NC}"
                ;;
            *node-red*)
                SERVICE_NAME="Node-RED"
                PORT=$(docker port "$CONTAINER_NAME" 1880 | cut -d: -f2)
                echo -e "${BLUE}Access $SERVICE_NAME -> http://$HOST_IP:$PORT${NC}"
                ;;
            *web*)
                SERVICE_NAME="Scenescape Web UI"
                PORT=$(docker port "$CONTAINER_NAME" 443 | cut -d: -f2)
                echo -e "${BLUE}Access $SERVICE_NAME -> https://$HOST_IP:$PORT${NC}"
                ;;
            *traffic-agent*)
                BACKEND_SERVICE_NAME="Traffic Intersection Agent API Docs"
                PORT=$(docker port "$CONTAINER_NAME" 8081 | cut -d: -f2)
                echo -e "${BLUE}Access $BACKEND_SERVICE_NAME -> http://$HOST_IP:$PORT/docs${NC}"

                UI_SERVICE_NAME="Traffic Intersection Agent UI"
                PORT=$(docker port "$CONTAINER_NAME" 7860 | cut -d: -f2)
                echo -e "${BLUE}Access $UI_SERVICE_NAME -> http://$HOST_IP:$PORT${NC}"
                ;;
            *vlm*)
                SERVICE_NAME="VLM OpenVINO Serving API"
                PORT=$(docker port "$CONTAINER_NAME" 8000 | cut -d: -f2)
                echo -e "${BLUE}Access $SERVICE_NAME -> http://$HOST_IP:$PORT/docs${NC}"
                ;;
            *)
                SERVICE_NAME="Unknown Service"
                ;;
        esac
    done
    echo -e "${MAGENTA}=======================================================${NC}"
    echo -e
}   

# Build service images without starting containers
build_service() {
    echo -e "${BLUE}==> Building Smart-Traffic-Intersection-Agent ${RED}${PROJECT_NAME} ${BLUE}...${NC}"

    # Build the service images
    if [ -L "${APP_DIR}/docker/ri-compose.yaml" ]; then
        docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME build
    else
        docker compose -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME build
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Smart-Traffic-Intersection-Agent images built successfully!${NC}"
    else
        echo -e "${RED}Failed to build Smart-Traffic-Intersection-Agent images${NC}"
        return 1
    fi
}

# Build agent Backend/UI image and run its container along with all other services - to run Traffic Intersection Agent End-to-End
build_and_start_service() {
    echo -e "${BLUE}==> Starting Smart-Traffic-Intersection-Agent ${RED}${PROJECT_NAME} ${BLUE}...${NC}"

    # Build and start the services
    docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME up -d --build
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Smart-Traffic-Intersection-Agent Services built and started successfully!${NC}"
        print_all_service_host_endpoints
    else
        echo -e "${RED}Failed to build and start Smart-Traffic-Intersection-Agent Services${NC}"
        return 1
    fi
}

# Start the services without building agent Backend/UI service image
start_service() {
    echo -e "${BLUE}==> Starting Smart-Traffic-Intersection-Agent ${RED}${PROJECT_NAME} ${BLUE}...${NC}"
    
    # Start the services
    docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME up -d
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Smart-Traffic-Intersection-Agent Services started successfully!${NC}"
        print_all_service_host_endpoints
    else
        echo -e "${RED}Failed to start Smart-Traffic-Intersection-Agent Services${NC}"
        return 1
    fi
}

# Restart the services based on provided service type (agent, deps or all)
restart_service() {
    local SERVICE_TYPE="${1:-all}"
    
    case "$SERVICE_TYPE" in
        agent)
            echo -e "${BLUE}==> Restarting Traffic Intersection Agent Backend/UI ...${NC}"
            
            # Stop the Traffic Intersection Agent Backend/UI Service
            docker compose -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME down
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to stop Traffic Intersection Agent Backend/UI service!${NC}"
                return 1
            fi
            
            docker compose -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME up -d --force-recreate
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}Traffic Intersection Agent Backend/UI restarted successfully!${NC}"
                print_all_service_host_endpoints
            else
                echo -e "${RED}Failed to restart Traffic Intersection Agent Backend/UI service!${NC}"
                return 1
            fi
            ;;

        deps)
            echo -e "${BLUE}==> Restarting Dependencies for Traffic Intersection Agent (Smart Intersection RI) ...${NC}"
            
            if [ ! -d "$DEPS_DIR" ] || [ ! -f "${APP_DIR}/docker/ri-compose.yaml" ]; then
                echo -e "${RED}Required Submodules for setting up Smart Intersection RI not found${NC}"
                echo -e "${YELLOW}Please run 'source setup.sh --setup' first to set up submodules${NC}"
                return 1
            fi
            
            # Stop the dependency - Smart Intersection RI services
            echo -e "${BLUE}==> Stopping dependencies ...${NC}"
            docker compose -f "${APP_DIR}/docker/ri-compose.yaml" -p $PROJECT_NAME down
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to stop dependencies!${NC}"
                return 1
            fi
            
            # Start with force-recreate to ensure env vars are picked up
            echo -e "${BLUE}==> Restarting dependencies (Smart Intersection RI) ...${NC}"
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -p $PROJECT_NAME up -d --force-recreate
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}Dependencies restarted successfully!${NC}"
                print_all_service_host_endpoints
            else
                echo -e "${RED}Failed to restart dependencies!${NC}"
                return 1
            fi
            ;;
            
        all)
            echo -e "${BLUE}==> Restarting all component services for Smart Traffic Intersection Agent ${RED}${PROJECT_NAME} ${BLUE} ...${NC}"
            
            if [ ! -d "$DEPS_DIR" ] || [ ! -f "$APP_DIR/docker/ri-compose.yaml" ]; then
                echo -e "${RED}Required Submodules for setting up Smart Intersection RI not found${NC}"
                echo -e "${YELLOW}Please run 'source setup.sh --setup' first to set up submodules${NC}"
                return 1
            fi
            
            # Stop all services
            docker compose -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME down
            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to stop services for Traffic Intersection Agent!${NC}"
                return 1
            fi

            # Restart all services
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME up -d --force-recreate  
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}All dependencies and Backend/UI services for Traffic Intersection Agent restarted successfully!${NC}"
            else
                echo -e "${RED}Failed to restart dependencies and Backend/UI services!${NC}"
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

# Execute actions based on options provided to setup script
case $1 in
    --build)
        build_service
        ;;
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
