#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Generate MQTT credentials for a local NVR deployment.
#
# Idempotent: if the secrets file already exists it is left untouched so
# credentials stay stable across restarts. Use --force to rotate.
#
# Usage:
#   scripts/gen-mqtt-secrets.sh              # generate once, reuse on next run
#   scripts/gen-mqtt-secrets.sh --force      # rotate (invalidates broker state)
#   MQTT_SECRETS_FILE=/path/to/file scripts/gen-mqtt-secrets.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="${MQTT_SECRETS_FILE:-${SCRIPT_DIR}/../resources/mqtt-secrets}"

if [ "${1:-}" = "--force" ]; then
    rm -f "$SECRETS_FILE"
elif [ -f "$SECRETS_FILE" ]; then
    echo "MQTT secrets already present: $SECRETS_FILE (use --force to rotate)"
    exit 0
fi

if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: openssl is required but not found." >&2
    echo "Install openssl, or export MQTT_USER and MQTT_PASSWORD before running setup." >&2
    exit 1
fi

rand() { openssl rand -hex 24; }

mkdir -p "$(dirname "$SECRETS_FILE")"
umask 077
cat > "$SECRETS_FILE" <<EOF
export MQTT_USER="${MQTT_USER:-nvr-$(openssl rand -hex 4)}"
export MQTT_PASSWORD="${MQTT_PASSWORD:-$(rand)}"
EOF

chmod 600 "$SECRETS_FILE"
echo "MQTT secrets generated: $SECRETS_FILE"
