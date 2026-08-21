#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
GRAY='\033[0;90m'
NC='\033[0m'

# =================== Defaults ======================
USE_CASE=""
CONFIG_ONLY=false

# =================== Functions ======================
show_help() {
    echo -e "Agentic Predictive Maintenance Blueprint v1.0"
    echo -e "Copyright (C) 2026 Intel Corporation"
    echo -e ""
    echo -e "${YELLOW}USAGE:${NC}"
    echo -e "  ${GREEN}source setup.sh --use-case <use-case-name> [--stop | --clean-data | config]${NC}"
    echo -e ""
    echo -e "${YELLOW}OPTIONS:${NC}"
    echo -e "  ${BLUE}--use-case <name>${NC}    Use case to deploy (required). Example: pipeline-defect-detection"
    echo -e "  ${BLUE}--stop${NC}               Bring down all running containers"
    echo -e "  ${BLUE}--clean-data${NC}         Bring down containers and remove all volumes"
    echo -e "  ${BLUE}config${NC}               Print resolved compose configuration without starting"
    echo -e "  ${BLUE}-h, --help${NC}           Show this help message"
    echo -e ""
    echo -e "${YELLOW}EXAMPLES:${NC}"
    echo -e "  ${GRAY}source setup.sh --use-case pipeline-defect-detection"
    echo -e "  source setup.sh --use-case weld-defect-detection"
    echo -e "  source setup.sh --use-case pipeline-defect-detection --stop${NC}"
}

stop_containers() {
    echo -e "${YELLOW}Bringing down all containers...${NC}"
    # Stop by fixed container names — no USE_CASE env vars required
    local containers=(
        apm-nginx apm-ui apm-agent apm-detection apm-llm
        apm-storage apm-dlstreamer apm-mqtt-broker apm-model-download
        apm-metrics
    )
    local found=0
    for c in "${containers[@]}"; do
        if docker inspect "${c}" >/dev/null 2>&1; then
            docker rm -f "${c}" >/dev/null 2>&1 && echo -e "  ${GREEN}✓${NC} ${c}" || true
            found=1
        fi
    done
    if [ "${found}" -eq 0 ]; then
        echo -e "${YELLOW}No APM containers found running.${NC}"
    else
        echo -e "${GREEN}All containers stopped and removed.${NC}"
    fi
}

remove_volumes() {
    echo -e "${YELLOW}Removing Docker volumes...${NC}"
    # docker compose prefixes named volumes with the compose project name
    # (here "docker", from the directory of the first -f file), so the
    # actual volume names are e.g. "docker_apm_sqlite_data", not the bare
    # "apm_sqlite_data". Match on suffix so this works regardless of the
    # project name in effect.
    local volume_names=(apm_sqlite_data apm_model_cache apm_agent_output)
    local found=0
    for name in "${volume_names[@]}"; do
        local matches
        matches=$(docker volume ls -q --filter "name=${name}$")
        if [ -n "${matches}" ]; then
            while IFS= read -r vol; do
                docker volume rm "${vol}" >/dev/null 2>&1 && echo -e "  ${GREEN}✓${NC} ${vol}" && found=1
            done <<< "${matches}"
        fi
    done
    if [ "${found}" -eq 0 ]; then
        echo -e "${YELLOW}No APM volumes found.${NC}"
    else
        echo -e "${GREEN}Volumes removed.${NC}"
    fi
}

validate_env() {
    # The env file ships inside the use-case directory (apps/<use-case>/.env_<use-case>),
    # not at the project root.
    local env_file="${USE_CASE_DIR}/.env_${USE_CASE}"
    if [ ! -f "${env_file}" ]; then
        echo -e "${RED}ERROR: Environment file '${env_file}' not found.${NC}" >&2
        echo -e "${YELLOW}Create it by copying the template for your use case.${NC}" >&2
        return 1
    fi

    # Capture any vars the caller explicitly set before sourcing the env file
    # so they take precedence over file values (e.g. LLM_MODE=fallback ./setup.sh)
    local _pre_llm_mode="${LLM_MODE:-}"
    local _pre_llm_device="${LLM_DEVICE:-}"
    local _pre_dl_device="${DL_DEVICE:-}"

    # Source the env file
    set -a
    source "${env_file}"
    set +a

    # Restore caller-supplied overrides. Since this script is normally
    # sourced (`source setup.sh ...`), variables exported in a *previous*
    # invocation stay in the shell and would otherwise silently keep
    # overriding the .env file on every subsequent run — warn loudly so a
    # stale exported LLM_DEVICE/LLM_MODE/DL_DEVICE isn't mistaken for the
    # .env file being ignored/broken.
    if [ -n "${_pre_llm_mode}" ] && [ "${_pre_llm_mode}" != "${LLM_MODE:-}" ]; then
        echo -e "${YELLOW}NOTE: LLM_MODE is already exported in this shell ('${_pre_llm_mode}') and overrides '${LLM_MODE:-}' from ${env_file}.${NC}" >&2
        echo -e "${YELLOW}      Run 'unset LLM_MODE' if you meant to use the value from the env file.${NC}" >&2
        export LLM_MODE="${_pre_llm_mode}"
    fi
    if [ -n "${_pre_llm_device}" ] && [ "${_pre_llm_device}" != "${LLM_DEVICE:-}" ]; then
        echo -e "${YELLOW}NOTE: LLM_DEVICE is already exported in this shell ('${_pre_llm_device}') and overrides '${LLM_DEVICE:-}' from ${env_file}.${NC}" >&2
        echo -e "${YELLOW}      Run 'unset LLM_DEVICE' if you meant to use the value from the env file.${NC}" >&2
        export LLM_DEVICE="${_pre_llm_device}"
    fi
    if [ -n "${_pre_dl_device}" ] && [ "${_pre_dl_device}" != "${DL_DEVICE:-}" ]; then
        echo -e "${YELLOW}NOTE: DL_DEVICE is already exported in this shell ('${_pre_dl_device}') and overrides '${DL_DEVICE:-}' from ${env_file}.${NC}" >&2
        echo -e "${YELLOW}      Run 'unset DL_DEVICE' if you meant to use the value from the env file.${NC}" >&2
        export DL_DEVICE="${_pre_dl_device}"
    fi

    # HOST_IP is optional — default to localhost if not set in the env file
    export HOST_IP="${HOST_IP:-localhost}"
    
    # GPU render group configuration. Keep the compose default if this host
    # does not expose a render node.
    local render_devices=(/dev/dri/render*)
    if [ -e "${render_devices[0]}" ]; then
        echo -e "\nRENDER device exists. Getting the GID...\n"
        export RENDER_GROUP_ID
        RENDER_GROUP_ID=$(stat -c "%g" "${render_devices[0]}")
    fi
    if [ -n "${LLM_MODEL_PATH:-}" ] && [[ "${LLM_MODEL_PATH}" != /* ]]; then
        export LLM_MODEL_PATH="$(cd "${PWD}" && realpath -m "${LLM_MODEL_PATH}")"
    fi

    # Validate required variables (LLM_MODEL_NAME/LLM_MODEL_PATH not needed in fallback mode)
    local required_vars=()
    if [ "${LLM_MODE:-llm}" != "fallback" ]; then
        required_vars+=("LLM_MODEL_NAME" "LLM_DEVICE" "LLM_MODEL_PATH")
    fi
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo -e "${RED}ERROR: Required variable '${var}' is not set in ${env_file}.${NC}" >&2
            if [ "${var}" = "LLM_MODEL_PATH" ]; then
                echo -e "${YELLOW}   Run: ./scripts/download_llm_model.sh --use-case ${USE_CASE}${NC}" >&2
                echo -e "${YELLOW}   to download and convert the configured LLM, then rerun setup.sh.${NC}" >&2
                echo -e "${YELLOW}   Or set LLM_MODE=fallback in ${env_file} to skip the LLM service.${NC}" >&2
            fi
            return 1
        fi
    done

    if [ "${LLM_MODE:-llm}" != "fallback" ] && [ ! -d "${LLM_MODEL_PATH}" ]; then
        echo -e "${RED}ERROR: LLM_MODEL_PATH '${LLM_MODEL_PATH}' does not exist.${NC}" >&2
        echo -e "${YELLOW}   Run: ./scripts/download_llm_model.sh --use-case ${USE_CASE}${NC}" >&2
        return 1
    fi

    echo -e "${GREEN}Environment validated.${NC}"
    return 0
}

validate_npu_device() {
    if ! has_npu_device; then
        echo -e "${RED}ERROR: NPU was selected, but /dev/accel does not exist on this host.${NC}" >&2
        echo -e "${YELLOW}   Use CPU/GPU, or install/enable the Intel NPU driver so /dev/accel is available.${NC}" >&2
        return 1
    fi
    return 0
}

has_npu_device() {
    [ -d /dev/accel ]
}

has_gpu_device() {
    local render_devices=(/dev/dri/render*)
    [ -e "${render_devices[0]}" ]
}

validate_gpu_device() {
    if ! has_gpu_device; then
        echo -e "${RED}ERROR: GPU was selected, but no /dev/dri/render* device exists on this host.${NC}" >&2
        echo -e "${YELLOW}   Use CPU, or install/enable the Intel GPU driver so a render device is available.${NC}" >&2
        return 1
    fi
    return 0
}

# =================== Argument Parsing ======================
if [ "$#" -eq 0 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
    return 0 2>/dev/null || exit 0
fi

ACTION="start"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --use-case)
            USE_CASE="$2"
            shift 2
            ;;
        --stop|--down)
            ACTION="stop"
            shift
            ;;
        --clean-data)
            ACTION="clean"
            shift
            ;;
        config)
            CONFIG_ONLY=true
            shift
            ;;
        *)
            echo -e "${RED}ERROR: Unknown argument '$1'${NC}" >&2
            show_help
            return 1 2>/dev/null || exit 1
            ;;
    esac
done

# =================== Validate use-case ======================
if [ "${ACTION}" != "stop" ] && [ "${ACTION}" != "clean" ] && [ -z "${USE_CASE}" ]; then
    echo -e "${RED}ERROR: --use-case is required.${NC}" >&2
    show_help
    return 1 2>/dev/null || exit 1
fi

# =================== Resolve use-case paths ======================
if [ -n "${USE_CASE}" ]; then
    # Look for the use-case in the current repo (eal) or sibling eas repo
    USE_CASE_DIR=""
    CANDIDATE_DIRS=(
        "${PWD}/apps/${USE_CASE}"
    )
    for dir in "${CANDIDATE_DIRS[@]}"; do
        if [ -d "${dir}" ]; then
            USE_CASE_DIR="${dir}"
            break
        fi
    done

    if [ -z "${USE_CASE_DIR}" ]; then
        echo -e "${RED}ERROR: Use case '${USE_CASE}' not found.${NC}" >&2
        echo -e "${YELLOW}Expected directory: apps/${USE_CASE}/${NC}" >&2
        return 1 2>/dev/null || exit 1
    fi
    export USE_CASE_DIR
    export USE_CASE
fi

# =================== Execute ======================
case "${ACTION}" in
    stop)
        stop_containers
        ;;
    clean)
        stop_containers && remove_volumes
        ;;
    start)
        validate_env || { return 1 2>/dev/null || exit 1; }

        export APP_HOST_PORT="${APP_HOST_PORT:-8080}"
        export USE_CASE_CONFIGS_DIR="${USE_CASE_DIR}/configs"
        export USE_CASE_PROMPTS_DIR="${USE_CASE_DIR}/prompts"
        export USE_CASE_MODELS_DIR="${USE_CASE_DIR}/models"
        export USE_CASE_RESOURCES_DIR="${USE_CASE_DIR}/resources"

        LLM_DEVICE_NORMALIZED="${LLM_DEVICE:-CPU}"
        LLM_DEVICE_NORMALIZED="${LLM_DEVICE_NORMALIZED^^}"
        AVAILABLE_DEVICES="CPU"
        has_gpu_device && AVAILABLE_DEVICES="${AVAILABLE_DEVICES},GPU"
        has_npu_device && AVAILABLE_DEVICES="${AVAILABLE_DEVICES},NPU"
        export AVAILABLE_DEVICES

        # Warn if sample video is missing (DL Streamer needs it for auto_start pipeline)
        SAMPLE_VIDEO="${USE_CASE_RESOURCES_DIR}/videos/datastream.mp4"
        if [ ! -f "${SAMPLE_VIDEO}" ]; then
            echo -e "${YELLOW}⚠️  Sample video not found: ${SAMPLE_VIDEO}${NC}"
            echo -e "${YELLOW}   Run the data prep script to download and create it:${NC}"
            echo -e "${YELLOW}       python scripts/download_and_prep_data.py <dataset_url> --use-case ${USE_CASE}${NC}"
            echo -e "${YELLOW}   DL Streamer will fail to start the auto_start pipeline without this file.${NC}"
            echo -e "${YELLOW}   Set LLM_MODE=fallback in ${USE_CASE_DIR}/.env_${USE_CASE} to run without DL Streamer.${NC}"
            echo
        fi

        echo -e "${BLUE}Starting Agentic Predictive Maintenance — use case: ${USE_CASE}${NC}"

        COMPOSE_CMD="docker compose \
            -f docker/compose.base.yaml \
            -f docker/compose.telemetry.yaml \
            -f docker/compose.detection.yaml \
            -f docker/compose.agents.yaml \
            -f docker/compose.ui.yaml"

        if has_gpu_device; then
            COMPOSE_CMD="${COMPOSE_CMD} -f docker/compose.telemetry-gpu.yaml"
        fi

        if has_gpu_device; then
            COMPOSE_CMD="${COMPOSE_CMD} -f docker/compose.dlstreamer-gpu.yaml"
            echo -e "${BLUE}DL Streamer GPU device mapping enabled.${NC}"
        fi

        if has_npu_device; then
            COMPOSE_CMD="${COMPOSE_CMD} -f docker/compose.dlstreamer-npu.yaml"
            echo -e "${BLUE}DL Streamer NPU device mapping enabled.${NC}"
        fi

        # Include VLM service only when LLM mode is active
        if [ "${LLM_MODE:-llm}" != "fallback" ]; then
            COMPOSE_CMD="${COMPOSE_CMD} -f docker/compose.llm.yaml"
            echo -e "${BLUE}LLM mode: ${LLM_MODEL_NAME} on ${LLM_DEVICE}${NC}"
            if [ "${LLM_DEVICE_NORMALIZED}" = "GPU" ]; then
                validate_gpu_device || { return 1 2>/dev/null || exit 1; }
                COMPOSE_CMD="${COMPOSE_CMD} -f docker/compose.llm-gpu.yaml"
                echo -e "${BLUE}LLM GPU device mapping enabled.${NC}"
            fi
            if [ "${LLM_DEVICE_NORMALIZED}" = "NPU" ]; then
                validate_npu_device || { return 1 2>/dev/null || exit 1; }
                COMPOSE_CMD="${COMPOSE_CMD} -f docker/compose.llm-npu.yaml"
                echo -e "${BLUE}LLM NPU device mapping enabled.${NC}"
            fi
        else
            echo -e "${YELLOW}Fallback mode: rule-based reasoning (no VLM service)${NC}"
        fi

        if [ "${CONFIG_ONLY}" = true ]; then
            ${COMPOSE_CMD} config
        else
            ${COMPOSE_CMD} up -d
            if [ $? -ne 0 ]; then
                echo -e "${RED}ERROR: Failed to start containers.${NC}" >&2
                return 1 2>/dev/null || exit 1
            fi
            echo -e "${GREEN}Application started. UI available at: http://${HOST_IP}:${APP_HOST_PORT}${NC}"
            echo -e "${BLUE}Click \"Run Pipeline\" on the dashboard to run one detect-then-reason cycle over the sample video.${NC}"
        fi
        ;;
esac
