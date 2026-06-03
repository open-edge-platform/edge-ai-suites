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

# Staging directory for ephemeral container downloads (temporary)
MODEL_DOWNLOAD_PATH="${ROOT}/ovms_model"

# Final model directories
DEFAULT_MODEL_PATH="${ROOT}/ov_models"
LLM_MODEL_PATH="${ROOT}/llm_models"
DETECTION_MODEL_PATH="${ROOT}/ov_detection_models"

MODEL_TYPE="vlm"
DEVICE="CPU"
PRECISION="int8"
MODEL=""

EPHEMERAL_SCRIPT_URL="${MODEL_DOWNLOAD_EPHEMERAL_SCRIPT_URL:-https://raw.githubusercontent.com/open-edge-platform/edge-ai-libraries/main/microservices/model-download/scripts/get_model.sh}"
IMAGE_TAG="${TAG:-latest}"
OVMS_RELEASE_TAG="${OVMS_RELEASE_TAG:-v2026.0}"

ensure_model_base_dir_for_current_user() {
  local dir_path="$1"
  local dir_label="$2"
  local uid gid owner_uid owner_gid

  uid="$(id -u)"
  gid="$(id -g)"

  if [[ ! -d "$dir_path" ]]; then
    log "Creating ${dir_label} base directory: $dir_path"
    mkdir -p "$dir_path"
  fi

  owner_uid="$(stat -c '%u' "$dir_path" 2>/dev/null || echo "")"
  owner_gid="$(stat -c '%g' "$dir_path" 2>/dev/null || echo "")"

  if [[ -z "$owner_uid" || -z "$owner_gid" ]]; then
    err "Unable to determine ownership for directory: $dir_path"
    return 1
  fi

  if [[ "$owner_uid" != "$uid" || "$owner_gid" != "$gid" ]]; then
    log "Directory ownership mismatch for $dir_path (found ${owner_uid}:${owner_gid}, expected ${uid}:${gid}). Fixing..."

    if chown -R "${uid}:${gid}" "$dir_path" 2>/dev/null; then
      log "Ownership updated for: $dir_path"
    elif command -v docker >/dev/null 2>&1; then
      log "Direct chown failed; retrying with docker as root for: $dir_path"
      docker run --rm -u root \
        -v "${dir_path}:/data" \
        alpine:3.22 sh -c "chown -R ${uid}:${gid} /data"
      log "Ownership updated via docker for: $dir_path"
    else
      err "Failed to change ownership for $dir_path and docker is not available for root fallback."
      return 1
    fi
  fi
}

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
    EXTRA_ARGS=(--type vlm --is-ovms --precision "${PRECISION}" --device "${DEVICE}")
    FINAL_DIR="${DEFAULT_MODEL_PATH}"
    ensure_model_base_dir_for_current_user "$FINAL_DIR" "VLM"
    ;;
  llm)
    HUB="openvino"
    PLUGINS="huggingface,openvino"
    EXTRA_ARGS=(--type llm --is-ovms --precision "${PRECISION}" --device "${DEVICE}")
    FINAL_DIR="${LLM_MODEL_PATH}"
    ensure_model_base_dir_for_current_user "$FINAL_DIR" "LLM"
    ;;
  vision)
    HUB="ultralytics"
    PLUGINS="ultralytics"
    EXTRA_ARGS=(--type vision)
    FINAL_DIR="${DETECTION_MODEL_PATH}"
    ensure_model_base_dir_for_current_user "$FINAL_DIR" "Vision"
    ;;
  *)
    err "Unknown model type: ${MODEL_TYPE}. Use vlm, vision, or llm."
    exit 1
    ;;
esac

mkdir -p "${MODEL_DOWNLOAD_PATH}"

log "Downloading ${MODEL_TYPE} model '${MODEL}' with the ephemeral model-download container."
log "Models will be stored under: ${FINAL_DIR}"

EPHEMERAL_SCRIPT=$(curl -fsSL "${EPHEMERAL_SCRIPT_URL}") || {
  err "Failed to download ephemeral script from: ${EPHEMERAL_SCRIPT_URL}"
  err "Please verify the URL is correct and accessible."
  exit 1
}

# Use ovms_model as the staging download path
DOWNLOAD_ARGS=(
  --model-name "${MODEL}"
  --hub "${HUB}"
  --plugins "${PLUGINS}"
  --model-path "${ROOT}"
  --download-path "ovms_model"
  --image-tag "${IMAGE_TAG}"
  --ovms-release-tag "${OVMS_RELEASE_TAG}"
)

echo "${EPHEMERAL_SCRIPT}" | bash -s -- \
  "${DOWNLOAD_ARGS[@]}" \
  "${EXTRA_ARGS[@]}"

# ----------- Flatten directory -----------
# The ephemeral container runs as root, so fix ownership before moving files.
log "Flattening model directory..."

# Fix ownership of the staging directory (container creates files as root)
PARENT_DIR="$(dirname "$MODEL_DOWNLOAD_PATH")"
docker run --rm -u root \
  -v "${PARENT_DIR}:/parent" \
  alpine:3.22 sh -c "chown $(id -u):$(id -g) /parent && chmod u+rwx /parent"

docker run --rm -u root \
  -v "${MODEL_DOWNLOAD_PATH}:/data" \
  alpine:3.22 sh -c "chown -R $(id -u):$(id -g) /data && chmod -R u+rwX /data"

if [[ "${MODEL_TYPE}" == "vlm" || "${MODEL_TYPE}" == "llm" ]]; then
  # Find the converted model inside the nested openvino structure
  # Structure: ovms_model/openvino_models/<device>/<precision>/<org>/<model>/
  DEVICE_LOWER="$(echo "${DEVICE}" | tr '[:upper:]' '[:lower:]')"
  PRECISION_LOWER="$(echo "${PRECISION}" | tr '[:upper:]' '[:lower:]')"
  NESTED_DIR="${MODEL_DOWNLOAD_PATH}/openvino_models/${DEVICE_LOWER}/${PRECISION_LOWER}"

  MODEL_BASENAME="${MODEL##*/}"
  MODEL_SRC="${NESTED_DIR}/${MODEL}"

  if [[ ! -d "${MODEL_SRC}" ]]; then
    # Try finding it
    MODEL_SRC=$(find "${NESTED_DIR}" -mindepth 1 -maxdepth 2 -type d -name "${MODEL_BASENAME}" 2>/dev/null | head -1)
  fi

  if [[ "${MODEL_TYPE}" == "vlm" ]]; then
    TARGET_DIR="${FINAL_DIR}/${MODEL_BASENAME}"
  elif [[ "${MODEL_TYPE}" == "llm" ]]; then
    # For LLMs, preserve the org/model structure if present
    TARGET_DIR="${FINAL_DIR}/${MODEL}"
  fi

  if [[ -n "${MODEL_SRC}" && -d "${MODEL_SRC}" ]]; then
    mkdir -p "${TARGET_DIR}"
    mv "${MODEL_SRC}"/* "${TARGET_DIR}"/
    log "Relocated model to: ${TARGET_DIR}"
  else
    err "Could not find model files in nested structure at: ${NESTED_DIR}"
    err "Listing staging directory contents:"
    find "${MODEL_DOWNLOAD_PATH}" -type d | head -20
    exit 1
  fi

elif [[ "${MODEL_TYPE}" == "vision" ]]; then
  MODEL_BASENAME="${MODEL##*/}"
  TARGET_DIR="${FINAL_DIR}/${MODEL_BASENAME}"
  mkdir -p "${TARGET_DIR}"
  # Vision models may be nested under ultralytics/public/<model>.
  # Flatten to: ov_detection_models/<model>/public/<model>
  if [[ -d "${MODEL_DOWNLOAD_PATH}/ultralytics/public" ]]; then
    mv "${MODEL_DOWNLOAD_PATH}/ultralytics/public" "${TARGET_DIR}"/
  elif [[ -d "${MODEL_DOWNLOAD_PATH}/public" ]]; then
    mv "${MODEL_DOWNLOAD_PATH}/public" "${TARGET_DIR}"/
  else
    err "Could not find vision model files under ${MODEL_DOWNLOAD_PATH}/ultralytics/public or ${MODEL_DOWNLOAD_PATH}/public"
    exit 1
  fi
  log "Relocated model to: ${TARGET_DIR}"
fi

# Clean up staging directory
rm -rf "${MODEL_DOWNLOAD_PATH}"
log "Completed model download. Check ${FINAL_DIR} for the generated model files."