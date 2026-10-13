#!/usr/bin/env bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Fetch CA certificates from remote SceneScape child machines and build
# a combined trust bundle so the parent controller can establish TLS
# connections to all remote brokers.
#
# Usage:
#   ./federate.sh <remote_ip1[:port]> [remote_ip2[:port]] ...
#
# Each remote machine must be running the ca-server service (port 8888
# by default) which serves its CA certificate over HTTP.
#
# The script:
#   1. Backs up the local CA to scenescape-ca-local.pem (first run only)
#   2. Fetches each remote machine's CA via HTTP
#   3. Validates each downloaded certificate
#   4. Concatenates local + all remote CAs into scenescape-ca.pem
#
# After running this script, restart the scene controller:
#   cd .. && docker compose up -d scene

set -euo pipefail

DEFAULT_PORT=8888
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CA_DIR="${SCRIPT_DIR}/src/secrets/certs"
LOCAL_CA="${CA_DIR}/scenescape-ca-local.pem"
BUNDLE="${CA_DIR}/scenescape-ca.pem"
REMOTE_CA_DIR="${CA_DIR}/remote-cas"

if [[ $# -lt 1 ]]; then
    # Try to read remote IPs from .env file
    ENV_FILE="${SCRIPT_DIR}/../.env"
    if [[ -f "$ENV_FILE" ]]; then
        TOTAL=$(grep -E "^TOTAL_REMOTE_CHILD=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' || echo "0")
        if [[ "$TOTAL" -gt 0 ]] 2>/dev/null; then
            REMOTES=()
            for i in $(seq 1 "$TOTAL"); do
                IP=$(grep -E "^REMOTE_IP_${i}=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d ' ')
                if [[ -n "$IP" ]]; then
                    REMOTES+=("$IP")
                fi
            done
            if [[ ${#REMOTES[@]} -gt 0 ]]; then
                echo "Reading remote IPs from .env: ${REMOTES[*]}"
                set -- "${REMOTES[@]}"
            fi
        fi
    fi

    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 <remote_ip1[:port]> [remote_ip2[:port]] ..."
        echo ""
        echo "Or set TOTAL_REMOTE_CHILD and REMOTE_IP_N in ../.env"
        echo ""
        echo "Examples:"
        echo "  $0 10.223.22.20                    # single remote, default port 8888"
        echo "  $0 10.223.22.20 10.223.22.30       # two remotes"
        echo "  $0 10.223.22.20:9999               # custom port"
        exit 1
    fi
fi

# Back up the original local CA on first run
if [[ ! -f "$LOCAL_CA" ]]; then
    echo "Backing up local CA certificate..."
    cp "$BUNDLE" "$LOCAL_CA"
fi

# Create directory for remote CA certificates
mkdir -p "$REMOTE_CA_DIR"

# Start the bundle with the local CA
cp "$LOCAL_CA" "$BUNDLE"
echo "Local CA: $(openssl x509 -in "$LOCAL_CA" -noout -subject 2>/dev/null || echo 'unknown')"

FAIL=0
for REMOTE in "$@"; do
    # Parse IP and optional port
    if [[ "$REMOTE" == *":"* ]]; then
        REMOTE_IP="${REMOTE%%:*}"
        REMOTE_PORT="${REMOTE##*:}"
    else
        REMOTE_IP="$REMOTE"
        REMOTE_PORT="$DEFAULT_PORT"
    fi

    REMOTE_CA="${REMOTE_CA_DIR}/ca-${REMOTE_IP}.pem"
    echo ""
    echo "Fetching CA from ${REMOTE_IP}:${REMOTE_PORT}..."

    if ! curl -sf --connect-timeout 5 --max-time 10 \
         "http://${REMOTE_IP}:${REMOTE_PORT}/scenescape-ca.pem" \
         -o "$REMOTE_CA"; then
        echo "  ERROR: Failed to fetch CA from ${REMOTE_IP}:${REMOTE_PORT}"
        echo "  Ensure the remote machine is running and ca-server is accessible."
        FAIL=1
        continue
    fi

    # Validate it's a real certificate
    if ! openssl x509 -in "$REMOTE_CA" -noout 2>/dev/null; then
        echo "  ERROR: Downloaded file is not a valid X.509 certificate"
        rm -f "$REMOTE_CA"
        FAIL=1
        continue
    fi

    SUBJECT=$(openssl x509 -in "$REMOTE_CA" -noout -subject 2>/dev/null)
    echo "  Retrieved: ${SUBJECT}"

    # Append to bundle
    echo "" >> "$BUNDLE"
    cat "$REMOTE_CA" >> "$BUNDLE"
    echo "  Added to trust bundle"
done

echo ""
CERT_COUNT=$(grep -c 'BEGIN CERTIFICATE' "$BUNDLE")
echo "Trust bundle: ${BUNDLE}"
echo "Contains ${CERT_COUNT} CA certificate(s)"

if [[ $FAIL -ne 0 ]]; then
    echo ""
    echo "WARNING: Some remote CAs could not be fetched. The bundle is incomplete."
    exit 1
fi

echo ""
echo "Federation complete. Restart the scene controller to apply:"
echo "  cd $(dirname "$SCRIPT_DIR") && docker compose up -d scene"
