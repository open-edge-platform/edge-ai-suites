#!/bin/bash
#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# Set working directory for SSL certificates
SSL_DIR="/opt/bitnami/nginx/conf/bitnami/certs"
mkdir -p "$SSL_DIR"

# Set default values for SSL parameters if not provided
KEY_LENGTH=3072
DAYS=365
SHA_ALGO="sha384"

echo "Generating SSL certificates for Nginx..."
if [ -d $SSL_DIR ]; then rm -rf $SSL_DIR; fi
	mkdir -p $SSL_DIR
	openssl req -x509 -nodes -days ${DAYS} -${SHA_ALGO} -newkey rsa:${KEY_LENGTH} -keyout $SSL_DIR/key.pem -out $SSL_DIR/cert.pem -subj "/CN=localhost"
	chmod 640 $SSL_DIR/key.pem $SSL_DIR/cert.pem
