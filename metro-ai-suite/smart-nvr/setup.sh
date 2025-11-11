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

# Function to configure Scenescape settings
configure_scenescape_setup() {
    print_info "Configuring Scenescape setup based on NVR_SCENESCAPE setting"
    
    if [ "${NVR_SCENESCAPE}" = "True" ] || [ "${NVR_SCENESCAPE}" = "true" ]; then
        print_info "NVR_SCENESCAPE is enabled - configuring Scenescape mode"
        
        # Configure Frigate with Scenescape cameras
        cp "./resources/frigate-config/config-scenescape.yml" "./resources/frigate-config/config.yml"
        
        # Substitute RTSP_STREAM_IP with host IP in the configuration
        local host_ip=$(get_host_ip)
        sed -i "s/{RTSP_STREAM_IP}/${host_ip}/g" "./resources/frigate-config/config.yml"
        print_success "Scenescape Frigate configuration activated"
        
        # Copy Scenescape certificates
        SMART_INTERSECTION_CERTS="edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/src/secrets/certs"
        if [ -f "${SMART_INTERSECTION_CERTS}/scenescape-ca.pem" ]; then
            mkdir -p ./resources/mqtt-certs
            chmod u+w ./resources/mqtt-certs
            cp "${SMART_INTERSECTION_CERTS}/scenescape-ca.pem" "./resources/mqtt-certs/root-cert"
            cp "${SMART_INTERSECTION_CERTS}/scenescape-broker.crt" "./resources/mqtt-certs/broker-cert"
            cp "${SMART_INTERSECTION_CERTS}/scenescape-broker.key" "./resources/mqtt-certs/broker-key"
            print_success "Scenescape certificates copied successfully"
        else
            print_error "Scenescape is enabled but certificates not found at ${SMART_INTERSECTION_CERTS}"
            print_info "Please ensure Smart Intersection application is running and certificates are generated"
            return 1
        fi
    else
        print_info "NVR_SCENESCAPE is disabled - using default configuration"
        cp "./resources/frigate-config/config-default.yml" "./resources/frigate-config/config.yml"
        print_success "Default Frigate configuration activated"
    fi
}

# Function to validate required environment variables
validate_environment() {    
    # Check for NVR_GENAI flag
    if [ -z "${NVR_GENAI}" ]; then
        print_error "NVR_GENAI environment variable is required"
        print_info "Please set it to 'true' or 'false' to enable/disable NVR GenAI features"
        return 1
    fi
    if [ -z "${NVR_SCENESCAPE}" ]; then
        print_error "NVR_SCENESCAPE environment variable is required"
        print_info "Please set it to 'true' or 'false' to enable/disable NVR SceneScape features"
        return 1
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
    # Check for VSS IP and port
    if [ -z "${VSS_SEARCH_IP}" ]; then
        print_error "VSS_SEARCH_IP environment variable is required"
        print_info "Please set it to the IP address of your Video Summarization Service"
        return 1
    fi
    
    if [ -z "${VSS_SEARCH_PORT}" ]; then
        print_error "VSS_SEARCH_PORT environment variable is required"
        print_info "Please set it to the port of your Video Summarization Service (typically 12345)"
        return 1
    fi
    
    # Check for VLM Model Endpoint IP and port
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
    # Check for SceneScape MQTT settings if enabled
    if [ "${NVR_SCENESCAPE}" = "True" ] || [ "${NVR_SCENESCAPE}" = "true" ]; then
        if [ -z "${SCENESCAPE_MQTT_USER}" ]; then
            print_error "SCENESCAPE_MQTT_USER environment variable is required when NVR_SCENESCAPE is enabled"
            print_info "Please set it to the MQTT username for SceneScape"
            return 1
        fi

        if [ -z "${SCENESCAPE_MQTT_PASSWORD}" ]; then
            print_error "SCENESCAPE_MQTT_PASSWORD environment variable is required when NVR_SCENESCAPE is enabled"
            print_info "Please set it to the MQTT password for SceneScape"
            return 1
        fi
    fi    
    # Check for MQTT user and password
    if [ -z "${MQTT_USER}" ]; then
        print_error "MQTT_USER environment variable is required"
        return 1
    fi
    
    if [ -z "${MQTT_PASSWORD}" ]; then
        print_error "MQTT_PASSWORD environment variable is required"
        return 1
    fi
}

# Function to start the services
start_services() {
    print_header "Starting NVR Event Router Services"
    HOST_IP=$(get_host_ip)
    export HOST_IP=$(get_host_ip)
    # Validate environment variables and exit if validation fails
    if ! validate_environment; then
        print_error "Environment validation failed. Please set the required variables."
        return 1
    fi
    
    # Configure Scenescape setup (config and certificates)
    if ! configure_scenescape_setup; then
        return 1
    fi
    
    print_info "Starting Docker Compose services..."
    # Run the Docker Compose stack with all services
    docker compose -f docker/compose.yaml up -d 
    if [ $? -eq 0 ]; then
    sleep 5
    print_success "Services are starting up..."
    print_info "UI will be available at: ${CYAN}http://${HOST_IP}:7860${NC}"
    else
        print_error "Docker Compose failed to start services."
        exit 1
    fi

}

# Function to stop the services
stop_services() {
    print_header "Stopping NVR Event Router Services"
    print_info "Stopping NVR Event Router services..."
    docker compose -f docker/compose.yaml down

    print_success "All services stopped."
}

# Function to display help
show_help() {
    print_header "NVR Event Router Setup Script"
    echo -e "${WHITE}Usage:${NC} $0 [command]"
    echo ""
    echo -e "${WHITE}Commands:${NC}"
    echo -e "  ${GREEN}start${NC}    - Start all services"
    echo -e "  ${RED}stop${NC}     - Stop all services"
    echo -e "  ${YELLOW}restart${NC}  - Restart all services"
    echo -e "  ${BLUE}help${NC}     - Display this help message"
    echo ""
    echo -e "${WHITE}Examples:${NC}"
    echo -e "  ${CYAN}source setup.sh start${NC}     # Start the services"
    echo -e "  ${CYAN}source setup.sh stop${NC}      # Stop the services"
    echo -e "  ${CYAN}source setup.sh restart${NC}   # Restart the services"
    echo ""
}

# Main script logic
case "$1" in
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
    help|-h|--help)
        show_help
        ;;
    *)
        # Default behavior - show help
        show_help
        ;;
esac