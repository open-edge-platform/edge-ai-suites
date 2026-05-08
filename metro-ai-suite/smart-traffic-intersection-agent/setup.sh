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

# Path variables needed by all commands (including --stop/--clean)
export SAMPLE_APP="smart-intersection"
CLONE_DIR="deps/metro-vision"
CLONE_PATH="$APP_DIR/$CLONE_DIR"
export DEPS_DIR="$CLONE_PATH/metro-ai-suite/metro-vision-ai-app-recipe"
export RI_DIR="$DEPS_DIR/$SAMPLE_APP"
export OVMS_CONFIG_DIR="${APP_DIR}/.ovms"

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
    echo -e "  --clean [option]:         Clean up containers, volumes, and networks"
    echo -e "                              • --keep-models - Remove all application volume data except VLM models"
    echo -e "                              • --all         - Remove containers, volumes, networks, and images"
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

elif [ "$1" = "--clean" ] && [ "$#" -eq 2 ] && [ "$2" != "--keep-models" ] && [ "$2" != "--all" ]; then
    echo -e "${RED}ERROR: Invalid option for --clean: $2${NC}"
    echo -e "${YELLOW}Valid options: --keep-models, --all${NC}"
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
        docker compose --project-directory "$DEPS_DIR" -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p ${PROJECT_NAME} down
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
            echo -e "${CYAN}Keeping OVMS model cache (${OVMS_CONFIG_DIR}/models)...${NC}"
            docker volume ls --format '{{.Name}}' | grep "$PROJECT_NAME" | xargs -r docker volume rm 2>/dev/null || true
        else
            docker volume ls --format '{{.Name}}' | grep "$PROJECT_NAME" | xargs -r docker volume rm 2>/dev/null || true
            if [ -d "${OVMS_CONFIG_DIR}" ]; then
                echo -e "${YELLOW}Removing OVMS model cache (${OVMS_CONFIG_DIR})...${NC}"
                rm -rf "${OVMS_CONFIG_DIR}"
            fi
        fi
        echo -e "${YELLOW}Removing networks for Smart-Traffic-Intersection-Agent ... ${NC}"
        docker network ls --format '{{.Name}}' | grep "$PROJECT_NAME" | xargs -r docker network rm 2>/dev/null || true
        if [ "$2" = "--all" ]; then
            echo -e "${YELLOW}Removing images for Smart-Traffic-Intersection-Agent ... ${NC}"
            docker rmi -f "${REGISTRY:-}smart-traffic-intersection-agent:${TAG:-latest}" 2>/dev/null || true
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

# Check if VLM Model name is set or not
if [ -z "$VLM_MODEL_NAME" ]; then
    echo -e "${RED}Error: VLM_MODEL_NAME environment variable is not set. Please check docs for some possible VLM model names.${NC}"
    return 1
fi

# Verify if dependencies are setup; if not, clone the required dependency and run install script
check_and_setup_dependencies() {
    echo -e "${BLUE}==> Setting up required dependencies ...${NC}"

    if [ ! -d "$DEPS_DIR" ]; then
        # Run git clone to fetch the dependencies (sparse, shallow)
        echo -e "${YELLOW}Dependencies not found. Cloning repository...${NC}"
        git clone --filter=blob:none --sparse --depth 1 \
            --branch release-2026.0.0 \
            https://github.com/open-edge-platform/edge-ai-suites.git \
            "$CLONE_PATH"
        git -C "$CLONE_PATH" sparse-checkout set metro-ai-suite/metro-vision-ai-app-recipe

        # Verify if the git commands were successful
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to clone and set up dependencies${NC}"
            return 1
        fi
    fi

    # Check if install.sh exists
    if [ ! -f "$RI_DIR/install.sh" ]; then
        echo -e "${RED}Installation script not found for dependency : $SAMPLE_APP ${NC}"
        return 1
    fi
    
    # Ensure all required secrets are generated
    if [ -f "$RI_DIR/src/secrets/browser.auth" ] && [ ! -f "$RI_DIR/src/secrets/pgserver/pgserver.env" ]; then
        echo -e "${YELLOW}Required secrets not found. Regenerating secrets...${NC}"
        rm -f "$RI_DIR/src/secrets/browser.auth"
    fi

    # Run the installation script
    echo -e "${BLUE}==> Running installation script for smart-intersection...${NC}"
    #cd $RI_DIR && ./install.sh && cd - > /dev/null
    cd $RI_DIR && ./install.sh && cd -
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

# VLM / OVMS Configuration
export VLM_MODEL_NAME=${VLM_MODEL_NAME}
export VLM_TARGET_DEVICE=${VLM_TARGET_DEVICE:-CPU}
export VLM_WEIGHT_FORMAT=${VLM_WEIGHT_FORMAT:-}

# OVMS model repository directory (host-side, mounted into OVMS container)
# Health Check Configuration
export HEALTH_CHECK_INTERVAL=${HEALTH_CHECK_INTERVAL:-30s}
export HEALTH_CHECK_TIMEOUT=${HEALTH_CHECK_TIMEOUT:-10s}
export HEALTH_CHECK_RETRIES=${HEALTH_CHECK_RETRIES:-3}
export HEALTH_CHECK_START_PERIOD=${HEALTH_CHECK_START_PERIOD:-10s}

# ============================================================================
# OVMS Model Export Functions (host-side, following PR #2109 pattern)
# ============================================================================

sanitize_ovms_metadata_name() {
    printf '%s' "$1" | sed 's#[^A-Za-z0-9_.-]#_#g'
}

is_openvino_namespace_model() {
    [[ "$1" == OpenVINO/* ]]
}

# Get weight format based on target device (GPU/NPU → int4, CPU → int8)
get_ovms_weight_format() {
    local target_device="$1"
    case "$target_device" in
        *NPU*|*GPU*) echo "int4" ;;
        *) echo "int8" ;;
    esac
}

get_ovms_cache_size() {
    local target_device="$1"
    case "$target_device" in
        *GPU*|*NPU*) echo "2" ;;
        *) echo "10" ;;
    esac
}

# Generate storage-aware model name: {model}_{device}_{format}
get_ovms_storage_model_name() {
    local source_model="$1"
    local target_device="$2"
    local weight_format="$3"
    local sanitized
    sanitized=$(sanitize_ovms_metadata_name "$source_model")

    if is_openvino_namespace_model "$source_model"; then
        printf '%s_%s' "$sanitized" "$target_device"
    else
        printf '%s_%s_%s' "$sanitized" "$target_device" "$weight_format"
    fi
}

ovms_config_has_model() {
    local config_path="$1"
    local model_name="$2"
    grep -q "\"name\": \"${model_name}\"" "$config_path" 2>/dev/null
}

# Export and convert a HuggingFace model for OVMS on the host
export_model_for_ovms() {
    local source_model="$1"
    local target_device="$2"
    local weight_format="$3"
    local pipeline_type="$4"
    local cache_size="$5"
    local extra_args=()
    local export_status
    local storage_model_name

    if [ -z "$source_model" ]; then
        echo -e "${RED}ERROR: Missing source model for OVMS export.${NC}"
        return 1
    fi

    storage_model_name=$(get_ovms_storage_model_name "$source_model" "$target_device" "$weight_format")
    echo -e "[ovms-service] ${BLUE}Storage model name: ${YELLOW}${storage_model_name}${NC}"

    if [ -n "$pipeline_type" ]; then
        extra_args+=(--pipeline_type "$pipeline_type")
    fi

    export storage_model_name

    (
        mkdir -p "${OVMS_CONFIG_DIR}"
        cd "${OVMS_CONFIG_DIR}" || exit 1

        echo -e "Downloading latest export_model.py from OVMS repository..."
        curl -fsSL https://raw.githubusercontent.com/openvinotoolkit/model_server/refs/tags/v2026.1/demos/common/export_models/export_model.py -o export_model.py || exit 1

        echo -e "Creating Python virtual environment for model export..."
        if ! dpkg-query -W -f='${Status}' python3-venv 2>/dev/null | grep -q "ok installed"; then
            echo -e "Installing python3-venv package..."
            sudo apt install -y python3-venv || exit 1
        else
            echo -e "python3-venv is already installed, skipping installation"
        fi

        python3 -m venv ovms_venv || exit 1
        # shellcheck disable=SC1091
        source ovms_venv/bin/activate || exit 1

        if is_openvino_namespace_model "$source_model"; then
            echo -e "${GREEN}Model '${source_model}' is from OpenVINO namespace (pre-converted).${NC}"
            echo -e "${YELLOW}Skipping full requirements — only need huggingface_hub for download.${NC}"
            if ! pip install --no-cache-dir 'huggingface_hub<0.27' jinja2; then
                echo -e "${RED}ERROR: Failed to install minimal dependencies for OpenVINO model.${NC}"
                deactivate
                rm -rf ovms_venv
                exit 1
            fi
        else
            local ovms_requirements_url="https://raw.githubusercontent.com/openvinotoolkit/model_server/refs/tags/v2026.1/demos/common/export_models/requirements.txt"
            local tmp_requirements
            tmp_requirements=$(mktemp)

            if ! curl -fsSL "$ovms_requirements_url" -o "$tmp_requirements"; then
                echo -e "${RED}ERROR: Failed to download OVMS requirements.${NC}"
                rm -f "$tmp_requirements"
                deactivate
                rm -rf ovms_venv
                exit 1
            fi

            if grep -q '^transformers' "$tmp_requirements"; then
                sed -i 's/^transformers.*/transformers==4.53.3/' "$tmp_requirements"
            else
                echo 'transformers==4.53.3' >> "$tmp_requirements"
            fi

            if ! pip install --no-cache-dir -r "$tmp_requirements"; then
                echo -e "${RED}ERROR: Failed to install OVMS requirements.${NC}"
                rm -f "$tmp_requirements"
                deactivate
                rm -rf ovms_venv
                exit 1
            fi
            rm -f "$tmp_requirements"
        fi

        if [ -n "${HUGGINGFACE_TOKEN:-}" ]; then
            pip install --no-cache-dir -U 'huggingface_hub[hf_xet]==0.36.0' || exit 1
            echo -e "${BLUE}Logging in to Hugging Face to access gated models...${NC}"
            hf auth login --token "$HUGGINGFACE_TOKEN" || exit 1
        fi

        mkdir -p models

        if ! python3 export_model.py text_generation \
            --source_model "$source_model" \
            --model_name "$storage_model_name" \
            --weight-format "$weight_format" \
            --config_file_path models/config.json \
            --model_repository_path models \
            --target_device "$target_device" \
            --cache_size "$cache_size" \
            "${extra_args[@]}"; then
            echo -e "${RED}ERROR: Failed to export the model '${source_model}' for OVMS.${NC}"
            deactivate
            rm -rf ovms_venv
            exit 1
        fi

        echo -e "Cleaning up virtual environment..."
        deactivate
        rm -rf ovms_venv
    )
    export_status=$?
    if [ $export_status -ne 0 ]; then
        return $export_status
    fi

    echo "$storage_model_name"
}

ensure_ovms_model() {
    local model_name="$1"
    local target_device="$2"
    local weight_format="$3"
    local pipeline_type="$4"
    local ovms_model_config="${OVMS_CONFIG_DIR}/models/config.json"
    local storage_model_name
    local model_path

    storage_model_name=$(get_ovms_storage_model_name "$model_name" "$target_device" "$weight_format")
    model_path="${OVMS_CONFIG_DIR}/models/${storage_model_name}"

    echo -e "[ovms-service] ${BLUE}Checking for model: ${YELLOW}${storage_model_name}${NC}"

    if [ -d "$model_path" ] && [ -f "${model_path}/graph.pbtxt" ]; then
        echo -e "[ovms-service] ${GREEN}Model ${YELLOW}${storage_model_name}${GREEN} already exists. Skipping export.${NC}"

        if [ -f "${ovms_model_config}" ] && ovms_config_has_model "${ovms_model_config}" "${storage_model_name}"; then
            echo -e "[ovms-service] ${GREEN}Model is registered in OVMS config.${NC}"
        else
            echo -e "[ovms-service] ${YELLOW}Model exists but not in config. Will re-register.${NC}"
        fi

        echo "$storage_model_name"
    else
        echo -e "[ovms-service] ${YELLOW}Model ${RED}${storage_model_name}${YELLOW} not found. Exporting...${NC}"

        export_model_for_ovms \
            "$model_name" \
            "$target_device" \
            "$weight_format" \
            "$pipeline_type" \
            "$(get_ovms_cache_size "$target_device")" || return 1
    fi
}

# ============================================================================
# END OVMS Model Export Functions
# ============================================================================

# Get and print the ports of all running services
print_all_service_host_endpoints() {
    # get the host port of each service using docker ps command and print
    echo -e
    echo -e "${MAGENTA}======================================================="
    echo -e "SERVICE ENDPOINTS"
    echo -e "=======================================================${NC}"
    
    for CONTAINER_NAME in $(docker ps --format '{{.Names}}' | grep -E "^${PROJECT_NAME}");
    do
        # Set/print service name and the host port based on corresponding container name
        case "$CONTAINER_NAME" in
            *nginx-reverse-proxy*)
                SERVICE_NAME="Nginx Reverse Proxy"
                HTTPS_PORT=$(docker port "$CONTAINER_NAME" 443 2>/dev/null | grep -v '^\[' | head -1 | cut -d: -f2)
                if [ -n "$HTTPS_PORT" ]; then
                    echo -e "${BLUE}Access Grafana Dashboard -> https://$HOST_IP:$HTTPS_PORT/grafana/${NC}"
                    echo -e "${BLUE}Access Node-RED -> https://$HOST_IP:$HTTPS_PORT/nodered/${NC}"
                    echo -e "${BLUE}Access DLStreamer Pipeline Server -> https://$HOST_IP:$HTTPS_PORT/api/pipelines${NC}"
                    echo -e "${BLUE}Access Scenescape Web UI -> https://$HOST_IP:$HTTPS_PORT/${NC}"
                fi
                ;;
            *traffic-agent*)
                BACKEND_SERVICE_NAME="Traffic Intersection Agent API Docs"
                PORT=$(docker port "$CONTAINER_NAME" 8081 2>/dev/null | grep -v '^\[' | head -1 | cut -d: -f2)
                echo -e "${CYAN}Access $BACKEND_SERVICE_NAME -> http://$HOST_IP:$PORT/docs${NC}"

                UI_SERVICE_NAME="Traffic Intersection Agent UI"
                PORT=$(docker port "$CONTAINER_NAME" 7860 2>/dev/null | grep -v '^\[' | head -1 | cut -d: -f2)
                echo -e "${CYAN}Access $UI_SERVICE_NAME -> http://$HOST_IP:$PORT${NC}"
                ;;
            *vlm*|*ovms*)
                SERVICE_NAME="OVMS API"
                PORT=$(docker port "$CONTAINER_NAME" 8000 2>/dev/null | grep -v '^\[' | head -1 | cut -d: -f2)
                echo -e "${BLUE}Access $SERVICE_NAME -> http://$HOST_IP:$PORT${NC}"
                ;;
        esac
    done
    echo -e "${MAGENTA}=======================================================${NC}"
    echo -e
}

# Prepare OVMS model on the host (export if not already present)
prepare_ovms_model() {
    # Determine weight format (auto-detect based on device if not user-specified)
    local weight_format="${VLM_WEIGHT_FORMAT:-$(get_ovms_weight_format "$VLM_TARGET_DEVICE")}"
    export VLM_WEIGHT_FORMAT="$weight_format"

    echo -e "${BLUE}==> Preparing OVMS model on host...${NC}"
    echo -e "[ovms-service] ${BLUE}VLM Model:          ${YELLOW}${VLM_MODEL_NAME}${NC}"
    echo -e "[ovms-service] ${BLUE}Target Device:      ${YELLOW}${VLM_TARGET_DEVICE}${NC}"
    echo -e "[ovms-service] ${BLUE}Weight Format:      ${YELLOW}${weight_format}${NC}"
    echo -e "[ovms-service] ${BLUE}OVMS Config Dir:    ${YELLOW}${OVMS_CONFIG_DIR}${NC}"

    mkdir -p "${OVMS_CONFIG_DIR}/models"

    local storage_name
    storage_name=$(ensure_ovms_model \
        "$VLM_MODEL_NAME" \
        "$VLM_TARGET_DEVICE" \
        "$weight_format" \
        "VLM_CB") || return 1

    export VLM_STORAGE_MODEL_NAME="$storage_name"
    echo -e "[ovms-service] ${GREEN}VLM Storage Model: ${YELLOW}${VLM_STORAGE_MODEL_NAME}${NC}"
}

# Build service images without starting containers
build_service() {
    echo -e "${BLUE}==> Building Smart-Traffic-Intersection-Agent ${RED}${PROJECT_NAME} ${BLUE}...${NC}"

    # Build the service images
    if [ -L "${APP_DIR}/docker/ri-compose.yaml" ]; then
        docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME build
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

    # Ensure OVMS model is exported on the host before starting containers
    prepare_ovms_model || return 1

    # Build and start the services
    docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME up -d --build
    
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
    
    # Ensure OVMS model is exported on the host before starting containers
    prepare_ovms_model || return 1

    # Start the services
    docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME up -d
    
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
            
            # Restart only the agent-specific services (exclude nginx override which requires RI compose)
            local AGENT_SERVICES="traffic-agent ovms-service live-metrics-service collector"
            
            # Stop the Traffic Intersection Agent Backend/UI Service
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME stop $AGENT_SERVICES
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME rm -f $AGENT_SERVICES
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to stop Traffic Intersection Agent Backend/UI service!${NC}"
                return 1
            fi
            
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME up -d --force-recreate $AGENT_SERVICES
            
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
                echo -e "${RED}Required dependencies for setting up Smart Intersection RI not found${NC}"
                echo -e "${YELLOW}Please run 'source setup.sh --setup' first to set up dependencies${NC}"
                return 1
            fi
            
            # Stop the dependency - Smart Intersection RI services
            echo -e "${BLUE}==> Stopping dependencies ...${NC}"
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -p $PROJECT_NAME down
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to stop dependencies!${NC}"
                return 1
            fi
            
            # Start with force-recreate to ensure env vars are picked up
            echo -e "${BLUE}==> Restarting dependencies (Smart Intersection RI) ...${NC}"
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -p $PROJECT_NAME up -d --force-recreate
            
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
                echo -e "${RED}Required dependencies for setting up Smart Intersection RI not found${NC}"
                echo -e "${YELLOW}Please run 'source setup.sh --setup' first to set up dependencies${NC}"
                return 1
            fi
            
            # Stop all services
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME down
            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to stop services for Traffic Intersection Agent!${NC}"
                return 1
            fi

            # Restart all services
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" -p $PROJECT_NAME up -d --force-recreate  
            
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
