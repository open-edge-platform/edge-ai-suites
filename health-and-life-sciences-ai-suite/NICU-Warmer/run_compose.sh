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

resolve_render_group_id() {
  if getent group render >/dev/null 2>&1; then
    getent group render | cut -d: -f3
    return 0
  fi
  if [[ -e /dev/accel/accel0 ]]; then
    stat -c '%g' /dev/accel/accel0
    return 0
  fi
  if [[ -d /dev/accel ]]; then
    stat -c '%g' /dev/accel
    return 0
  fi
  return 1
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
  # Resolve render group ID for NPU device access
  if ! RENDER_GROUP_ID="$(resolve_render_group_id)"; then
    echo "Unable to resolve the host render group for NPU access. Ensure the render group and /dev/accel devices are available." >&2
    exit 1
  fi

  # The base docker-compose.yaml already grants render group "992" and mounts
  # /dev/dri. Adding them again in the override triggers a
  # "group_add items ... are equal" validation error in modern docker compose.
  # So the override is strictly additive: it only adds items that are NOT in
  # the base. group_add is only appended when the resolved GID differs from
  # the base value ("992"); the /dev/dri mount is intentionally omitted.
  GROUP_ADD_BLOCK=""
  if [[ "${RENDER_GROUP_ID}" != "992" ]]; then
    GROUP_ADD_BLOCK=$'    group_add:\n      - "'"${RENDER_GROUP_ID}"$'"'
  fi

  TMP_OVERRIDE="$(mktemp)"
  trap 'rm -f "${TMP_OVERRIDE}"' EXIT

  cat > "${TMP_OVERRIDE}" <<EOF
services:
  nicu-backend:
    environment:
      - ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so
    devices:
      - /dev/accel/accel0:/dev/accel/accel0
${GROUP_ADD_BLOCK}
  nicu-dlsps:
    environment:
      - ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so
    devices:
      - /dev/accel/accel0:/dev/accel/accel0
${GROUP_ADD_BLOCK}
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