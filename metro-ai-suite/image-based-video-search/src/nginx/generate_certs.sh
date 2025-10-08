#!/bin/sh
set -e

SSL_DIR="/etc/nginx/ssl"

# Generate self-signed cert if not present
if [ ! -f "$SSL_DIR/server.crt" ] || [ ! -f "$SSL_DIR/server.key" ]; then
  echo "🔐 Generating self-signed SSL certificate..."
  openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "$SSL_DIR/server.key" \
    -out "$SSL_DIR/server.crt" \
    -subj "/C=IN/ST=KA/L=Bangalore/O=MyCompany/OU=Dev/CN=localhost"
fi

# Start nginx
nginx -g "daemon off;"