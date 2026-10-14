#!/bin/sh
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -e
# Only the standalone deployment (no nginx in front) needs a self-signed
# certificate; behind nginx this is left unset and app.py serves plain HTTP.
# app.py itself picks TLS_CERT/TLS_KEY up automatically (os.path.isfile
# check), so generating the files here is this script's only remaining job.
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
fi
exec python3 app.py

