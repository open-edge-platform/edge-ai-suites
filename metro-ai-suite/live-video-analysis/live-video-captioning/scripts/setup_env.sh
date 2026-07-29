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

Creates ${ENV_FILE} from .env.example and fills values that are specific to
this host, including HOST_IP.

Options:
  --force   Overwrite an existing .env file.
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

if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  case "${ID:-}" in
    debian|ubuntu)
      ;;
    *)
      echo "WARNING: This Docker Compose quickstart is validated only on Debian/Ubuntu." >&2
      ;;
  esac
fi

tmp_file="$(mktemp)"
trap 'rm -f "${tmp_file}"' EXIT

while IFS= read -r line || [[ -n "$line" ]]; do
  case "$line" in
    HOST_IP=*)
      printf 'HOST_IP=%s\n' "${HOST_IP}" >> "${tmp_file}"
      ;;
    *)
      printf '%s\n' "$line" >> "${tmp_file}"
      ;;
  esac
done < "${ENV_EXAMPLE}"

mv "${tmp_file}" "${ENV_FILE}"
trap - EXIT

echo "Created ${ENV_FILE}"
echo "HOST_IP=${HOST_IP}"
echo "Dashboard URL: http://${HOST_IP}:4173"
