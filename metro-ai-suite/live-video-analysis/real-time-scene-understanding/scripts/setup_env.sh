#!/usr/bin/env bash

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_EXAMPLE="${ROOT_DIR}/.env.example"
ENV_FILE="${ROOT_DIR}/.env"
FORCE=false

usage() {
  cat <<EOF
Usage: bash scripts/setup_env.sh [--force]

Creates ${ENV_FILE} from .env.example and fills host-specific values such as
HOST_IP, WEBRTC_SIGNALING_URL, and RENDER_GROUP_ID.

Options:
  --force     Overwrite an existing .env file.
  -h, --help  Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "${ENV_EXAMPLE}" ]]; then
  echo "ERROR: Missing template: ${ENV_EXAMPLE}" >&2
  exit 1
fi

if [[ -f "${ENV_FILE}" && "${FORCE}" != "true" ]]; then
  echo ".env already exists. Leaving it unchanged."
  echo "Use 'bash scripts/setup_env.sh --force' to regenerate it."
  exit 0
fi

HOST_IP="$(ip route get 1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i == "src") {print $(i+1); exit}}')"
HOST_IP="${HOST_IP:-127.0.0.1}"

WEBRTC_SIGNALING_PORT="$(awk -F= '$1 == "WEBRTC_SIGNALING_PORT" {print $2; exit}' "${ENV_EXAMPLE}")"
WEBRTC_SIGNALING_PORT="${WEBRTC_SIGNALING_PORT:-8889}"
WEBRTC_SIGNALING_URL="http://${HOST_IP}:${WEBRTC_SIGNALING_PORT}"

RENDER_GROUP_ID="$(getent group render 2>/dev/null | cut -d: -f3)"
RENDER_GROUP_ID="${RENDER_GROUP_ID:-992}"

HAS_NPU_DEVICE=false
if [[ -e /dev/accel ]]; then
  HAS_NPU_DEVICE=true
  NPU_DEVICE_PATH="/dev/accel"
fi

HOST_SEGMENTS_DIR="$(awk -F= '$1 == "HOST_SEGMENTS_DIR" {print $2; exit}' "${ENV_EXAMPLE}")"
HOST_SEGMENTS_DIR="${HOST_SEGMENTS_DIR:-/dev/shm/scene-segments}"
mkdir -p "${HOST_SEGMENTS_DIR}"

tmp_file="$(mktemp)"
trap 'rm -f "${tmp_file}"' EXIT

while IFS= read -r line || [[ -n "$line" ]]; do
  case "$line" in
    HOST_IP=*)
      printf 'HOST_IP=%s\n' "${HOST_IP}" >> "${tmp_file}"
      ;;
    WEBRTC_SIGNALING_URL=*)
      printf 'WEBRTC_SIGNALING_URL=%s\n' "${WEBRTC_SIGNALING_URL}" >> "${tmp_file}"
      ;;
    RENDER_GROUP_ID=*)
      printf 'RENDER_GROUP_ID=%s\n' "${RENDER_GROUP_ID}" >> "${tmp_file}"
      ;;
    NPU_DEVICE_PATH=*)
      if [[ "${HAS_NPU_DEVICE}" == "true" ]]; then
        printf 'NPU_DEVICE_PATH=%s\n' "${NPU_DEVICE_PATH}" >> "${tmp_file}"
      fi
      ;;
    *)
      printf '%s\n' "$line" >> "${tmp_file}"
      ;;
  esac
done < "${ENV_EXAMPLE}"

if [[ "${HAS_NPU_DEVICE}" == "true" ]] && ! grep -q '^NPU_DEVICE_PATH=' "${tmp_file}"; then
  printf 'NPU_DEVICE_PATH=%s\n' "${NPU_DEVICE_PATH}" >> "${tmp_file}"
fi

mv "${tmp_file}" "${ENV_FILE}"
trap - EXIT

echo "Created ${ENV_FILE}"
echo "HOST_IP=${HOST_IP}"
echo "WEBRTC_SIGNALING_URL=${WEBRTC_SIGNALING_URL}"
echo "RENDER_GROUP_ID=${RENDER_GROUP_ID}"
echo "HOST_SEGMENTS_DIR=${HOST_SEGMENTS_DIR}"
echo "UI URL: http://${HOST_IP}:9100"
if [[ "${HAS_NPU_DEVICE}" == "true" ]]; then
  echo "NPU device detected. NPU_DEVICE_PATH=${NPU_DEVICE_PATH}"
fi
