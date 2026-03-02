#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "${ROOT_DIR}/configs/device.env" ]]; then
  echo "configs/device.env not found; running without NPU override" >&2
  exec docker compose -f "${ROOT_DIR}/docker-compose.yaml" up "$@"
fi

source "${ROOT_DIR}/configs/device.env"

TMP_OVERRIDE="$(mktemp)"
trap 'rm -f "${TMP_OVERRIDE}"' EXIT

echo "services:" > "${TMP_OVERRIDE}"

HAS_NPU=false

if [[ "${ECG_DEVICE:-}" == "NPU" ]]; then
  HAS_NPU=true
  cat >> "${TMP_OVERRIDE}" <<EOF
  ai-ecg:
    environment:
      - ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so
    devices:
      - "/dev/dri:/dev/dri"
      - "/dev/accel/accel0:/dev/accel/accel0"
EOF
fi

if [[ "${POSE_3D_DEVICE:-}" == "NPU" ]]; then
  HAS_NPU=true
  cat >> "${TMP_OVERRIDE}" <<EOF
  3dpose-estimation:
    environment:
      - ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so
    devices:
      - "/dev/dri:/dev/dri"
      - "/dev/accel/accel0:/dev/accel/accel0"
EOF
fi

if [[ "${RPPG_DEVICE:-}" == "NPU" ]]; then
  HAS_NPU=true
  cat >> "${TMP_OVERRIDE}" <<EOF
  rppg:
    environment:
      - ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so
    devices:
      - "/dev/dri:/dev/dri"
      - "/dev/accel/accel0:/dev/accel/accel0"
EOF
fi

if [[ "${HAS_NPU}" == true ]]; then
  echo "Detected NPU devices in configs/device.env; using runtime override ${TMP_OVERRIDE}" >&2
  exec docker compose --env-file "${ROOT_DIR}/configs/device.env" -f "${ROOT_DIR}/docker-compose.yaml" -f "${TMP_OVERRIDE}" up "$@"
else
  echo "No NPU devices configured in configs/device.env; running without NPU override" >&2
  exec docker compose --env-file "${ROOT_DIR}/configs/device.env" -f "${ROOT_DIR}/docker-compose.yaml" up "$@"
fi

