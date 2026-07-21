#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Downloads and converts the LLM configured for a use case (LLM_MODEL_NAME in
# apps/<use-case>/.env_<use-case>) to OpenVINO Model Server (OVMS) format using
# the model-download microservice (https://github.com/open-edge-platform/edge-ai-libraries/
# tree/main/microservices/model-download), then writes the resulting local path
# back into the use case's env file as LLM_MODEL_PATH so setup.sh can mount it
# into the apm-llm (OVMS) container.
#
# Usage:
#   ./scripts/download_llm_model.sh --use-case pipeline-defect-detection

set -Eeuo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO ] $*${NC}"; }
warn() { echo -e "${YELLOW}[WARN ] $*${NC}" >&2; }
err()  { echo -e "${RED}[ERROR] $*${NC}" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

usage() {
    cat <<EOF
Usage:
  $(basename "$0") --use-case <use-case-name>

Downloads and converts the LLM configured for <use-case> (via LLM_MODEL_NAME,
LLM_DEVICE, LLM_WEIGHT_FORMAT in apps/<use-case>/.env_<use-case>) to OVMS
format using the model-download microservice, then writes LLM_MODEL_PATH back
into that env file.

Options:
  --use-case <name>   Use case directory under apps/ (required)
  -h, --help          Show this help message
EOF
}

USE_CASE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --use-case) USE_CASE="$2"; shift 2 ;;
        --use-case=*) USE_CASE="${1#*=}"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) err "Unknown argument: $1"; usage; exit 1 ;;
    esac
done

if [[ -z "${USE_CASE}" ]]; then
    err "--use-case is required."
    usage
    exit 1
fi

USE_CASE_DIR="${ROOT_DIR}/apps/${USE_CASE}"
ENV_FILE="${USE_CASE_DIR}/.env_${USE_CASE}"

if [[ ! -f "${ENV_FILE}" ]]; then
    err "Environment file not found: ${ENV_FILE}"
    exit 1
fi

# shellcheck disable=SC1090
set -a
source "${ENV_FILE}"
set +a

if [[ "${LLM_MODE:-llm}" == "fallback" ]]; then
    warn "LLM_MODE=fallback in ${ENV_FILE} — no LLM model download needed."
    exit 0
fi

LLM_MODEL_NAME="${LLM_MODEL_NAME:?LLM_MODEL_NAME must be set in ${ENV_FILE}}"
LLM_DEVICE="${LLM_DEVICE:-CPU}"
LLM_WEIGHT_FORMAT="${LLM_WEIGHT_FORMAT:-int8}"
MODEL_DOWNLOAD_PORT="${MODEL_DOWNLOAD_PORT:-8200}"
USE_CASE_MODELS_DIR="${USE_CASE_DIR}/models"

if command -v curl >/dev/null 2>&1; then
    :
else
    err "Required command not found: curl"
    exit 1
fi

if [[ "${LLM_DEVICE}" == "NPU" && "${LLM_WEIGHT_FORMAT}" != "int4" ]]; then
    warn "NPU only supports int4 conversion — overriding LLM_WEIGHT_FORMAT '${LLM_WEIGHT_FORMAT}' to 'int4'."
    LLM_WEIGHT_FORMAT="int4"
fi

mkdir -p "${USE_CASE_MODELS_DIR}"
# apm-model-download runs as a non-root container user (appuser); make sure it
# can write new model subdirectories into the host-mounted models directory
# regardless of the host UID that owns it.
chmod -R a+rwX "${USE_CASE_MODELS_DIR}" 2>/dev/null || true

log "Starting model-download service (apm-model-download)..."
export USE_CASE_DIR USE_CASE_MODELS_DIR
export USE_CASE_CONFIGS_DIR="${USE_CASE_DIR}/configs"
export USE_CASE_PROMPTS_DIR="${USE_CASE_DIR}/prompts"
export USE_CASE_RESOURCES_DIR="${USE_CASE_DIR}/resources"
export APP_HOST_PORT="${APP_HOST_PORT:-8080}"
# Services in compose.base.yaml (e.g. nginx) depend_on services defined in the
# other compose files (apm-ui, apm-agent), so all files must be loaded together
# for Compose to resolve the project — even though we only start model-download.
COMPOSE_CMD="docker compose \
    -f ${ROOT_DIR}/docker/compose.base.yaml \
    -f ${ROOT_DIR}/docker/compose.agents.yaml \
    -f ${ROOT_DIR}/docker/compose.ui.yaml"
${COMPOSE_CMD} up -d model-download

log "Waiting for model-download service to become healthy on port ${MODEL_DOWNLOAD_PORT}..."
for i in $(seq 1 60); do
    if curl -sf "http://localhost:${MODEL_DOWNLOAD_PORT}/api/v1/models/results" >/dev/null 2>&1; then
        break
    fi
    if [[ "${i}" -eq 60 ]]; then
        err "model-download service did not become ready in time. Check: docker logs apm-model-download"
        exit 1
    fi
    sleep 2
done

DOWNLOAD_PATH="llm_model_${USE_CASE}"
log "Requesting download+conversion of '${LLM_MODEL_NAME}' (device=${LLM_DEVICE}, precision=${LLM_WEIGHT_FORMAT})..."

RESPONSE=$(curl -sf -X POST \
    "http://localhost:${MODEL_DOWNLOAD_PORT}/api/v1/models/download?download_path=${DOWNLOAD_PATH}" \
    -H "Content-Type: application/json" \
    -d "$(cat <<JSON
{
  "models": [
    {
      "name": "${LLM_MODEL_NAME}",
      "hub": "openvino",
      "type": "llm",
      "is_ovms": true,
      "config": {
        "precision": "${LLM_WEIGHT_FORMAT}",
        "device": "${LLM_DEVICE}",
        "pipeline_type": "LM_CB"
      }
    }
  ],
  "parallel_downloads": false
}
JSON
)") || {
    err "Failed to submit download request to model-download service."
    exit 1
}

JOB_ID=$(echo "${RESPONSE}" | python3 -c "import sys, json; print(json.load(sys.stdin)['job_ids'][0])" 2>/dev/null) || {
    err "Unexpected response from model-download service: ${RESPONSE}"
    exit 1
}

log "Download job submitted (job_id=${JOB_ID}). Waiting for completion — this may take a while..."

STATUS="processing"
for i in $(seq 1 600); do
    JOB=$(curl -sf "http://localhost:${MODEL_DOWNLOAD_PORT}/api/v1/jobs/${JOB_ID}") || {
        err "Failed to query job status."
        exit 1
    }
    STATUS=$(echo "${JOB}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))")
    if [[ "${STATUS}" == "completed" || "${STATUS}" == "failed" ]]; then
        break
    fi
    sleep 5
done

if [[ "${STATUS}" != "completed" ]]; then
    err "Model download did not complete successfully (status=${STATUS})."
    err "Job details: ${JOB}"
    exit 1
fi

log "Download complete. Locating converted model files..."

DEVICE_LOWER="$(echo "${LLM_DEVICE}" | tr '[:upper:]' '[:lower:]')"
PRECISION_LOWER="$(echo "${LLM_WEIGHT_FORMAT}" | tr '[:upper:]' '[:lower:]')"
NESTED_DIR="${USE_CASE_MODELS_DIR}/${DOWNLOAD_PATH}/openvino_models/${DEVICE_LOWER}/${PRECISION_LOWER}"
MODEL_BASENAME="$(basename "${LLM_MODEL_NAME}")"

MODEL_SRC=$(find "${NESTED_DIR}" -mindepth 1 -maxdepth 2 -type d -iname "${MODEL_BASENAME}" 2>/dev/null | head -1)
if [[ -z "${MODEL_SRC}" ]]; then
    err "Could not find converted model under: ${NESTED_DIR}"
    err "Inspect the download output manually:"
    find "${USE_CASE_MODELS_DIR}/${DOWNLOAD_PATH}" -maxdepth 4 -type d 2>/dev/null | sed 's/^/  /'
    exit 1
fi

log "Found model at: ${MODEL_SRC}"

# Persist LLM_MODEL_PATH into the use-case env file (replace if present, append otherwise)
if grep -q "^LLM_MODEL_PATH=" "${ENV_FILE}"; then
    sed -i "s|^LLM_MODEL_PATH=.*|LLM_MODEL_PATH=${MODEL_SRC}|" "${ENV_FILE}"
else
    {
        echo ""
        echo "# Set automatically by scripts/download_llm_model.sh"
        echo "LLM_MODEL_PATH=${MODEL_SRC}"
    } >> "${ENV_FILE}"
fi

log "LLM_MODEL_PATH set to '${MODEL_SRC}' in ${ENV_FILE}"
log "You can now run: source setup.sh --use-case ${USE_CASE}"
