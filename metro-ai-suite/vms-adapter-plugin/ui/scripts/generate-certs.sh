#!/bin/sh
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Generate a self-signed TLS certificate for the VMS UI dashboard.
# Skips generation if cert and key already exist at the target path.

set -e

CERT_DIR="${CERT_DIR:-/etc/nginx/certs}"
CERT_FILE="${CERT_DIR}/cert.pem"
KEY_FILE="${CERT_DIR}/key.pem"
DAYS_VALID="${CERT_DAYS_VALID:-365}"
SUBJECT="${CERT_SUBJECT:-/CN=vms-adapter-ui/O=Intel Corporation}"

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    echo "TLS certificate already exists at ${CERT_DIR}, skipping generation."
    exit 0
fi

mkdir -p "$CERT_DIR"

echo "Generating self-signed TLS certificate (valid for ${DAYS_VALID} days)..."
openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -days "$DAYS_VALID" \
    -subj "$SUBJECT" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
    2>/dev/null

chmod 644 "$CERT_FILE"
chmod 640 "$KEY_FILE"

echo "Self-signed TLS certificate generated at ${CERT_DIR}."
