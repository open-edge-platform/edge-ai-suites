#!/bin/sh
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -e
# Only the standalone deployment (no nginx in front) needs a self-signed
# certificate; behind nginx this is left unset and gunicorn serves plain HTTP.
TLS_ARGS=""
if [ "${ENABLE_TLS:-false}" = "true" ]; then
    CERT_DIR=${CERT_DIR:-/app/certs}
    mkdir -p "$CERT_DIR"
    if [ ! -f "$CERT_DIR/console.crt" ] || [ ! -f "$CERT_DIR/console.key" ]; then
        echo "issuing a self-signed certificate for the console"
        openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
            -keyout "$CERT_DIR/console.key" -out "$CERT_DIR/console.crt" \
            -subj "/CN=${HOST_IP:-console}" \
            -addext "subjectAltName=IP:${HOST_IP:-127.0.0.1},DNS:localhost" 2>/dev/null
    fi
    TLS_ARGS="--certfile $CERT_DIR/console.crt --keyfile $CERT_DIR/console.key"
fi
# A single worker is required: SESSIONS/MQTT state live in process memory,
# so more than one worker would each see a different, inconsistent copy.
# Concurrency instead comes from threads within that one worker.
exec gunicorn --workers 1 --threads "${GUNICORN_THREADS:-8}" --timeout 120 \
    --bind "0.0.0.0:${UI_PORT:-9443}" $TLS_ARGS app:app
