#!/usr/bin/env bash
# download_models.sh — Submit a model download job, poll for completion, then flatten results.

# ----------- Color codes -----------
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; RESET=''
fi

log()  { echo -e "${GREEN}[INFO ] $*${RESET}"; }
warn() { echo -e "${YELLOW}[WARN ] $*${RESET}" >&2; }
err()  { echo -e "${RED}[ERROR] $*${RESET}" >&2; }

# ----------- Strict mode / anti-source guard -----------
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  err "This script is designed to be executed, not sourced. Please run: ./download_models.sh"
  return 1
fi

set -Eeuo pipefail

# ----------- Defaults / Config -----------
ROOT="${MODEL_PATH:-$PWD}"

MODEL_DOWNLOAD_PATH=${ROOT}/ovms_model
LLM_MODEL_PATH="${ROOT}/llm_models"
VLM_MODEL_PATH="${ROOT}/ov_models"
DETECTION_MODEL_PATH="${ROOT}/ov_detection_models"

API_SCHEME="http"
API_HOST="$(ip route get 1 | awk '{print $7}')"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT=8200

MODEL_TYPE="vlm"   # or "vision"
DEVICE="CPU"
PRECISION="fp16"

POLL_INTERVAL=10    # seconds between polls
TIMEOUT_MINUTES=30  # max time to wait for job completion

MODEL=""

API_BASE="${API_SCHEME}://${API_HOST}:${API_PORT}"
JOB_URL_BASE="${API_BASE}/api/v1/jobs"
MODEL_DOWNLOAD_URL="${API_BASE}/api/v1/models/download"
MODEL_DOWNLOAD_PATH_QUERY="download_path=ovms_model"

# ----------- Utilities -----------
have_cmd() { command -v "$1" >/dev/null 2>&1; }
need_cmd() {
  if ! have_cmd "$1"; then
    err "Required command not found: $1"
    return 1
  fi
}

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
    elif have_cmd docker; then
      log "Direct chown failed; retrying with docker as root for: $dir_path"
      docker run --rm -u root \
        -v "${dir_path}:/data" \
        alpine:latest sh -c "chown -R ${uid}:${gid} /data"
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
  --model <model_name>            Model identifier, e.g. "OpenGVLab/InternVL2-1B" or "OpenGVLab/InternVL2-2B"

Optional:
  --type <vlm|vision|llm>          Model type (default: ${MODEL_TYPE})
  --weight-format <int4|int8|fp16> Quantization. Applied only to VLM models not vision models. (default: ${PRECISION})
                                   fp16 -> FP16 precision (No quantization)
                                   int8 -> 8-bit integer quantization via NNCF
                                   int4 -> 4-bit integer quantization via NNCF (best compression if supported by model)
  --device <CPU|GPU|NPU>           Device. Not required unless using NPU device. Not tested on NPU at the moment. (default: ${DEVICE})
  -h, --help                       Show this help

Process:
  1) POST ${API_SCHEME}/api/v1/models/download?download_path=ov_models/<model_name>
     -> Parses <job_id> from response

  2) Poll GET ${API_SCHEME}://<host>:<port>/api/v1/jobs/<job_id> every ${POLL_INTERVAL}s
     until status is "completed", or fails/timeout.

  3) On success:
     - VLM: flatten to ${VLM_MODEL_PATH}/<model_name>
     - Vision: flatten to ${DETECTION_MODEL_PATH}/<model_name>
     - LLM: flatten to ${LLM_MODEL_PATH}/<model_name>
EOF
}

# ----------- Arg parsing -----------
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
  err "--model is required, e.g. --model \"OpenGVLab/InternVL2-1B\""
  usage
  exit 1
fi

if [[ "${PRECISION}" != "int4" && "${PRECISION}" != "int8" && "${PRECISION}" != "fp16" ]]; then
  err "Invalid precision: ${PRECISION}. Allowed values are int4, int8, fp16."
  exit 1
fi

# Compute max attempts from timeout/poll interval
if ! [[ "$POLL_INTERVAL" =~ ^[0-9]+$ && "$TIMEOUT_MINUTES" =~ ^[0-9]+$ ]]; then
  err "--poll-interval and --timeout-minutes must be integers"
  exit 1
fi
MAX_ATTEMPTS=$(( (TIMEOUT_MINUTES * 60 + POLL_INTERVAL - 1) / POLL_INTERVAL ))
(( MAX_ATTEMPTS > 0 )) || MAX_ATTEMPTS=1

# Ensure base directories exist
if [[ "$MODEL_TYPE" == "vlm" ]]; then
  ensure_model_base_dir_for_current_user "$VLM_MODEL_PATH" "VLM"
elif [[ "$MODEL_TYPE" == "vision" ]]; then
  ensure_model_base_dir_for_current_user "$DETECTION_MODEL_PATH" "Vision"
elif [[ "$MODEL_TYPE" == "llm" ]]; then
  ensure_model_base_dir_for_current_user "$LLM_MODEL_PATH" "LLM"
else
  err "Unknown model type: ${MODEL_TYPE}. Please specify a valid type (e.g. --type vlm, --type vision, or --type llm)."
  exit 1
fi

# ----------- Step 1: Download -----------
need_cmd curl
need_cmd jq

mkdir -p "$MODEL_DOWNLOAD_PATH"

if [[ "$MODEL_TYPE" == "vlm" || "$MODEL_TYPE" == "llm" ]]; then
  HUB="openvino"
  IS_OVMS=true
  PAYLOAD=$(cat <<JSON
{
  "models": [
    {
      "name": "${MODEL}",
      "hub": "${HUB}",
      "type": "${MODEL_TYPE}",
      "is_ovms": ${IS_OVMS},
      "config": {
        "precision": "${PRECISION}",
        "device": "${DEVICE}"
      }
    }
  ],
  "parallel_downloads": false
}
JSON
)
elif [[ "$MODEL_TYPE" == "vision" ]]; then
  HUB="ultralytics"
  PAYLOAD=$(cat <<JSON
{
  "models": [
    {
      "name": "${MODEL}",
      "hub": "${HUB}",
      "type": "${MODEL_TYPE}"
    }
  ],
  "parallel_downloads": false
}
JSON
)
else
  warn "Unknown model type: ${MODEL_TYPE}. Please specify a valid type (e.g. --type vlm, --type vision, or --type llm)."
  exit 1
fi

log "POST ${MODEL_DOWNLOAD_URL}?${MODEL_DOWNLOAD_PATH_QUERY}"

set +e
RESP="$(curl -sS -X POST "${MODEL_DOWNLOAD_URL}?${MODEL_DOWNLOAD_PATH_QUERY}" \
  -H "Content-Type: application/json" \
  -d "${PAYLOAD}")"
CURL_RC=$?

set -e
if (( CURL_RC != 0 )); then
  err "Download API call failed (curl rc=${CURL_RC})."
  exit 1
fi

# Check if response contains an error
if echo "$RESP" | jq -e '.detail' >/dev/null 2>&1; then
  err "API returned error: $(echo "$RESP" | jq -r '.detail')"
  exit 1
fi

JOB_ID="$(echo "$RESP" | jq -r '.job_ids[0]')"
if [[ -z "$JOB_ID" || "$JOB_ID" == "null" ]]; then
  err "No job_ids returned from download API. Response was:"
  echo "$RESP"
  exit 1
fi
log "Job submitted. job_id=${JOB_ID}"


# ----------- Step 2: Poll job status -----------
ATTEMPT=0
JOB_STATUS=""
JOB_RESULT_SUCCESS=""
JOB_RESULT_MSG=""
CONVERSION_PATH=""

log "Polling job status every ${POLL_INTERVAL}s for up to ${TIMEOUT_MINUTES} minute(s)..."

while (( ATTEMPT < MAX_ATTEMPTS )); do
  log "Attempting to poll job status..."
  ATTEMPT=$((ATTEMPT + 1))
  set +e
  log "GET ${JOB_URL_BASE}/${JOB_ID}"
  JOB_RESP="$(curl -sS -f -X GET "${JOB_URL_BASE}/${JOB_ID}")"
  CURL_RC=$?
  set -e
  if (( CURL_RC != 0 )); then
    warn "Failed to GET job status (curl rc=${CURL_RC}); will retry in ${POLL_INTERVAL}s."
    sleep "${POLL_INTERVAL}"
    continue
  fi

  JOB_STATUS="$(echo "$JOB_RESP" | jq -r '.status // "unknown"')"
  JOB_RESULT_SUCCESS="$(echo "$JOB_RESP" | jq -r '.result.success // ""')"
  JOB_RESULT_MSG="$(echo "$JOB_RESP" | jq -r '.result.message // ""')"
  CONVERSION_PATH="$(echo "$JOB_RESP" | jq -r '.result.conversion_path // .result.download_path // ""')"

  log "Job status: ${JOB_STATUS:-unknown} | success=${JOB_RESULT_SUCCESS:-} | msg=${JOB_RESULT_MSG:-}"

  case "${JOB_STATUS}" in
    completed)
      if [[ "${JOB_RESULT_SUCCESS}" == "true" ]]; then
        log "Job completed successfully."
        break
      else
        err "Job completed but result.success=false. Message: ${JOB_RESULT_MSG}"
        exit 1
      fi
      ;;
    failed|error|cancelled|canceled)
      err "Job ended with status=${JOB_STATUS}. Message: ${JOB_RESULT_MSG}"
      exit 1
      ;;
    *)
      log "Job still in progress (status: ${JOB_STATUS}), waiting ${POLL_INTERVAL}s..."
      sleep "${POLL_INTERVAL}"
      ;;
  esac
done

if [[ "${JOB_STATUS}" != "completed" || "${JOB_RESULT_SUCCESS}" != "true" ]]; then
  err "Timed out waiting for job completion after ${TIMEOUT_MINUTES} minute(s)."
  exit 1
fi

# ----------- Step 3: Flatten directory -----------
log "Start flattening model directory..."
log "Conversion path from API response: ${CONVERSION_PATH}"

if [[ -n "$CONVERSION_PATH" && -d "$CONVERSION_PATH" ]]; then
  MODEL_ROOT=$(echo "$CONVERSION_PATH" | sed -E "s|(.*ov_[^/]*models/[^/]+).*|\1|")
  if [[ -d "$MODEL_ROOT" ]]; then
    log "Fixing ownership and flattening: ${MODEL_ROOT}"
    # Ensure we can delete MODEL_DOWNLOAD_PATH by fixing parent perms first
    PARENT_DIR="$(dirname "$MODEL_DOWNLOAD_PATH")"
    BASENAME="$(basename "$MODEL_DOWNLOAD_PATH")"
    # Fix ownership
    # Make sure parent is writable
    docker run --rm -u root \
      -v "${PARENT_DIR}:/parent" \
      alpine:latest sh -c "chown $(id -u):$(id -g) /parent && chmod u+rwx /parent"

    # Ensure the target tree is ours and writable
    docker run --rm -u root \
      -v "${MODEL_DOWNLOAD_PATH}:/data" \
      alpine:latest sh -c "chown -R $(id -u):$(id -g) /data && chmod -R u+rwX /data"

    # Move files and cleanup
    if [[ "$MODEL_TYPE" == "vlm" ]]; then
      MODEL_BASENAME=$(basename "$MODEL")
      log "Creating model directory for VLM: ${MODEL_BASENAME}"
      MODEL_DIRNAME="${VLM_MODEL_PATH}/${MODEL_BASENAME}"
      mkdir -p "$MODEL_DIRNAME"
      mv "$MODEL_ROOT"/"$MODEL"/* "$MODEL_DIRNAME"/
    elif [[ "$MODEL_TYPE" == "vision" ]]; then
      MODEL_DIRNAME="${DETECTION_MODEL_PATH}/${MODEL}"
      mkdir -p "$MODEL_DIRNAME"
      mv "$CONVERSION_PATH"/public "$MODEL_DIRNAME"/
    elif [[ "$MODEL_TYPE" == "llm" ]]; then
      MODEL_DIRNAME="${LLM_MODEL_PATH}/${MODEL}"
      mkdir -p "$MODEL_DIRNAME"
      mv "$MODEL_ROOT"/"$MODEL"/* "$MODEL_DIRNAME"/
    fi
    rm -rf "$MODEL_DOWNLOAD_PATH"
    log "Completed: ${MODEL_DIRNAME}"
  fi
fi
