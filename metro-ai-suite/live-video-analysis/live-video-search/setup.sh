#!/bin/bash

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

LIVE_SEARCH_ROOT=$(pwd)
METRO_ROOT=${METRO_ROOT:-$(cd "${LIVE_SEARCH_ROOT}/../.." && pwd)}

CONFIG_DIR=${LIVE_SEARCH_ROOT}/config
export NGINX_CONFIG=${CONFIG_DIR}/nginx.conf
export LIVE_SEARCH_CONFIG_DIR=${CONFIG_DIR}

get_host_ip() {
    if command -v ip &> /dev/null; then
        HOST_IP=$(ip route get 1 | sed -n 's/^.*src \([0-9.]*\) .*$/\1/p')
    elif command -v ifconfig &> /dev/null; then
        HOST_IP=$(ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -n 1)
    else
        HOST_IP=$(hostname -I | awk '{print $1}')
    fi

    if [ -z "$HOST_IP" ]; then
        HOST_IP="localhost"
    fi

    echo "$HOST_IP"
}

stop_containers() {
    echo -e "${YELLOW}Bringing down the Docker containers... ${NC}"
    docker compose \
      -f docker/compose.search.yaml \
      -f docker/compose.smart-nvr.yaml \
            -f docker/compose.telemetry.yaml \
            -f docker/compose.rtsp-test.yaml \
      down
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Failed to stop and remove containers.${NC}"
        return 1
    fi
    echo -e "${GREEN}All containers were successfully stopped and removed. ${NC}"
    return 0
}

if [ "$1" = "--start" ]; then
    if [ -n "$2" ]; then
        set -- "--start" "$2"
    else
        set -- "--start"
    fi
elif [ "$1" = "--start-rtsp-test" ]; then
    if [ -n "$2" ]; then
        set -- "--start-rtsp-test" "$2"
    else
        set -- "--start-rtsp-test"
    fi
elif [ "$1" = "--start-usb-camera" ]; then
    if [ -n "$2" ]; then
        set -- "--start-usb-camera" "$2"
    else
        set -- "--start-usb-camera"
    fi
fi

if [ "$#" -eq 0 ] || ([ "$#" -eq 1 ] && [ "$1" = "--help" ]); then
    echo -e "-----------------------------------------------------------------"
    echo -e "${YELLOW}USAGE: ${GREEN}source setup.sh ${BLUE}[--setenv | --down | --clean-data | --help | --start | --start-rtsp-test | --start-usb-camera ${GREEN}[config]${BLUE}]"
    echo -e "${YELLOW}"
    echo -e "  --setenv:     Set environment variables without starting containers"
    echo -e "  --start:      Configure and bring up Live Video Search application"
    echo -e "  --start-rtsp-test: Start app plus RTSP test stream (looped sample video)"
    echo -e "  --start-usb-camera: Start app with USB camera input (/dev/video0)"
    echo -e "  --down:       Bring down all docker containers for the application"
    echo -e "  --clean-data: Bring down containers and remove docker volumes"
    echo -e "  --help:       Show this help message"
    echo -e "  config:       Optional argument to print the resolved compose config"
    echo -e "-----------------------------------------------------------------"
    return 0
elif [ "$#" -gt 2 ]; then
    echo -e "${RED}ERROR: Too many arguments provided.${NC}"
    return 1
elif [ "$1" != "--help" ] && [ "$1" != "--start" ] && [ "$1" != "--start-rtsp-test" ] && [ "$1" != "--start-usb-camera" ] && [ "$1" != "--setenv" ] && [ "$1" != "--down" ] && [ "$1" != "--clean-data" ]; then
    echo -e "${RED}Unknown option: $1 ${NC}"
    return 1
elif [ "$#" -eq 2 ] && [ "$2" != "config" ]; then
    echo -e "${RED}Unknown second argument: $2${NC}"
    return 1
elif [ "$1" = "--down" ]; then
    stop_containers
    return $?
elif [ "$1" = "--clean-data" ]; then
    stop_containers || return 1
    echo -e "${YELLOW}Removing Docker volumes created by the application... ${NC}"
    docker volume rm docker_minio_data docker_pg_data docker_vdms_db docker_data_prep docker_mosquitto_data docker_mosquitto_log docker_redis_data docker_frigate_recordings docker_collector_signals data-prep minikube 2>/dev/null || true
    echo -e "${GREEN}Clean operation completed successfully! ${NC}"
    return 0
fi

export APP_HOST_PORT=${APP_HOST_PORT:-12345}
export HOST_IP=$(get_host_ip)
export TAG=${TAG:-latest}

[[ -n "$REGISTRY_URL" ]] && REGISTRY_URL="${REGISTRY_URL%/}/"
[[ -n "$PROJECT_NAME" ]] && PROJECT_NAME="${PROJECT_NAME%/}/"
export REGISTRY="${REGISTRY_URL}${PROJECT_NAME}"

export USER_GROUP_ID=$(id -g)
export VIDEO_GROUP_ID=$(getent group video | awk -F: '{printf "%s\n", $3}')
export RENDER_GROUP_ID=$(getent group render | awk -F: '{printf "%s\n", $3}')

# VSS service endpoints
export PM_HOST_PORT=${PM_HOST_PORT:-3001}
export PM_HOST=${PM_HOST:-pipeline-manager}
export PM_MINIO_BUCKET=${PM_MINIO_BUCKET:-video-summary}
export UI_HOST_PORT=${UI_HOST_PORT:-9998}
export UI_PM_ENDPOINT=${UI_PM_ENDPOINT:-/manager}
export UI_ASSETS_ENDPOINT=${UI_ASSETS_ENDPOINT:-/datastore}
export SUMMARY_FEATURE=${SUMMARY_FEATURE:-FEATURE_OFF}
export SEARCH_FEATURE=${SEARCH_FEATURE:-FEATURE_ON}
export APP_FEATURE_MUX=${APP_FEATURE_MUX:-ATOMIC}
export CONFIG_SOCKET_APPEND=${CONFIG_SOCKET_APPEND:-CONFIG_OFF}

# Optional hosts used in proxy bypass lists
export EVAM_HOST=${EVAM_HOST:-video-ingestion}
export VLM_HOST=${VLM_HOST:-vlm-openvino-serving}
export AUDIO_HOST=${AUDIO_HOST:-audio-analyzer}
export RABBITMQ_HOST=${RABBITMQ_HOST:-rabbitmq-service}
export OVMS_HOST=${OVMS_HOST:-ovms-service}

# MinIO / Postgres
export MINIO_API_HOST_PORT=${MINIO_API_HOST_PORT:-4001}
export MINIO_CONSOLE_HOST_PORT=${MINIO_CONSOLE_HOST_PORT:-4002}
export MINIO_HOST=${MINIO_HOST:-minio-service}
export POSTGRES_HOST_PORT=${POSTGRES_HOST_PORT:-5432}
export POSTGRES_HOST=${POSTGRES_HOST:-postgres-service}
export POSTGRES_DB=${POSTGRES_DB:-video_summary_db}

# VSS Search
export VS_HOST_PORT=${VS_HOST_PORT:-7890}
export VS_HOST=${VS_HOST:-video-search}
export VS_ENDPOINT=http://${VS_HOST}:8000
export VDMS_PIPELINE_MANAGER_UPLOAD=http://${PM_HOST}:3000
export VS_INDEX_NAME=${VS_INDEX_NAME:-video_frame_embeddings}

# VDMS / Embeddings
export VDMS_VDB_HOST_PORT=${VDMS_VDB_HOST_PORT:-55555}
export VDMS_VDB_HOST=${VDMS_VDB_HOST:-vdms-vector-db}
export VDMS_DATAPREP_HOST_PORT=${VDMS_DATAPREP_HOST_PORT:-6016}
export VDMS_DATAPREP_HOST=${VDMS_DATAPREP_HOST:-vdms-dataprep}
export VDMS_DATAPREP_ENDPOINT=http://${VDMS_DATAPREP_HOST}:8000
export DEFAULT_BUCKET_NAME=${DEFAULT_BUCKET_NAME:-vdms-bucket}
export FRAME_INTERVAL=${FRAME_INTERVAL:-15}
export ENABLE_OBJECT_DETECTION=${ENABLE_OBJECT_DETECTION:-true}
export DETECTION_CONFIDENCE=${DETECTION_CONFIDENCE:-0.85}
export ROI_CONSOLIDATION_ENABLED=${ROI_CONSOLIDATION_ENABLED:-false}
export ROI_CONSOLIDATION_IOU_THRESHOLD=${ROI_CONSOLIDATION_IOU_THRESHOLD:-0.2}
export ROI_CONSOLIDATION_CLASS_AWARE=${ROI_CONSOLIDATION_CLASS_AWARE:-false}
export ROI_CONSOLIDATION_CONTEXT_SCALE=${ROI_CONSOLIDATION_CONTEXT_SCALE:-0.2}
export FRAMES_TEMP_DIR=${FRAMES_TEMP_DIR:-/tmp/dataprep}
export EMBEDDING_PROCESSING_MODE=${EMBEDDING_PROCESSING_MODE:-sdk}
export SDK_USE_OPENVINO=${SDK_USE_OPENVINO:-true}
export EMBEDDING_SERVER_PORT=${EMBEDDING_SERVER_PORT:-9777}
export MULTIMODAL_EMBEDDING_HOST=${MULTIMODAL_EMBEDDING_HOST:-multimodal-embedding-serving}
export MULTIMODAL_EMBEDDING_ENDPOINT=${MULTIMODAL_EMBEDDING_ENDPOINT:-http://${MULTIMODAL_EMBEDDING_HOST}:8000/embeddings}
export EMBEDDING_USE_OV=${EMBEDDING_USE_OV:-$SDK_USE_OPENVINO}
export OV_MODELS_DIR=${OV_MODELS_DIR:-/app/ov_models}
export EMBEDDING_OV_MODELS_DIR=${EMBEDDING_OV_MODELS_DIR:-$OV_MODELS_DIR}
export DEFAULT_START_OFFSET_SEC=${DEFAULT_START_OFFSET_SEC:-0}
export DEFAULT_CLIP_DURATION=${DEFAULT_CLIP_DURATION:--1}
export DEFAULT_NUM_FRAMES=${DEFAULT_NUM_FRAMES:-64}
export OV_PERFORMANCE_MODE=${OV_PERFORMANCE_MODE:-THROUGHPUT}
# export OV_PERFORMANCE_MODE=${OV_PERFORMANCE_MODE:-LATENCY}

# Aggregation defaults
export AGGREGATION_ENABLED=${AGGREGATION_ENABLED:-true}
export AGGREGATION_SEGMENT_DURATION=${AGGREGATION_SEGMENT_DURATION:-8}
export AGGREGATION_MIN_GAP=${AGGREGATION_MIN_GAP:-0}
export AGGREGATION_MAX_RESULTS=${AGGREGATION_MAX_RESULTS:-20}
export AGGREGATION_INITIAL_K=${AGGREGATION_INITIAL_K:-1000}
export AGGREGATION_CONTEXT_SEEK_OFFSET_SECONDS=${AGGREGATION_CONTEXT_SEEK_OFFSET_SECONDS:-0}

# Device selection (CPU/GPU for embeddings)
export VDMS_DATAPREP_DEVICE=${VDMS_DATAPREP_DEVICE:-""}
export EMBEDDING_DEVICE=${EMBEDDING_DEVICE:-""}

if [ -n "$EMBEDDING_DEVICE" ] && [ -z "$VDMS_DATAPREP_DEVICE" ]; then
    export VDMS_DATAPREP_DEVICE="$EMBEDDING_DEVICE"
elif [ -z "$EMBEDDING_DEVICE" ]; then
    export EMBEDDING_DEVICE="$VDMS_DATAPREP_DEVICE"
fi

if [ "$ENABLE_EMBEDDING_GPU" = true ]; then
    export VDMS_DATAPREP_DEVICE=GPU
    export EMBEDDING_DEVICE=GPU
fi

configure_device() {
    local device=${1:-"CPU"}

    echo -e "${BLUE}Configuring device for embedding + dataprep: ${YELLOW}${device}${NC}"

    if [[ "${device}" == GPU* ]]; then
        echo -e "${YELLOW}⚙️  Setting up GPU configuration...${NC}"

        if ! lspci | grep -i "vga.*intel" > /dev/null 2>&1; then
            echo -e "${RED}Warning: No Intel GPU detected. GPU mode may not work properly.${NC}"
        else
            echo -e "${GREEN}Intel GPU detected${NC}"
        fi

        if [[ ! -d "/dev/dri" ]]; then
            echo -e "${RED}Warning: /dev/dri not found. GPU acceleration may not be available.${NC}"
        else
            echo -e "${GREEN}DRI devices found for GPU acceleration${NC}"
        fi

        export VDMS_DATAPREP_DEVICE="${device}"
        export EMBEDDING_DEVICE="${device}"
        export SDK_USE_OPENVINO=true
    else
        echo -e "${BLUE}CPU mode configured for embedding + dataprep${NC}"
        export VDMS_DATAPREP_DEVICE="${device}"
        export EMBEDDING_DEVICE="${device}"
    fi
}

if [ -z "$VDMS_DATAPREP_DEVICE" ] && [ -z "$EMBEDDING_DEVICE" ]; then
    configure_device "CPU"
elif [[ "${VDMS_DATAPREP_DEVICE}" == GPU* ]] || [[ "${EMBEDDING_DEVICE}" == GPU* ]]; then
    configure_device "GPU"
else
    configure_device "CPU"
fi

# YOLOX models
export YOLOX_MODELS_VOLUME_NAME=${YOLOX_MODELS_VOLUME_NAME:-vdms-yolox-models}
export YOLOX_MODELS_MOUNT_PATH=${YOLOX_MODELS_MOUNT_PATH:-/app/models/yolox}

# Smart NVR settings
if [ -z "${MQTT_USER}" ] || [ -z "${MQTT_PASSWORD}" ]; then
    echo -e "${RED}ERROR: MQTT_USER and MQTT_PASSWORD must be set.${NC}"
    return 1
fi
export MQTT_USER=${MQTT_USER}
export MQTT_PASSWORD=${MQTT_PASSWORD}
export VLM_SERVING_IP=${VLM_SERVING_IP:-${PM_HOST}}
export VLM_SERVING_PORT=${VLM_SERVING_PORT:-9766}
export VSS_SEARCH_IP=${VSS_SEARCH_IP:-nginx}
export VSS_SUMMARY_IP=${VSS_SUMMARY_IP:-nginx}
export VSS_SEARCH_PORT=${VSS_SEARCH_PORT:-80}
export VSS_SUMMARY_PORT=${VSS_SUMMARY_PORT:-80}
export VSS_SEARCH_URL=http://${VSS_SEARCH_IP}:${VSS_SEARCH_PORT}
export VSS_SUMMARY_URL=http://${VSS_SUMMARY_IP}:${VSS_SUMMARY_PORT}
export FRIGATE_BASE_URL=${FRIGATE_BASE_URL:-http://frigate-vms:5000}
export NVR_API_BASE_URL=${NVR_API_BASE_URL:-http://nvr-event-router:8000}


if [ "$1" = "--start" ] || [ "$1" = "--start-rtsp-test" ] || [ "$1" = "--start-usb-camera" ]; then
    export HOST_IP=$(get_host_ip)
    if [ "$1" = "--start" ]; then
        cp "${CONFIG_DIR}/frigate-config/config-default.yml" "${CONFIG_DIR}/frigate-config/config.yml"
    elif [ "$1" = "--start-rtsp-test" ]; then
        cp "${CONFIG_DIR}/frigate-config/config-rtsp.yml" "${CONFIG_DIR}/frigate-config/config.yml"
        if ! docker network inspect live-video-network >/dev/null 2>&1; then
            docker network create live-video-network
        fi
    elif [ "$1" = "--start-usb-camera" ]; then
        cp "${CONFIG_DIR}/frigate-config/config-usb.yml" "${CONFIG_DIR}/frigate-config/config.yml"
    fi
fi

if [ "$1" = "--setenv" ]; then
    echo -e "${BLUE}Done setting up environment variables.${NC}"
    return 0
fi

APP_COMPOSE_FILE="-f docker/compose.search.yaml -f docker/compose.smart-nvr.yaml -f docker/compose.telemetry.yaml"
if [ "$1" = "--start-rtsp-test" ]; then
    APP_COMPOSE_FILE="$APP_COMPOSE_FILE -f docker/compose.rtsp-test.yaml"
elif [ "$1" = "--start-usb-camera" ]; then
    APP_COMPOSE_FILE="$APP_COMPOSE_FILE -f docker/compose.usb-camera.yaml"
fi
FINAL_ARG="up -d" && [ "$2" = "config" ] && FINAL_ARG="config"
DOCKER_COMMAND="docker compose $APP_COMPOSE_FILE $FINAL_ARG"

echo -e "${GREEN}Running Docker command: $DOCKER_COMMAND ${NC}"

if [ "$2" = "config" ]; then
    eval "$DOCKER_COMMAND"
    return $?
fi

eval "$DOCKER_COMMAND"
if [ $? -ne 0 ]; then
    echo -e "\n${RED}Failed: Some error occurred while setting up containers.${NC}"
    return 1
fi

echo -e "\n${GREEN}Setup completed successfully!"
echo -e "${GREEN}Access the VSS UI at: ${YELLOW}http://${HOST_IP}:${APP_HOST_PORT}${NC}"
echo -e "${GREEN}Access Smart NVR UI at: ${YELLOW}http://${HOST_IP}:7860${NC}"
