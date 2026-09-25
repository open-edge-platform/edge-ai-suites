#!/bin/bash

# Copyright (C) 2026 Intel Corporation
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

# When the opt-in demo flow (STIA_DEMO_INTERSECTION) is set and that intersection
# ships its own deployment_instance.json (name/lat/long) under the overrides dir,
# prefer it over the default deployment_instance.json so each demo intersection
# reports its own identity/coordinates instead of inheriting intersection_1's.
STIA_DEMO_DEPLOYMENT_CONFIG="$APP_DIR/src/config/smart-intersection-overrides/${STIA_DEMO_INTERSECTION}/deployment_instance.json"
if [ -n "$STIA_DEMO_INTERSECTION" ] && [ -f "$STIA_DEMO_DEPLOYMENT_CONFIG" ]; then
    DEPLOYMENT_CONFIG="$STIA_DEMO_DEPLOYMENT_CONFIG"
fi

# set agent instance specific environment variables based on deployment_instance.json.
# Precedence: if the opt-in demo flow (STIA_DEMO_INTERSECTION) is set, its value
# scopes this deployment's PROJECT_NAME/container/network names so it runs as an
# independent stack instead of reusing/restarting deployment_instance.json's default
# "intersection_1" stack; otherwise fall back to deployment_instance.json's "name"
# (unchanged default behavior). Always recomputed (not "${INTERSECTION_NAME:-...}")
# because this script is meant to be `source`d: exported vars from a prior run in
# the same shell would otherwise stick around and mask a newly-set
# STIA_DEMO_INTERSECTION on a later `source setup.sh` call in that same shell.
if [ -n "$STIA_DEMO_INTERSECTION" ]; then
    export INTERSECTION_NAME="$STIA_DEMO_INTERSECTION"
else
    export INTERSECTION_NAME="$(grep -oP '"name"\s*:\s*"\K[^"]+' "$DEPLOYMENT_CONFIG")"
fi
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
export STIA_OVERRIDES_DIR="${APP_DIR}/src/config/smart-intersection-overrides"
export SI_SETUP_REPO_URL="${SI_SETUP_REPO_URL:-https://github.com/svamsik/edge-ai-suites.git}"
export SI_SETUP_BRANCH="${SI_SETUP_BRANCH:-svamsik/si-rtsp-config}"
export RTSP_STREAM_IP="${RTSP_STREAM_IP:-${SI_RTSP_HOST:-}}"
export RTSP_STREAM_PORT="${RTSP_STREAM_PORT:-8554}"

# Opt-in demo/synthetic-data flow: unset by default, so the standard STIA
# flow (RI's own default scene + DLSPS config, no RTSP source required) is
# completely untouched. When set to a known intersection name (e.g.
# "intersection_1", matching a subdirectory under STIA_OVERRIDES_DIR and a
# video-file prefix at the download URL below), setup.sh will additionally:
#   1. download that intersection's 4 demo videos,
#   2. apply its Scenescape scene bundle + DLSPS pipeline config overrides,
#   3. start a local RTSP streamer built into STIA (docker/streamer-compose.yaml)
#      unless RTSP_STREAM_IP/SI_RTSP_HOST already points at an external source,
#   4. start the RTSP-backed DLSPS pipelines against it.
export STIA_DEMO_INTERSECTION="${STIA_DEMO_INTERSECTION:-}"
export STIA_DEMO_VIDEO_URL="${STIA_DEMO_VIDEO_URL:-https://github.com/open-edge-platform/edge-ai-resources/raw/refs/heads/main/videos/synthetic_data}"
export STIA_DEMO_VIDEOS_DIR="${APP_DIR}/resources/videos"

if [ "$ENABLE_TC" = "true" ]; then
    TC_OVERLAY_AGENT="-f ${APP_DIR}/docker/tc-overlay-agent.yaml"
    if [ "$VLM_TARGET_DEVICE" = "GPU" ]; then
        # Run GPU validation only for runtime commands (--setup, --run, --restart)
        if [ "$1" = "--setup" ] || [ "$1" = "--run" ] || [ "$1" = "--restart" ]; then
            GPU_PCI_FULL=$(lspci -Dnn | grep -E '(VGA compatible controller|Display controller).*Intel' | head -1 | awk '{print $1}')
            if [ -z "$GPU_PCI_FULL" ]; then
                echo -e "${RED}ERROR: No Intel iGPU found for VFIO passthrough.${NC}"
                return 1
            fi
            IOMMU_LINK="/sys/bus/pci/devices/${GPU_PCI_FULL}/iommu_group"
            if [ ! -L "$IOMMU_LINK" ]; then
                echo -e "${RED}ERROR: No IOMMU group found for ${GPU_PCI_FULL}. Ensure IOMMU is enabled.${NC}"
                return 1
            fi
            export TC_GPU_VFIO_GROUP=$(basename "$(readlink -f "$IOMMU_LINK")")
            if [ ! -e "/dev/vfio/${TC_GPU_VFIO_GROUP}" ]; then
                echo -e "${RED}ERROR: GPU (${GPU_PCI_FULL}) is not bound to vfio-pci driver.${NC}"
                return 1
            fi
        fi
        TC_OVERLAY_AGENT="${TC_OVERLAY_AGENT} -f ${APP_DIR}/docker/tc-gpu-overlay-agent.yaml"
    elif [[ "${TC_SI_TARGET_DEVICE:-CPU}" == "GPU" || "${TC_SI_TARGET_DEVICE:-CPU}" == "NPU" ]] && [ "${VLM_TARGET_DEVICE:-CPU}" = "CPU" ]; then
        # SI device is passed through via VFIO; /dev/dri is unavailable on the host.
        TC_OVERLAY_AGENT="${TC_OVERLAY_AGENT} -f ${APP_DIR}/docker/tc-si-device-overlay-agent.yaml"
    fi
else
    TC_OVERLAY_AGENT="";
fi

# Setting command usage and invalid arguments handling before the actual setup starts
if [ "$#" -eq 0 ] || ([ "$#" -eq 1 ] && [ "$1" = "--help" ]); then
    # If no valid argument is passed, print usage information
    echo -e "-----------------------------------------------------------------"
    echo -e "${YELLOW}USAGE: ${GREEN}source setup.sh ${BLUE}[--setenv | --setup | --run | --restart [agent|deps|all] | --stop | --clean | --help]"
    echo -e "${YELLOW}"
    echo -e "  --setenv:                 Set environment variables without building image or starting any containers"
    echo -e "                              • RTSP_STREAM_IP or SI_RTSP_HOST enables RTSP-backed Smart Intersection pipelines"
    echo -e "                              • RTSP_STREAM_PORT sets the RTSP server port (default: 8554)"
    echo -e "                              • STIA_DEMO_INTERSECTION=<name> (e.g. intersection_1) opts into the full"
    echo -e "                                self-contained demo flow: downloads that intersection's videos, applies"
    echo -e "                                its scene/DLSPS overrides, and starts a local RTSP streamer automatically"
    echo -e "                                unless RTSP_STREAM_IP/SI_RTSP_HOST already points at an external source."
    echo -e "                                Unset (default): standard flow, no RTSP source required."
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

    # Stop STIA's own local RTSP streamer, if it was ever started for the
    # opt-in demo flow (STIA_DEMO_INTERSECTION). Inlined here (rather than
    # calling stop_stia_rtsp_streamer(), defined later in this file) since
    # this early --stop/--clean branch runs and returns before later
    # function definitions are sourced. Safe/no-op if it was never started.
    if [ -n "$STIA_DEMO_INTERSECTION" ] && [ -f "${APP_DIR}/docker/streamer-compose.yaml" ]; then
        docker compose --project-directory "$APP_DIR" -f "${APP_DIR}/docker/streamer-compose.yaml" -p "${PROJECT_NAME}-streamer" down 2>/dev/null || true
    fi

    # check if ri-compose.yaml exists and run docker compose down accordingly
    if [ -L "${APP_DIR}/docker/ri-compose.yaml" ]; then
        docker compose --project-directory "$DEPS_DIR" -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" $TC_OVERLAY_AGENT -p ${PROJECT_NAME} down
    else
        docker compose -f "${APP_DIR}/docker/agent-compose.yaml" $TC_OVERLAY_AGENT -p ${PROJECT_NAME} down 2> /dev/null
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
                # Model files may be root-owned (created inside Docker container).
                # Fix ownership first so rm -rf can delete them.
                docker run --rm -v "${OVMS_CONFIG_DIR}:/ovms_dir" busybox chown -R "$(id -u):$(id -g)" /ovms_dir 2>/dev/null || true
                rm -rf "${OVMS_CONFIG_DIR}"
            fi
        fi
        if [ -d "${APP_DIR}/.model_download_logs" ]; then
            echo -e "${YELLOW}Removing model download logs (${APP_DIR}/.model_download_logs) ... ${NC}"
            rm -rf "${APP_DIR}/.model_download_logs"
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

        rm -f "${APP_DIR}/docker/tc-resolv.conf" 2>/dev/null || true
        rm -f "${APP_DIR}/deps/metro-vision/metro-ai-suite/metro-vision-ai-app-recipe/tc-resolv.conf" 2>/dev/null || true

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

# Copy tracked site-specific Smart Intersection overrides (DL Streamer Pipeline Server
# config and Scenescape scene bundle) into the vendored RI dependency. These live under
# version-controlled $STIA_OVERRIDES_DIR/$STIA_DEMO_INTERSECTION (not in deps/metro-vision,
# which is gitignored and recreated on every re-clone/upgrade). Opt-in only: no-op unless
# STIA_DEMO_INTERSECTION is set, so the standard flow keeps the RI's own default scene/config.
#
# Each intersection's overrides are a flat directory containing exactly one *.json
# (DLSPS pipeline config) and one *.tar.bz2 (Scenescape scene bundle), e.g.
# intersection_1/intersection_1.json + intersection_1/Intersection_1.tar.bz2. File name
# casing is not significant; the files are located by extension via glob.
apply_stia_overrides() {
    if [ -z "$STIA_DEMO_INTERSECTION" ]; then
        return 0
    fi

    local overrides_dir="${STIA_OVERRIDES_DIR}/${STIA_DEMO_INTERSECTION}"
    local dlsps_config_dst="${RI_DIR}/src/dlstreamer-pipeline-server/config.json"
    local scene_dst="${RI_DIR}/src/webserver/smart-intersection-ri.tar.bz2"
    local dlsps_config_src=""
    local scene_src=""
    local match

    if [ -d "$overrides_dir" ]; then
        for match in "$overrides_dir"/*.json; do
            [ -f "$match" ] && dlsps_config_src="$match" && break
        done
        for match in "$overrides_dir"/*.tar.bz2; do
            [ -f "$match" ] && scene_src="$match" && break
        done
    fi

    if [ -z "$dlsps_config_src" ] && [ -z "$scene_src" ]; then
        echo -e "${RED}ERROR: No Smart Intersection overrides tracked for STIA_DEMO_INTERSECTION='${STIA_DEMO_INTERSECTION}' under ${overrides_dir}.${NC}"
        return 1
    fi

    echo -e "${BLUE}==> Applying Smart Intersection overrides for '${STIA_DEMO_INTERSECTION}' from ${overrides_dir} ...${NC}"


    if [ -f "$dlsps_config_src" ]; then
        cp -f "$dlsps_config_src" "$dlsps_config_dst" || {
            echo -e "${RED}ERROR: Failed to apply DL Streamer Pipeline Server config override.${NC}"
            return 1
        }
        echo -e "${GREEN}Applied DL Streamer Pipeline Server config override.${NC}"
    fi

    if [ -f "$scene_src" ]; then
        cp -f "$scene_src" "$scene_dst" || {
            echo -e "${RED}ERROR: Failed to apply Scenescape scene bundle override.${NC}"
            return 1
        }
        echo -e "${GREEN}Applied Scenescape scene bundle override.${NC}"
    fi
}

# Verify if dependencies are setup; if not, clone the required dependency and run install script
check_and_setup_dependencies() {
    echo -e "${BLUE}==> Setting up required dependencies ...${NC}"

    if [ ! -d "$DEPS_DIR" ]; then
        # Run git clone to fetch the dependencies (sparse, shallow)
        echo -e "${YELLOW}Dependencies not found. Cloning repository...${NC}"
        git clone --filter=blob:none --sparse --depth 1 \
            --branch "$SI_SETUP_BRANCH" \
            "$SI_SETUP_REPO_URL" \
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

    apply_stia_overrides || return 1

    # Create symbolic link to compose-scenescape.yml in docker dir of agent application
    rm "$APP_DIR/docker/ri-compose.yaml" 2> /dev/null
    ln -sf "$DEPS_DIR/compose-scenescape.yml" "$APP_DIR/docker/ri-compose.yaml"

    if [ "$ENABLE_TC" = "true" ]; then
        export TC_SUBNET=$(grep -oP 'TC_SUBNET\s*=\s*\K[^\s]+' "$DEPS_DIR/.env" 2>/dev/null || echo "")
        if [ -z "$TC_SUBNET" ]; then
            echo -e "${RED}ERROR: TC_SUBNET not found in $DEPS_DIR/.env. ${NC}"
            return 1
        fi

        export TC_DNS_IP=$(grep -oP 'TC_DNS_IP\s*=\s*\K[^\s]+' "$DEPS_DIR/.env" 2>/dev/null || echo "")
        if [ -z "$TC_DNS_IP" ]; then
            echo -e "${RED}ERROR: TC_DNS_IP not found in $DEPS_DIR/.env. ${NC}"
            return 1
        fi
        echo "nameserver ${TC_DNS_IP}" > "${APP_DIR}/docker/tc-resolv.conf"

        #Create symbolic link to docker-compose.yml in docker dir of agent application
        rm "$APP_DIR/docker/ri-compose.yaml" 2> /dev/null
        ln -sf "$DEPS_DIR/docker-compose.yml" "$APP_DIR/docker/ri-compose.yaml"
    fi

	export SUPASS=$(cat "$RI_DIR/src/secrets/supass")
    verify_si_rtsp_config || return 1
    return 0
}

validate_rtsp_stream_config() {
    if [ -z "$RTSP_STREAM_IP" ]; then
        return 0
    fi

    if ! [[ "$RTSP_STREAM_IP" =~ ^[A-Za-z0-9.-]+$ ]]; then
        echo -e "${RED}ERROR: RTSP_STREAM_IP/SI_RTSP_HOST must be an IP address or hostname.${NC}"
        return 1
    fi

    if ! [[ "$RTSP_STREAM_PORT" =~ ^[0-9]+$ ]] || [ "$RTSP_STREAM_PORT" -lt 1 ] || [ "$RTSP_STREAM_PORT" -gt 65535 ]; then
        echo -e "${RED}ERROR: RTSP_STREAM_PORT must be a TCP port between 1 and 65535.${NC}"
        return 1
    fi
}

# Download the demo intersection's 4 synthetic RTSP videos from the shared
# edge-ai-resources bucket (same source smart-nvr's own streamer uses).
# Opt-in only: no-op unless STIA_DEMO_INTERSECTION is set. Skips files
# already present so re-running setup.sh doesn't re-download every time.
download_stia_demo_videos() {
    if [ -z "$STIA_DEMO_INTERSECTION" ]; then
        return 0
    fi

    mkdir -p "$STIA_DEMO_VIDEOS_DIR"

    local camera_number
    local video
    for camera_number in 1 2 3 4; do
        video="${STIA_DEMO_INTERSECTION}_${camera_number}.ts"
        if [ -f "${STIA_DEMO_VIDEOS_DIR}/${video}" ]; then
            continue
        fi
        echo -e "${BLUE}==> Downloading demo video ${video} ...${NC}"
        if ! curl -fL "${STIA_DEMO_VIDEO_URL}/${video}" -o "${STIA_DEMO_VIDEOS_DIR}/${video}"; then
            echo -e "${RED}ERROR: Failed to download demo video ${video} from ${STIA_DEMO_VIDEO_URL}.${NC}"
            rm -f "${STIA_DEMO_VIDEOS_DIR}/${video}"
            return 1
        fi
    done
}

# Start STIA's own local RTSP streamer (mediamtx + ffmpeg publisher, defined
# in docker/streamer-compose.yaml) so the demo flow is fully self-contained
# and doesn't need smart-nvr or any other external RTSP source running.
# Opt-in only: no-op unless STIA_DEMO_INTERSECTION is set. If RTSP_STREAM_IP
# or SI_RTSP_HOST is already set (an external RTSP source was explicitly
# provided), this is skipped and the external source is used instead. On
# success, exports RTSP_STREAM_IP=$HOST_IP so start_si_dlsps_rtsp_pipelines()
# picks up the local streamer automatically.
start_stia_rtsp_streamer() {
    if [ -z "$STIA_DEMO_INTERSECTION" ]; then
        return 0
    fi

    if [ -n "$RTSP_STREAM_IP" ]; then
        echo -e "${BLUE}==> External RTSP source detected (${RTSP_STREAM_IP}); skipping local STIA streamer.${NC}"
        return 0
    fi

    download_stia_demo_videos || return 1

    echo -e "${BLUE}==> Starting local RTSP streamer for demo '${STIA_DEMO_INTERSECTION}' ...${NC}"
    STIA_DEMO_INTERSECTION="$STIA_DEMO_INTERSECTION" \
    RTSP_STREAM_BIND_IP="${RTSP_STREAM_BIND_IP:-0.0.0.0}" \
    RTSP_STREAM_PORT="$RTSP_STREAM_PORT" \
        docker compose --project-directory "$APP_DIR" -f "${APP_DIR}/docker/streamer-compose.yaml" -p "${PROJECT_NAME}-streamer" up -d
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Failed to start local STIA RTSP streamer.${NC}"
        return 1
    fi

    export RTSP_STREAM_IP="$HOST_IP"
    echo -e "${GREEN}Local RTSP streamer for '${STIA_DEMO_INTERSECTION}' running at ${RTSP_STREAM_IP}:${RTSP_STREAM_PORT}.${NC}"
}

# Stop STIA's local RTSP streamer, if it was started. No-op unless
# STIA_DEMO_INTERSECTION is set - safe to call unconditionally from the
# --stop/--clean paths.
stop_stia_rtsp_streamer() {
    if [ -z "$STIA_DEMO_INTERSECTION" ]; then
        return 0
    fi
    docker compose --project-directory "$APP_DIR" -f "${APP_DIR}/docker/streamer-compose.yaml" -p "${PROJECT_NAME}-streamer" down 2>/dev/null || true
}

verify_si_rtsp_config() {
    if [ -z "$STIA_DEMO_INTERSECTION" ] || [ -z "$RTSP_STREAM_IP" ]; then
        return 0
    fi

    validate_rtsp_stream_config || return 1

    local dlstreamer_config="${RI_DIR}/src/dlstreamer-pipeline-server/config.json"
    if [ ! -f "$dlstreamer_config" ]; then
        echo -e "${RED}ERROR: DLStreamer Pipeline Server config not found: $dlstreamer_config${NC}"
        return 1
    fi

    if ! grep -q 'rtsp_server' "$dlstreamer_config"; then
        echo -e "${RED}ERROR: Smart Intersection DLSPS config does not contain rtsp_server support.${NC}"
        echo -e "${YELLOW}Remove ${CLONE_PATH} or set SI_SETUP_REPO_URL/SI_SETUP_BRANCH to the RTSP-enabled SI setup branch, then rerun setup.${NC}"
        return 1
    fi
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

# When VLM_TARGET_DEVICE=GPU, force SI to CPU so GPU is reserved for OVMS/VLM.
export TC_SI_TARGET_DEVICE=${TC_SI_TARGET_DEVICE:-CPU}
if [ "$VLM_TARGET_DEVICE" = "GPU" ] && [ "$TC_SI_TARGET_DEVICE" != "CPU" ]; then
    echo -e "${YELLOW}VLM_TARGET_DEVICE=GPU: overriding TC_SI_TARGET_DEVICE to CPU (GPU reserved for OVMS).${NC}"
    export TC_SI_TARGET_DEVICE=CPU
fi

# Select OVMS image tag based on target device:
# GPU requires the GPU-enabled image (includes OpenCL/Level Zero runtime).
# Mirrors the Helm chart logic: vlmServing.image.gpuTag vs vlmServing.image.tag.
case "$VLM_TARGET_DEVICE" in
    *GPU*) export OVMS_TAG="${OVMS_TAG:-2026.1-gpu}" ;;
    *)     export OVMS_TAG="${OVMS_TAG:-2026.1}" ;;
esac

# OVMS model repository directory (host-side, mounted into OVMS container)
# Health Check Configuration
export HEALTH_CHECK_INTERVAL=${HEALTH_CHECK_INTERVAL:-30s}
export HEALTH_CHECK_TIMEOUT=${HEALTH_CHECK_TIMEOUT:-10s}
export HEALTH_CHECK_RETRIES=${HEALTH_CHECK_RETRIES:-3}
export HEALTH_CHECK_START_PERIOD=${HEALTH_CHECK_START_PERIOD:-10s}

# ============================================================================
# OVMS Model Export Functions (host-side, using model-download ephemeral container)
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

# Export and convert a model for OVMS using the model-download ephemeral container.
# Replaces the previous host-side python venv + export_model.py approach.
export_model_for_ovms() {
    local source_model="$1"
    local target_device="$2"
    local weight_format="$3"
    local storage_model_name

    if [ -z "$source_model" ]; then
        echo -e "${RED}ERROR: Missing source model for OVMS export.${NC}"
        return 1
    fi

    storage_model_name=$(get_ovms_storage_model_name "$source_model" "$target_device" "$weight_format")
    echo -e "[ovms-service] ${BLUE}Storage model name: ${YELLOW}${storage_model_name}${NC}" >&2
    export storage_model_name

    local get_model_script="${OVMS_CONFIG_DIR}/get_model.sh"

    echo -e "${BLUE}==> Fetching get_model.sh from edge-ai-libraries...${NC}"
    curl -fsSL "https://raw.githubusercontent.com/open-edge-platform/edge-ai-libraries/main/microservices/model-download/scripts/get_model.sh" \
        -o "$get_model_script" || { echo -e "${RED}ERROR: Failed to download get_model.sh${NC}"; return 1; }
    chmod +x "$get_model_script"

    echo -e "${BLUE}==> Downloading/converting model via model-download ephemeral container...${NC}"

    # Pass HuggingFace token via env var if set
    if [ -n "${HUGGINGFACE_TOKEN:-}" ]; then
        export HF_TOKEN="${HUGGINGFACE_TOKEN}"
    fi

    bash "$get_model_script" \
        --model-name "$source_model" \
        --hub openvino \
        --type vlm \
	--is-ovms \
        --precision "$weight_format" \
        --device "$target_device" \
        --model-path "${OVMS_CONFIG_DIR}/models" \
        --plugins openvino

    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}ERROR: Model download/conversion failed for '${source_model}' (exit code: ${exit_code}).${NC}"
        local log_dir="${PWD}/.model_download_logs"
        local latest_log
        latest_log=$(ls -t "${log_dir}"/model_download_*.log 2>/dev/null | head -1)
        if [ -n "$latest_log" ]; then
            echo -e "${YELLOW}==> Last 30 lines from log: ${latest_log}${NC}"
            tail -30 "$latest_log"
        else
            echo -e "${YELLOW}No model download log found in: ${log_dir}${NC}"
        fi
        return 1
    fi

    # get_model.sh places config_all.json under openvino_models/{device}/{precision}/.
    # The base_paths inside it are relative to that directory.
    # Copy it to models/config.json, prefixing each base_path so it is relative to the models root.
    local models_root="${OVMS_CONFIG_DIR}/models"
    local generated_config
    generated_config=$(find "${models_root}/openvino_models" -name "config_all.json" 2>/dev/null | head -1)

    if [ -n "$generated_config" ]; then
        local config_rel_dir
        config_rel_dir=$(dirname "${generated_config#${models_root}/}")

        # Prefix every base_path value with the directory that config_all.json lives in
        python3 - "${generated_config}" "${config_rel_dir}" "${models_root}/config.json" << 'PYEOF'
import json, sys

src, prefix, dst = sys.argv[1], sys.argv[2], sys.argv[3]
with open(src) as f:
    cfg = json.load(f)
for entry in cfg.get("model_config_list", []):
    c = entry.get("config", {})
    if "base_path" in c:
        c["base_path"] = prefix + "/" + c["base_path"]
    c.pop("target_device", None)
with open(dst, "w") as f:
    json.dump(cfg, f, indent=4)
print(f"Created {dst} with {len(cfg['model_config_list'])} model(s)")
PYEOF
        echo -e "${GREEN}==> Created config.json from ${generated_config}${NC}"
    else
        echo -e "${YELLOW}WARNING: Could not find generated config_all.json under ${models_root}/openvino_models. OVMS may not start.${NC}"
    fi

    echo "$source_model"
}

ensure_ovms_model() {
    local model_name="$1"
    local target_device="$2"
    local weight_format="$3"
    local ovms_model_config="${OVMS_CONFIG_DIR}/models/config.json"

    echo -e "[ovms-service] ${BLUE}Checking for model: ${YELLOW}${model_name}${NC}"

    if [ -f "${ovms_model_config}" ] && ovms_config_has_model "${ovms_model_config}" "${model_name}"; then
        echo -e "[ovms-service] ${GREEN}Model ${YELLOW}${model_name}${GREEN} already registered in OVMS config. Skipping export.${NC}"
        echo "$model_name"
    else
        echo -e "[ovms-service] ${YELLOW}Model ${RED}${model_name}${YELLOW} not found. Exporting...${NC}"

        export_model_for_ovms \
            "$model_name" \
            "$target_device" \
            "$weight_format" || return 1
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
                    echo -e "${BLUE}Access DL Streamer Pipeline Server -> https://$HOST_IP:$HTTPS_PORT/api/pipelines${NC}"
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
                echo -e "${BLUE}Access $SERVICE_NAME -> http://$HOST_IP:$PORT/v2${NC}"
                ;;
            *metrics-manager*)
                SERVICE_NAME="Metrics Manager API"
                PORT=$(docker port "$CONTAINER_NAME" 9090 2>/dev/null | grep -v '^\[' | head -1 | cut -d: -f2)
                if [ -n "$PORT" ]; then
                    echo -e "${BLUE}Access $SERVICE_NAME -> http://$HOST_IP:$PORT${NC}"
                    echo -e "${BLUE}Access Metrics Manager Stream -> http://$HOST_IP:$PORT/metrics/stream${NC}"
                fi

                PORT=$(docker port "$CONTAINER_NAME" 9273 2>/dev/null | grep -v '^\[' | head -1 | cut -d: -f2)
                if [ -n "$PORT" ]; then
                    echo -e "${BLUE}Access Metrics Manager Telegraf/Prometheus -> http://$HOST_IP:$PORT/metrics${NC}"
                fi

                PORT=$(docker port "$CONTAINER_NAME" 8186 2>/dev/null | grep -v '^\[' | head -1 | cut -d: -f2)
                if [ -n "$PORT" ]; then
                    echo -e "${BLUE}Access Metrics Manager Telegraf HTTP -> http://$HOST_IP:$PORT/write${NC}"
                fi
                ;;
        esac
    done
    echo -e "${MAGENTA}=======================================================${NC}"
    echo -e
}

get_dlsps_pipeline_api_base() {
    local nginx_container
    local https_port

    nginx_container=$(docker ps --format '{{.Names}}' | grep -E "^${PROJECT_NAME}.*nginx-reverse-proxy" | head -1)
    if [ -z "$nginx_container" ]; then
        nginx_container=$(docker ps --format '{{.Names}}' | grep -E 'nginx-reverse-proxy$' | head -1)
    fi

    if [ -n "$nginx_container" ]; then
        https_port=$(docker port "$nginx_container" 443 2>/dev/null | grep -v '^\[' | head -1 | cut -d: -f2)
    fi

    if [ -z "$https_port" ]; then
        https_port=443
    fi

    printf 'https://localhost:%s/api/pipelines' "$https_port"
}

wait_for_dlsps_api() {
    local api_base="$1"
    local timeout="${DLSPS_START_TIMEOUT:-120}"
    local elapsed=0

    echo -e "${BLUE}==> Waiting for DLStreamer Pipeline Server API at ${api_base} ...${NC}"
    while [ "$elapsed" -lt "$timeout" ]; do
        if curl -k -s --noproxy '*' --fail "${api_base}/status" >/dev/null; then
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done

    echo -e "${RED}ERROR: DLStreamer Pipeline Server API was not reachable within ${timeout}s.${NC}"
    return 1
}

build_si_rtsp_pipeline_payload() {
    local camera_number="$1"
    local stream_path

    stream_path=$(get_si_rtsp_stream_path "$camera_number") || return 1

    cat <<EOF
{
  "rtsp_server": "rtsp://${RTSP_STREAM_IP}:${RTSP_STREAM_PORT}/${stream_path}",
  "parameters": {
    "camera_config": {
      "cameraid": "camera${camera_number}"
    }
  }
}
EOF
}

get_si_rtsp_stream_path() {
    local camera_number="$1"

    case "$camera_number" in
        1) echo "camera1" ;;
        2) echo "camera2" ;;
        3) echo "camera3" ;;
        4) echo "camera4" ;;
        *)
            echo -e "${RED}ERROR: Unsupported camera number: ${camera_number}${NC}"
            return 1
            ;;
    esac
}

# Resolve the actual loaded pipeline name for a given camera number.
# Custom DLSPS configs (e.g. via smart-intersection-overrides) may use a
# different name prefix than the stock demo (e.g. "intersection1-cam1"
# instead of "intersection-cam1"), so discover the real name from the API
# instead of hardcoding it. Excludes -gpu/-npu device variants.
resolve_si_pipeline_name() {
    local camera_number="$1"
    local api_base="$2"
    local pipelines_json
    local match

    # NOTE: the pipeline's runtime/instance name lives in the "version"
    # field of each entry returned by GET /api/pipelines; "name" is always
    # the pipeline group ("user_defined_pipelines").
    pipelines_json=$(curl -k -s --noproxy '*' "${api_base}") || return 1

    match=$(printf '%s' "$pipelines_json" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(1)
cam = 'cam${camera_number}'
candidates = [
    p.get('version') for p in data
    if isinstance(p, dict) and p.get('version', '').endswith(cam)
    and not p.get('version', '').endswith(cam + '-gpu')
    and not p.get('version', '').endswith(cam + '-npu')
]
if candidates:
    print(candidates[0])
" 2>/dev/null)

    if [ -z "$match" ]; then
        # Fallback to legacy hardcoded convention
        match="intersection-cam${camera_number}"
    fi

    printf '%s' "$match"
}

start_si_dlsps_rtsp_pipelines() {
    if [ -z "$STIA_DEMO_INTERSECTION" ] || [ -z "$RTSP_STREAM_IP" ]; then
        return 0
    fi

    validate_rtsp_stream_config || return 1

    local api_base
    api_base=$(get_dlsps_pipeline_api_base)
    wait_for_dlsps_api "$api_base" || return 1

    echo -e "${BLUE}==> Starting Smart Intersection DLStreamer pipelines with RTSP source ${RTSP_STREAM_IP}:${RTSP_STREAM_PORT} ...${NC}"
    for camera_number in 1 2 3 4; do
        local pipeline_name
        pipeline_name=$(resolve_si_pipeline_name "$camera_number" "$api_base")
        local payload
        local response
        local http_code
        local response_body
        local stream_path

        stream_path=$(get_si_rtsp_stream_path "$camera_number") || return 1
        payload=$(build_si_rtsp_pipeline_payload "$camera_number") || return 1
        response=$(curl -k -s --noproxy '*' -w "\nHTTP_CODE:%{http_code}" \
            "${api_base}/user_defined_pipelines/${pipeline_name}" \
            -X POST \
            -H "Content-Type: application/json" \
            -d "$payload")

        http_code=$(printf '%s\n' "$response" | awk -F: '/^HTTP_CODE:/ {print $2}' | tail -1)
        response_body=$(printf '%s\n' "$response" | sed '/^HTTP_CODE:/d')
        if [ "$http_code" != "200" ] && [ "$http_code" != "201" ]; then
            echo -e "${RED}ERROR: Failed to start ${pipeline_name}. HTTP ${http_code}: ${response_body}${NC}"
            return 1
        fi

        echo -e "${GREEN}Started ${pipeline_name} from rtsp://${RTSP_STREAM_IP}:${RTSP_STREAM_PORT}/${stream_path}.${NC}"
    done
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
        "$weight_format") || return 1

    export VLM_STORAGE_MODEL_NAME="$storage_name"
    echo -e "[ovms-service] ${GREEN}VLM Storage Model: ${YELLOW}${VLM_STORAGE_MODEL_NAME}${NC}"
}

# Build service images without starting containers
build_service() {
    echo -e "${BLUE}==> Building Smart-Traffic-Intersection-Agent ${RED}${PROJECT_NAME} ${BLUE}...${NC}"

    # Build the service images
    if [ -L "${APP_DIR}/docker/ri-compose.yaml" ]; then
        docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" $TC_OVERLAY_AGENT -p $PROJECT_NAME build
    else
        docker compose -f "${APP_DIR}/docker/agent-compose.yaml" $TC_OVERLAY_AGENT -p $PROJECT_NAME build
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
    docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" $TC_OVERLAY_AGENT -p $PROJECT_NAME up -d --build

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Smart-Traffic-Intersection-Agent Services built and started successfully!${NC}"
        start_stia_rtsp_streamer || return 1
        start_si_dlsps_rtsp_pipelines || return 1
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
    docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" $TC_OVERLAY_AGENT -p $PROJECT_NAME up -d --no-build

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Smart-Traffic-Intersection-Agent Services started successfully!${NC}"
        start_stia_rtsp_streamer || return 1
        start_si_dlsps_rtsp_pipelines || return 1
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
            local AGENT_SERVICES="traffic-agent ovms-service metrics-manager"

            # Stop the Traffic Intersection Agent Backend/UI Service
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" $TC_OVERLAY_AGENT -p $PROJECT_NAME stop $AGENT_SERVICES
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" $TC_OVERLAY_AGENT -p $PROJECT_NAME rm -f $AGENT_SERVICES

            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to stop Traffic Intersection Agent Backend/UI service!${NC}"
                return 1
            fi

            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" $TC_OVERLAY_AGENT -p $PROJECT_NAME up -d --force-recreate $AGENT_SERVICES

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
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml"  -p $PROJECT_NAME down

            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to stop dependencies!${NC}"
                return 1
            fi

            # Start with force-recreate to ensure env vars are picked up
            echo -e "${BLUE}==> Restarting dependencies (Smart Intersection RI) ...${NC}"
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -p $PROJECT_NAME up -d --force-recreate

            if [ $? -eq 0 ]; then
                echo -e "${GREEN}Dependencies restarted successfully!${NC}"
                start_stia_rtsp_streamer || return 1
                start_si_dlsps_rtsp_pipelines || return 1
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
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" $TC_OVERLAY_AGENT -p $PROJECT_NAME down
            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to stop services for Traffic Intersection Agent!${NC}"
                return 1
            fi

            # Restart all services
            docker compose --project-directory $DEPS_DIR -f "${APP_DIR}/docker/ri-compose.yaml" -f "${APP_DIR}/docker/ri-override.yaml" -f "${APP_DIR}/docker/agent-compose.yaml" $TC_OVERLAY_AGENT -p $PROJECT_NAME up -d --force-recreate

            if [ $? -eq 0 ]; then
                echo -e "${GREEN}All dependencies and Backend/UI services for Traffic Intersection Agent restarted successfully!${NC}"
                start_stia_rtsp_streamer || return 1
                start_si_dlsps_rtsp_pipelines || return 1
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
