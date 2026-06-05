#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_COMPOSE="${ROOT_DIR}/docker-compose.yaml"
DEVICE_ENV_FILE="${DEVICE_ENV:-configs/res/mixed-optimized.env}"

if [[ "${DEVICE_ENV_FILE}" != /* ]]; then
  DEVICE_ENV_FILE="${ROOT_DIR}/${DEVICE_ENV_FILE}"
fi

read_device() {
  local key="$1"
  local file="$2"
  awk -F= -v key="$key" '$1 == key { print $2; exit }' "$file"
}

if [[ ! -f "${DEVICE_ENV_FILE}" ]]; then
  echo "${DEVICE_ENV_FILE} not found; running without NPU override" >&2
  exec docker compose -f "${BASE_COMPOSE}" "$@"
fi

DETECTION_DEVICE="$(read_device DETECTION_DEVICE "${DEVICE_ENV_FILE}")"
RPPG_DEVICE="$(read_device RPPG_DEVICE "${DEVICE_ENV_FILE}")"
ACTION_DEVICE="$(read_device ACTION_DEVICE "${DEVICE_ENV_FILE}")"

HAS_NPU=false
if [[ "${DETECTION_DEVICE}" == "NPU" || "${RPPG_DEVICE}" == "NPU" || "${ACTION_DEVICE}" == "NPU" ]]; then
  HAS_NPU=true
fi

HOST_HAS_NPU=false
if [[ -e /dev/accel/accel0 || -e /dev/accel ]]; then
  HOST_HAS_NPU=true
fi

if [[ "${HAS_NPU}" == true && "${HOST_HAS_NPU}" == true ]]; then
  TMP_OVERRIDE="$(mktemp)"
  trap 'rm -f "${TMP_OVERRIDE}"' EXIT

  cat > "${TMP_OVERRIDE}" <<'EOF'
services:
  nicu-backend:
    devices:
      - /dev/accel:/dev/accel
  nicu-dlsps:
    devices:
      - /dev/accel:/dev/accel
EOF

  echo "Detected NPU device usage in ${DEVICE_ENV_FILE}; using runtime override ${TMP_OVERRIDE}" >&2
  exec docker compose -f "${BASE_COMPOSE}" -f "${TMP_OVERRIDE}" "$@"
elif [[ "${HAS_NPU}" == true ]]; then
  echo "NPU requested by ${DEVICE_ENV_FILE}, but /dev/accel is not present on this host; continuing without NPU device override" >&2
  exec docker compose -f "${BASE_COMPOSE}" "$@"
else
  echo "No NPU devices configured in ${DEVICE_ENV_FILE}; running without NPU override" >&2
  exec docker compose -f "${BASE_COMPOSE}" "$@"
fi