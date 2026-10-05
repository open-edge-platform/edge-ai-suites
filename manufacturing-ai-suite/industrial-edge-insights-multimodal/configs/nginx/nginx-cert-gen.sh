#!/bin/bash
#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# Set working directory for SSL certificates
SSL_DIR="/opt/nginx/certs"
mkdir -p "$SSL_DIR"
if [ -d "$SSL_DIR" ]; then rm -rf "${SSL_DIR:?}"/*; fi

# Generate htpasswd file for HTTP Basic Auth in front of the SeaweedFS filer
# web UI, proxied at /image-store. The nginx image doesn't ship the
# htpasswd utility, so use openssl to produce an APR1-hashed credential line.
: "${SEAWEEDFS_WEB_AUTH_USER:?SEAWEEDFS_WEB_AUTH_USER is required}"
: "${SEAWEEDFS_WEB_AUTH_PASSWORD:?SEAWEEDFS_WEB_AUTH_PASSWORD is required}"
echo "${SEAWEEDFS_WEB_AUTH_USER}:$(openssl passwd -apr1 "${SEAWEEDFS_WEB_AUTH_PASSWORD}")" > "$SSL_DIR/.htpasswd"
chmod 640 "$SSL_DIR/.htpasswd"

# Render the profile-specific server locations (insights-ui, agentic-ui,
# metrics API) included by nginx.conf.template, and the matching gateway
# timeouts. "base" has no extra locations and keeps nginx's 60s defaults;
# "agentic" adds all of them; "vllm" adds only insights-ui. These values
# reproduce what used to be three separate, duplicated nginx.conf files.
case "${NGINX_PROFILE:-base}" in
    agentic)
        NGINX_DEFAULT_TIMEOUT="${NGINX_DEFAULT_TIMEOUT:-60s}"
        NGINX_STREAM_TIMEOUT="${NGINX_STREAM_TIMEOUT:-300s}"
        cat > "$SSL_DIR/nginx-extra-locations.conf" <<'EOF'
        location = /insights-ui {
            return 308 /insights-ui/;
        }

        location /insights-ui/ {
            proxy_pass http://multimodal-agentic-ui:5003;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
        }

        # APM UI Server
        location /agentic-ui/ {
            proxy_pass http://multimodal-agentic-ui:5003;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
        }

        # Metrics API — /api/metrics/* routed to metrics-manager /metrics/*
        # Includes SSE stream support (/api/metrics/stream → /metrics/stream)
        # Uses variable-based proxy_pass so nginx starts even if apm-metrics
        # is not yet running (resolved at request time via Docker DNS).
        location /api/metrics/ {
            resolver 127.0.0.11 valid=10s ipv6=off;
            set $metrics_upstream http://apm-metrics:9090;
            rewrite ^/api(/metrics/.*)$ $1 break;
            proxy_pass $metrics_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header Connection '';
            proxy_http_version 1.1;
            chunked_transfer_encoding off;
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 3600s;
        }

        # Capabilities API — proxied as-is to metrics-manager's
        # /api/v1/capabilities endpoint (reports CPU/GPU/NPU presence and
        # specs so the dashboard can render system resource cards).
        location /api/v1/capabilities {
            resolver 127.0.0.11 valid=10s ipv6=off;
            set $metrics_upstream http://apm-metrics:9090;
            proxy_pass $metrics_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 15s;
        }
EOF
        ;;
    vllm)
        NGINX_DEFAULT_TIMEOUT="${NGINX_DEFAULT_TIMEOUT:-180s}"
        NGINX_STREAM_TIMEOUT="${NGINX_STREAM_TIMEOUT:-180s}"
        cat > "$SSL_DIR/nginx-extra-locations.conf" <<'EOF'
        location = /insights-ui {
            return 308 /insights-ui/;
        }

        location /insights-ui/ {
            proxy_pass http://multimodal-agentic-ui:5003;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
        }
EOF
        ;;
    *)
        NGINX_DEFAULT_TIMEOUT="${NGINX_DEFAULT_TIMEOUT:-60s}"
        NGINX_STREAM_TIMEOUT="${NGINX_STREAM_TIMEOUT:-300s}"
        : > "$SSL_DIR/nginx-extra-locations.conf"
        ;;
esac
export NGINX_DEFAULT_TIMEOUT NGINX_STREAM_TIMEOUT

# Set default values for SSL parameters if not provided
KEY_LENGTH=3072
DAYS=365
SHA_ALGO="sha384"

echo "Generating SSL certificates for Nginx..."

envsubst '$MEDIAMTX_SERVER $WHIP_SERVER_PORT $NGINX_DEFAULT_TIMEOUT $NGINX_STREAM_TIMEOUT' < /tmp/default.conf.template > /etc/nginx/nginx.conf

openssl req -x509 -nodes -days ${DAYS} -${SHA_ALGO} -newkey rsa:${KEY_LENGTH} -keyout "$SSL_DIR/key.pem" -out "$SSL_DIR/cert.pem" -subj "/CN=localhost"
chmod 640 "$SSL_DIR/key.pem" "$SSL_DIR/cert.pem"