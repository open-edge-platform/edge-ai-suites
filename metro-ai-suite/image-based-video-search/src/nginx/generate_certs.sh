#!/bin/sh
set -e

SSL_DIR="/etc/nginx/ssl"
mkdir -p "$SSL_DIR"

# Install openssl if missing
if ! command -v openssl >/dev/null 2>&1; then
    echo "Installing openssl..."
    apk add --no-cache openssl
fi

# Generate self-signed cert if not present
if [ ! -f "$SSL_DIR/server.crt" ] || [ ! -f "$SSL_DIR/server.key" ]; then
  echo "🔐 Generating self-signed SSL certificate..."
  openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "$SSL_DIR/server.key" \
    -out "$SSL_DIR/server.crt" \
    -subj "/C=US/ST=CA/L=San Francisco/O=Intel/OU=Edge AI/CN=localhost"
fi

# Start nginx
nginx -g "daemon off;"