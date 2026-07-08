#!/bin/bash

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

export REGISTRY_URL=${REGISTRY_URL:-}
export PROJECT_NAME=${PROJECT_NAME:-}
export TAG=${TAG:-latest}
export RTSP_STREAM_PORT=${RTSP_STREAM_PORT:-8554}
RTSP_STREAM_BIND_IP=${RTSP_STREAM_BIND_IP:-0.0.0.0}


[[ -n "$REGISTRY_URL" ]] && REGISTRY_URL="${REGISTRY_URL%/}/"
[[ -n "$PROJECT_NAME" ]] && PROJECT_NAME="${PROJECT_NAME%/}/"
REGISTRY="${REGISTRY_URL}${PROJECT_NAME}"

export REGISTRY="${REGISTRY:-}"

# Display info about the registry being used
if [ -z "$REGISTRY" ]; then
  echo -e "${YELLOW}Warning: No registry prefix set. Images will be tagged without a registry prefix.${NC}"
  echo "Using local image names with tag: ${TAG}"
else
  echo "Using registry prefix: ${REGISTRY}"
fi


# Helper functions for colored output
print_error() {
    echo -e "${RED}Error: $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}Warning: $1${NC}"
}

print_success() {
    echo -e "${GREEN}Success: $1${NC}"
}

print_info() {
    echo -e "${BLUE}Info: $1${NC}"
}

print_header() {
    echo -e "${PURPLE}=== $1 ===${NC}"
}

MQTT_SECRETS_FILE="./resources/mqtt-secrets"

resolve_mqtt_credentials() {
    if [[ -n "${MQTT_USER}" && -n "${MQTT_PASSWORD}" ]]; then
        print_info "Using provided MQTT credentials (MQTT_USER=${MQTT_USER})"
        return 0
    fi

    if ! bash "$(dirname "${BASH_SOURCE[0]}")/scripts/gen-mqtt-secrets.sh"; then
        return 1
    fi

    # shellcheck source=/dev/null
    source "${MQTT_SECRETS_FILE}"
    export MQTT_USER MQTT_PASSWORD
    print_info "MQTT credentials loaded from ${MQTT_SECRETS_FILE}"
}

# Get the host IP address
get_host_ip() {
    # Try different methods to get the host IP
    if command -v ip &> /dev/null; then
        # Use ip command if available (Linux)
        HOST_IP=$(ip route get 1 | sed -n 's/^.*src \([0-9.]*\) .*$/\1/p')
    elif command -v ifconfig &> /dev/null; then
        # Use ifconfig if available (Linux/Mac)
        HOST_IP=$(ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -n 1)
    else
        # Fallback to hostname command
        HOST_IP=$(hostname -I | awk '{print $1}')
    fi

    # Fallback to localhost if we couldn't determine the IP
    if [ -z "$HOST_IP" ]; then
        HOST_IP="localhost"
        print_warning "Could not determine host IP, using localhost instead."
    fi

    echo "$HOST_IP"
}

# Generate Frigate config for scenescape mode (si1 uses env var or auto-detect; si2+ use env var or prompt)
generate_scenescape_config() {
    local config_file="./resources/frigate-config/config.yml"
    local port="${RTSP_STREAM_PORT:-8554}"

    local total_nodes
    read -r -p "$(echo -e "${BLUE}How many SI nodes total? [1]: ${NC}")" total_nodes
    total_nodes="${total_nodes:-1}"
    if ! [[ "${total_nodes}" =~ ^[0-9]+$ ]] || [ "${total_nodes}" -lt 1 ]; then
        print_warning "Invalid input, using 1 SI node."
        total_nodes=1
    fi

    # Copy template and add cameras section
    cp "./resources/frigate-config/config-scenescape.yml" "${config_file}"
    printf '\ncameras:\n' >> "${config_file}"

    # Loop through all SI nodes (si1 to siN)
    for node_num in $(seq 1 "${total_nodes}"); do
        local si_id="si${node_num}"
        local rtsp_ip

        if [ "${node_num}" -eq 1 ]; then
            rtsp_ip="${SI_RTSP_HOST:-}"
            if [ -z "${rtsp_ip}" ]; then
                if [ "${SCENESCAPE_NVR_ONLY}" = "true" ]; then
                    # NVR-only (System 2): SI is remote, prompt for its IP
                    read -r -p "$(echo -e "${BLUE}  RTSP stream IP for si1: ${NC}")" rtsp_ip
                else
                    # Single-node (start): SI is local, auto-detect
                    rtsp_ip="$(get_host_ip)"
                fi
            fi
            if [ -z "${rtsp_ip}" ]; then
                print_error "RTSP IP for si1 is required."
                return 1
            fi
        else
            local env_var="SI${node_num}_RTSP_HOST"
            rtsp_ip="${!env_var:-}"
            if [ -z "${rtsp_ip}" ]; then
                read -r -p "$(echo -e "${BLUE}  RTSP stream IP for ${si_id}: ${NC}")" rtsp_ip
            fi
            if [ -z "${rtsp_ip}" ]; then
                print_error "RTSP IP for ${si_id} is required. Skipping ${si_id}."
                continue
            fi
        fi

        for cam_num in 1 2 3 4; do
            cat >> "${config_file}" <<CAMERA_BLOCK

  ${si_id}-camera${cam_num}:
    ffmpeg:
      inputs:
        - path: rtsp://${rtsp_ip}:${port}/camera${cam_num}
          input_args: preset-rtsp-generic
          roles:
            - record
      output_args:
        record: -f segment -segment_time 10 -segment_format mp4 -reset_timestamps 1 -strftime 1 -c:v copy -movflags +faststart
    detect:
      enabled: false
    motion:
      enabled: false
    snapshots:
      enabled: false
    record:
      enabled: true
      retain:
        days: 1
        mode: all
CAMERA_BLOCK
        done

        print_success "Added ${si_id} (cameras 1-4, RTSP: ${rtsp_ip}:${port})"
    done

    printf '\nversion: 0.15-1\n' >> "${config_file}"
}

configure_scenescape_setup() {

    if [ "${NVR_SCENESCAPE}" = "True" ] || [ "${NVR_SCENESCAPE}" = "true" ]; then
        print_info "NVR_SCENESCAPE is enabled - configuring Scenescape mode"

        local metro_recipe_dir
        metro_recipe_dir="$(cd .. && pwd)/metro-vision-ai-app-recipe"
        local rtsp_ip="${SI_RTSP_HOST:-$(get_host_ip)}"

        if [ "${SCENESCAPE_NVR_ONLY}" != "true" ]; then
            # Configure SI stack: compose + DLStreamer
            local dlstreamer_config="${metro_recipe_dir}/smart-intersection/src/dlstreamer-pipeline-server/config.json"
            cp "./resources/compose-scenescape-rtsp.yml" "${metro_recipe_dir}/compose-scenescape.yml"
            cp "./resources/si-rtsp-config.json" "${dlstreamer_config}"
            sed -i "s/{RTSP_STREAM_IP}/${rtsp_ip}/g" "${dlstreamer_config}"
            sed -i "s/{RTSP_STREAM_PORT}/${RTSP_STREAM_PORT}/g" "${dlstreamer_config}"
        fi

        if [ "${SCENESCAPE_SI_ONLY}" != "true" ]; then
            generate_scenescape_config
        fi

        print_success "Scenescape configuration activated"
    else
        print_info "NVR_SCENESCAPE is disabled - using default configuration"
        cp "./resources/frigate-config/config-default.yml" "./resources/frigate-config/config.yml"
        print_success "Default Frigate configuration activated"
    fi
}

configure_genai_setup() {
    if [ "${NVR_GENAI}" = "True" ] || [ "${NVR_GENAI}" = "true" ]; then
        print_info "Enabling GenAI detection in Frigate"
        
        if [ -f "./resources/frigate-config/config.yml" ]; then
            sed -i '/^\s*genai:/!b;n;s/enabled: false/enabled: true/' "./resources/frigate-config/config.yml"
            # Enable Detect - required for GenAI
            sed -i '/^\s*detect:/!b;n;s/enabled: false/enabled: true/' "./resources/frigate-config/config.yml"
            print_success "GenAI and Detection enabled in Frigate configuration"
        else
            print_error "Frigate config file not found at ./resources/frigate-config/config.yml"
            return 1
        fi
    else
        print_info "NVR_GENAI is disabled"
    fi
}

download_videos() {
    local video_dir="./resources/videos"
    local video_url="https://github.com/open-edge-platform/edge-ai-resources/raw/refs/heads/main/videos"
    local videos=(1122north_h264.ts 1122east_h264.ts 1122south_h264.ts 1122west_h264.ts)
    mkdir -p "$video_dir"
    local downloaded=false
    for video in "${videos[@]}"; do
        if [ ! -f "${video_dir}/${video}" ]; then
            print_info "Downloading ${video}..."
            if ! curl -fL "${video_url}/${video}" -o "${video_dir}/${video}"; then
                print_error "Failed to download ${video}"
                return 1
            fi
            downloaded=true
        fi
    done
    [[ "$downloaded" == true ]] && print_success "Demo videos downloaded" || print_info "Demo videos already present"
}

start_rtsp_streamer() {
    local videos=(1122north_h264.ts 1122east_h264.ts 1122south_h264.ts 1122west_h264.ts)
    for video in "${videos[@]}"; do
        if [ ! -f "./resources/videos/${video}" ]; then
            print_error "Missing video: ./resources/videos/${video}"
            return 1
        fi
    done
    print_info "Starting MediaMTX RTSP streamer on ${RTSP_STREAM_BIND_IP}:${RTSP_STREAM_PORT}"
    RTSP_STREAM_BIND_IP="$RTSP_STREAM_BIND_IP" RTSP_STREAM_PORT="$RTSP_STREAM_PORT" \
        docker compose -p smartnvr-mediamtx -f streamer/docker-compose.yml up -d
}

stop_rtsp_streamer() {
    if [ -f "streamer/docker-compose.yml" ]; then
        docker compose -p smartnvr-mediamtx -f streamer/docker-compose.yml down || true
    fi
}

start_scenescape() {
    local metro_recipe_dir
    metro_recipe_dir="$(cd .. && pwd)/metro-vision-ai-app-recipe"
    if [ ! -f "${metro_recipe_dir}/compose-scenescape.yml" ]; then
        print_error "Smart Intersection compose not found at ${metro_recipe_dir}"
        return 1
    fi
    if [ ! -f "${metro_recipe_dir}/smart-intersection/src/secrets/supass" ]; then
        (cd "${metro_recipe_dir}" && bash install.sh smart-intersection)
    fi
    docker compose -f "${metro_recipe_dir}/compose-scenescape.yml" --env-file "${metro_recipe_dir}/.env" up -d
}

stop_scenescape() {
    local metro_recipe_dir
    metro_recipe_dir="$(cd .. && pwd)/metro-vision-ai-app-recipe"
    if [ -f "${metro_recipe_dir}/compose-scenescape.yml" ]; then
        docker compose -f "${metro_recipe_dir}/compose-scenescape.yml" --env-file "${metro_recipe_dir}/.env" down || true
    fi
}

validate_environment() {
    if [ -z "${NVR_SCENESCAPE}" ]; then
        print_error "NVR_SCENESCAPE environment variable is required (true/false)"
        return 1
    fi

    if [ "${NVR_SCENESCAPE}" = "True" ] || [ "${NVR_SCENESCAPE}" = "true" ]; then
        if [ "${NVR_GENAI}" = "True" ] || [ "${NVR_GENAI}" = "true" ]; then
            print_error "NVR_GENAI cannot be enabled when NVR_SCENESCAPE is enabled"
            return 1
        fi
        export NVR_GENAI=false
    else
        if [ -z "${NVR_GENAI}" ]; then
            print_error "NVR_GENAI environment variable is required (true/false)"
            return 1
        fi
    fi

    # Check for VSS IP and port
    if [ -z "${VSS_SUMMARY_IP}" ]; then
        print_error "VSS_SUMMARY_IP environment variable is required"
        print_info "Please set it to the IP address of your Video Summarization Service"
        return 1
    fi

    if [ -z "${VSS_SUMMARY_PORT}" ]; then
        print_error "VSS_SUMMARY_PORT environment variable is required"
        print_info "Please set it to the port of your Video Summarization Service (typically 12345)"
        return 1
    fi
    if [ -z "${VSS_SEARCH_IP}" ]; then
        print_error "VSS_SEARCH_IP environment variable is required"
        print_info "Please set it to the IP address of your Video Search Service"
        return 1
    fi

    if [ -z "${VSS_SEARCH_PORT}" ]; then
        print_error "VSS_SEARCH_PORT environment variable is required"
        print_info "Please set it to the port of your Video Search Service (typically 12345)"
        return 1
    fi
    
    if [ "${NVR_GENAI}" = "True" ] || [ "${NVR_GENAI}" = "true" ]; then
        if [ -z "${VLM_SERVING_IP}" ]; then
            print_error "VLM_SERVING_IP environment variable is required when NVR_GENAI is enabled"
            print_info "Please set it to the IP address of your VLM Model Endpoint"
            return 1
        fi

        if [ -z "${VLM_SERVING_PORT}" ]; then
            print_error "VLM_SERVING_PORT environment variable is required when NVR_GENAI is enabled"
            print_info "Please set it to the port of your VLM Model Endpoint (typically 9766)"
            return 1
        fi
    fi
    # Resolve MQTT credentials — auto-generates if not provided by the user
    if ! resolve_mqtt_credentials; then
        print_error "Could not resolve MQTT credentials. Aborting."
        return 1
    fi
}

# Function to start the services
start_services() {
    print_header "Starting NVR Event Router Services"
    HOST_IP=$(get_host_ip)
    export HOST_IP
    # Validate environment variables and exit if validation fails
    if ! validate_environment; then
        print_error "Environment validation failed. Please set the required variables."
        return 1
    fi

    if ! configure_scenescape_setup; then
        return 1
    fi

    if [ "${NVR_SCENESCAPE}" = "True" ] || [ "${NVR_SCENESCAPE}" = "true" ]; then
        if ! download_videos; then
            return 1
        fi
        if ! start_rtsp_streamer; then
            return 1
        fi
        if ! start_scenescape; then
            return 1
        fi
    fi
    
    # Configure GenAI setup
    if ! configure_genai_setup; then
        return 1
    fi

    print_info "Starting Docker Compose services..."
    docker compose -f docker/compose.yaml up -d
    if [ $? -eq 0 ]; then
    sleep 5
    if [ "${NVR_SCENESCAPE}" = "True" ] || [ "${NVR_SCENESCAPE}" = "true" ]; then
        docker network connect metro-vision-ai-app-recipe_scenescape nvr-event-router 2>/dev/null || true
    fi
    sleep 5
    print_success "Services are starting up..."
    print_info "UI will be available at: ${CYAN}http://${HOST_IP}:7860${NC}"
    else
        print_error "Docker Compose failed to start services."
        return 1
    fi
}

# Function to stop the services
stop_services() {
    print_header "Stopping NVR Event Router Services"
    print_info "Stopping NVR Event Router services..."
    docker compose -f docker/compose.yaml down
    stop_scenescape
    stop_rtsp_streamer
    print_success "All services stopped."
}

# ─── Remote mode: distributed node deployment ────────────────────────────

start_si_services() {
    print_header "Starting SI (System 1 / SI-only mode)"
    if [ "${NVR_SCENESCAPE}" != "True" ] && [ "${NVR_SCENESCAPE}" != "true" ]; then
        print_error "start-si requires NVR_SCENESCAPE=true"
        print_info "Run: export NVR_SCENESCAPE=true"
        return 1
    fi
    HOST_IP=$(get_host_ip)
    export HOST_IP

    # Start local RTSP streamer only when no external stream source is provided and not already running
    local rtsp_host="${SI_RTSP_HOST:-}"
    if [ -z "${rtsp_host}" ] || [ "${rtsp_host}" = "${HOST_IP}" ] || [ "${rtsp_host}" = "localhost" ]; then
        if docker ps --filter "name=^mediamtx$" --filter "status=running" --format '{{.Names}}' | grep -q .; then
            print_info "Local RTSP streamer already running - skipping"
        else
            print_info "No external RTSP source set - starting local MediaMTX streamer"
            if ! download_videos; then
                return 1
            fi
            if ! start_rtsp_streamer; then
                return 1
            fi
        fi
    else
        print_info "External RTSP source detected (${rtsp_host}) - skipping local streamer"
    fi

    if ! SCENESCAPE_SI_ONLY=true configure_scenescape_setup; then
        return 1
    fi

    if ! start_scenescape; then
        return 1
    fi

    local nvr_rtsp_host="${rtsp_host:-${HOST_IP}}"
    print_success "SI services are running on System 1."
    echo ""
    print_info "System 1 IP: ${CYAN}${HOST_IP}${NC}"
    print_info "On System 2 (SmartNVR machine), run:"
    echo -e "  ${CYAN}export NVR_SCENESCAPE=true${NC}"
    echo -e "  ${CYAN}export VSS_SUMMARY_IP=<vss_ip>${NC}"
    echo -e "  ${CYAN}export VSS_SUMMARY_PORT=<vss_port>${NC}"
    echo -e "  ${CYAN}export VSS_SEARCH_IP=<vss_ip>${NC}"
    echo -e "  ${CYAN}export VSS_SEARCH_PORT=<vss_port>${NC}"
    echo -e "  ${CYAN}source setup.sh start-nvr${NC}   # will prompt for SI RTSP IP(s)"
    echo ""
    print_info "SI1 RTSP: ${CYAN}${nvr_rtsp_host}:${RTSP_STREAM_PORT}${NC}  |  SI1 MQTT: ${CYAN}${HOST_IP}:1883${NC}"
    print_info "On System 2, add the MQTT broker via POST /brokers/ API (or edit brokers.yaml before running start-nvr)."
    echo -e "  ${CYAN}# Optional: export SI_RTSP_HOST=${nvr_rtsp_host}   # skip si1 RTSP prompt${NC}"
    echo -e "  ${CYAN}# Optional: export RTSP_STREAM_PORT=<port>             # default ${RTSP_STREAM_PORT}${NC}"
}

stop_si_services() {
    print_header "Stopping SI (System 1)"
    stop_scenescape
    if docker ps --filter "name=^mediamtx$" --filter "status=running" --format '{{.Names}}' | grep -q .; then
        read -r -p "Local RTSP streamer is running. Stop it too? [y/N] " answer
        if [[ "${answer}" =~ ^[Yy]$ ]]; then
            stop_rtsp_streamer
            print_success "SI and RTSP streamer stopped."
        else
            print_info "RTSP streamer left running. Stop manually with: source setup.sh stop-streamer"
            print_success "SI services stopped."
        fi
    else
        print_success "SI services stopped."
    fi
}

start_nvr_services() {
    print_header "Starting SmartNVR (System 2 / NVR-only mode)"
    if [ "${NVR_SCENESCAPE}" != "True" ] && [ "${NVR_SCENESCAPE}" != "true" ]; then
        print_error "start-nvr requires NVR_SCENESCAPE=true"
        print_info "Run: export NVR_SCENESCAPE=true"
        return 1
    fi
    HOST_IP=$(get_host_ip)
    export HOST_IP

    if ! validate_environment; then
        print_error "Environment validation failed. Please set the required variables."
        return 1
    fi

    if ! SCENESCAPE_NVR_ONLY=true configure_scenescape_setup; then
        return 1
    fi

    if ! configure_genai_setup; then
        return 1
    fi

    print_info "Starting Docker Compose services..."
    docker compose -f docker/compose.yaml up -d
    if [ $? -eq 0 ]; then
        sleep 5
        print_success "SmartNVR services are starting up..."
        print_info "UI will be available at: ${CYAN}http://${HOST_IP}:7860${NC}"
        if [ -n "${SCENESCAPE_MQTT_BROKER}" ]; then
            print_info "MQTT broker seeded from env: ${SCENESCAPE_MQTT_BROKER}"
        else
            print_info "Add MQTT broker via POST /brokers/ API or edit resources/broker-config/brokers.yaml and restart."
        fi
    else
        print_error "Docker Compose failed to start services."
        return 1
    fi
}

stop_nvr_services() {
    print_header "Stopping SmartNVR (System 2)"
    docker compose -f docker/compose.yaml down
    print_success "SmartNVR services stopped."
}

# Function to display help
show_help() {
    print_header "NVR Event Router Setup Script"
    echo -e "${WHITE}Usage:${NC} $0 [command]"
    echo ""
    echo -e "${WHITE}Commands:${NC}"
    echo -e "  ${GREEN}start${NC}          - Single-node: start everything (RTSP + SI + Frigate + event router)"
    echo -e "  ${RED}stop${NC}           - Single-node: stop everything"
    echo -e "  ${YELLOW}restart${NC}        - Single-node: restart everything"
    echo -e "  ${GREEN}start-streamer${NC} - RTSP-only: start MediaMTX streamer "
    echo -e "  ${RED}stop-streamer${NC}  - RTSP-only: stop MediaMTX streamer"
  echo -e "  ${GREEN}start-si${NC}       - Distributed Node System 1: start SI services (starts local RTSP streamer unless SI_RTSP_HOST is set)"
  echo -e "  ${RED}stop-si${NC}        - Distributed Node System 1: stop SI services (prompts to stop local RTSP streamer if running)"
  echo -e "  ${GREEN}start-nvr${NC}      - Distributed Node System 2: start SmartNVR only (prompts for SI RTSP IP(s); MQTT broker via API or brokers.yaml)"
  echo -e "  ${RED}stop-nvr${NC}       - Distributed Node System 2: stop SmartNVR"
    echo -e "  ${BLUE}help${NC}           - Display this help message"
    echo ""
    echo -e "${WHITE}Examples:${NC}"
    echo -e "  ${CYAN}source setup.sh start${NC}          # Single-node: start all services"
    echo -e "  ${CYAN}source setup.sh stop${NC}           # Single-node: stop all services"
    echo -e "  ${CYAN}source setup.sh restart${NC}        # Single-node: restart all services"
    echo -e "  ${CYAN}source setup.sh start-streamer${NC} # RTSP-only: start MediaMTX streamer"
    echo ""
    echo -e "  # Distributed Node — System 1 (SI + RTSP):${NC}"
    echo -e "  ${CYAN}export NVR_SCENESCAPE=true${NC}"
    echo -e "  ${CYAN}source setup.sh start-si${NC}"
    echo ""
    echo -e "  # Distributed Node — System 2 (SmartNVR):${NC}"
    echo -e "  ${CYAN}export NVR_SCENESCAPE=true${NC}"
    echo -e "  ${CYAN}export VSS_SUMMARY_IP=<ip> VSS_SUMMARY_PORT=<port>${NC}"
    echo -e "  ${CYAN}export VSS_SEARCH_IP=<ip> VSS_SEARCH_PORT=<port>${NC}"
    echo -e "  ${CYAN}source setup.sh start-nvr${NC}   # prompts for SI RTSP IP(s) interactively"
    echo -e "  ${CYAN}# Optional: export SI_RTSP_HOST=<sys1_ip>  to skip si1 prompt${NC}"
    echo ""
}

# Main script logic
case "$1" in
    start-streamer)
        print_header "Starting RTSP Streamer"
        HOST_IP=$(get_host_ip)
        export HOST_IP
        if ! download_videos; then
            exit 1
        fi
        if ! start_rtsp_streamer; then
            exit 1
        fi
        print_success "RTSP streamer running on ${HOST_IP}:${RTSP_STREAM_PORT}"
        ;;
    stop-streamer)
        print_header "Stopping RTSP Streamer"
        stop_rtsp_streamer
        print_success "RTSP streamer stopped."
        ;;
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        print_header "Restarting NVR Event Router Services"
        stop_services
        sleep 5
        start_services
        ;;
    start-si)
        start_si_services
        ;;
    stop-si)
        stop_si_services
        ;;
    start-nvr)
        start_nvr_services
        ;;
    stop-nvr)
        stop_nvr_services
        ;;
    help|-h|--help)
        show_help
        ;;
    *)
        # Default behavior - show help
        show_help
        ;;
esac