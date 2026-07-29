#!/bin/sh
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Docker entrypoint for VMS UI container.
# Generates a self-signed TLS certificate if no user-provided cert exists,
# then starts nginx.

set -e

CERT_DIR="/etc/nginx/certs"

# Generate self-signed cert if user hasn't provided one
/usr/local/bin/generate-certs.sh

exec nginx -g "daemon off;"
