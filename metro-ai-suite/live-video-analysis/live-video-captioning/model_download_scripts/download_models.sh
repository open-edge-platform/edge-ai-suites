#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -Eeuo pipefail

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; RESET=''
fi

log()  { echo -e "${GREEN}[INFO ] $*${RESET}"; }
warn() { echo -e "${YELLOW}[WARN ] $*${RESET}" >&2; }
err()  { echo -e "${RED}[ERROR] $*${RESET}" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "${ROOT_DIR}/.env"
  set +a
fi

ROOT="${MODEL_PATH:-${ROOT_DIR}}"
MODEL_TYPE="vlm"
DEVICE="CPU"
PRECISION="int8"
MODEL=""

EPHEMERAL_SCRIPT_URL="${MODEL_DOWNLOAD_EPHEMERAL_SCRIPT_URL:-https://raw.githubusercontent.com/yogeshmpandey/edge-ai-libraries/feat/ephemeral-container/microservices/model-download/scripts/run_ephemeral.sh}"
IMAGE_TAG="${TAG:-latest}"
OVMS_RELEASE_TAG="${OVMS_RELEASE_TAG:-v2026.0}"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") --model "<model_name>" [options]

Required:
  --model <model_name>            Model identifier, e.g. "OpenGVLab/InternVL2-1B" or "yolov8s"

Optional:
  --type <vlm|vision|llm>          Model type (default: ${MODEL_TYPE})
  --weight-format <int4|int8|fp16> Quantization for VLM/LLM OpenVINO conversion (default: ${PRECISION})
  --device <CPU|GPU|NPU>           Target device for VLM/LLM OpenVINO conversion (default: ${DEVICE})
  -h, --help                       Show this help

Examples:
  ./model_download_scripts/download_models.sh --model OpenGVLab/InternVL2-1B --type vlm --weight-format int8
  ./model_download_scripts/download_models.sh --model yolov8s --type vision
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)              MODEL="${2:-}"; shift 2 ;;
    --model=*)            MODEL="${1#*=}"; shift ;;
    --device)             DEVICE="${2:-}"; shift 2 ;;
    --type)               MODEL_TYPE="${2:-}"; shift 2 ;;
    --weight-format)      PRECISION="${2:-}"; shift 2 ;;
    -h|--help)            usage; exit 0 ;;
    *) err "Unknown option: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "${MODEL}" ]]; then
  err "--model is required."
  usage
  exit 1
fi

if [[ "${PRECISION}" != "int4" && "${PRECISION}" != "int8" && "${PRECISION}" != "fp16" ]]; then
  err "Invalid precision: ${PRECISION}. Allowed values are int4, int8, fp16."
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  err "Required command not found: curl"
  exit 1
fi

case "${MODEL_TYPE}" in
  vlm)
    HUB="openvino"
    PLUGINS="huggingface,openvino"
    DOWNLOAD_PATH="ov_models"
    EXTRA_ARGS=(--type vlm --is-ovms --precision "${PRECISION}" --device "${DEVICE}")
    FINAL_DIR="${ROOT}/ov_models"
    ;;
  llm)
    HUB="openvino"
    PLUGINS="huggingface,openvino"
    DOWNLOAD_PATH="llm_models"
    EXTRA_ARGS=(--type llm --is-ovms --precision "${PRECISION}" --device "${DEVICE}")
    FINAL_DIR="${ROOT}/llm_models"
    ;;
  vision)
    HUB="ultralytics"
    PLUGINS="ultralytics"
    DOWNLOAD_PATH="ov_detection_models"
    EXTRA_ARGS=(--type vision)
    FINAL_DIR="${ROOT}/ov_detection_models"
    ;;
  *)
    err "Unknown model type: ${MODEL_TYPE}. Use vlm, vision, or llm."
    exit 1
    ;;
esac

mkdir -p "${FINAL_DIR}"

log "Downloading ${MODEL_TYPE} model '${MODEL}' with the ephemeral model-download container."
log "Models will be stored under: ${FINAL_DIR}"

curl -sSL "${EPHEMERAL_SCRIPT_URL}" | bash -s -- \
  --model-name "${MODEL}" \
  --hub "${HUB}" \
  --plugins "${PLUGINS}" \
  --model-path "${ROOT}" \
  --download-path "${DOWNLOAD_PATH}" \
  --image-tag "${IMAGE_TAG}" \
  --ovms-release-tag "${OVMS_RELEASE_TAG}" \
  "${EXTRA_ARGS[@]}"

log "Completed model download. Check ${FINAL_DIR} for the generated model files."
