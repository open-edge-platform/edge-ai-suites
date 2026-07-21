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
        apm-nginx apm-ui apm-agent apm-llm
        apm-storage apm-dlstreamer apm-mqtt-broker apm-model-download
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
    docker volume rm apm_sqlite_data apm_model_cache 2>/dev/null
    echo -e "${GREEN}Volumes removed.${NC}"
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

    # Source the env file
    set -a
    source "${env_file}"
    set +a

    # Restore caller-supplied overrides
    [ -n "${_pre_llm_mode}" ] && export LLM_MODE="${_pre_llm_mode}"

    # HOST_IP is optional — default to localhost if not set in the env file
    export HOST_IP="${HOST_IP:-localhost}"
    
    #GPU Configuration
    # Check if render device exist
    echo -e "\nRENDER device exist. Getting the GID...\n"
    export RENDER_GROUP_ID=$(stat -c "%g" /dev/dri/render* | head -n 1)

    # LLM_MODEL_PATH is stored relative to the repo root in the use-case env
    # file (e.g. "./apps/.../Phi-4-mini-instruct") for portability across
    # machines/users. Docker Compose resolves relative volume host paths
    # against the compose file's directory (docker/), not the caller's CWD —
    # so a relative LLM_MODEL_PATH silently binds an empty/auto-created stub
    # directory instead of the real model, and OVMS then fails to serve any
    # model ("No version found for model in path" / "Mediapipe graph
    # definition with requested name is not found"). Normalize it to an
    # absolute path here (anchored at the repo root, same convention as
    # USE_CASE_DIR below) before it reaches docker compose.
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

        # Warn if sample video is missing (DL Streamer needs it for auto_start pipeline)
        SAMPLE_VIDEO="${USE_CASE_RESOURCES_DIR}/videos/sample.mp4"
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
            -f docker/compose.agents.yaml \
            -f docker/compose.ui.yaml"

        # Include VLM service only when LLM mode is active
        if [ "${LLM_MODE:-llm}" != "fallback" ]; then
            COMPOSE_CMD="${COMPOSE_CMD} -f docker/compose.llm.yaml"
            echo -e "${BLUE}LLM mode: ${LLM_MODEL_NAME} on ${LLM_DEVICE}${NC}"
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
