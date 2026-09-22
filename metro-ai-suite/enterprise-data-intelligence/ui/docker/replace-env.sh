#!/bin/sh
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -eu

HTML_ROOT="/usr/share/nginx/html"
NGINX_TEMPLATE="/etc/nginx/templates/default.conf.template"
NGINX_CONF="/etc/nginx/conf.d/default.conf"

require_env() {
    var_name="$1"
    eval "var_value=\${$var_name:-}"

    if [ -z "$var_value" ]; then
        echo "Missing required environment variable: $var_name" >&2
        exit 1
    fi
}

require_env UI_PORT
require_env SERVER_HOST
require_env STATS_API_PORT
require_env VITE_API_BASE_URL
require_env VITE_AUTH_TOKEN
require_env VITE_CHATBOT_URL
require_env VITE_CHATBOT_WS_PORT

mkdir -p "$(dirname "$NGINX_CONF")"
envsubst '${UI_PORT} ${SERVER_HOST} ${STATS_API_PORT} ${VITE_CHATBOT_WS_PORT}' \
    < "$NGINX_TEMPLATE" \
    > "$NGINX_CONF"

if grep -n '\${[A-Za-z_][A-Za-z0-9_]*}' "$NGINX_CONF"; then
    echo "[replace-env] Unresolved nginx template variables remain in $NGINX_CONF" >&2
    exit 1
fi

escape_sed_replacement() {
    printf '%s' "$1" | sed 's/[\\&|]/\\&/g'
}

replace_placeholder() {
    placeholder="$1"
    value="$2"
    escaped_value="$(escape_sed_replacement "$value")"

    find "$HTML_ROOT" -type f \( -name '*.js' -o -name '*.css' -o -name '*.html' \) \
        -exec sed -i "s|${placeholder}|${escaped_value}|g" {} +
}

replace_placeholder "__VITE_API_BASE_URL__" "$VITE_API_BASE_URL"
replace_placeholder "__VITE_AUTH_TOKEN__" "$VITE_AUTH_TOKEN"
replace_placeholder "__VITE_CHATBOT_URL__" "$VITE_CHATBOT_URL"
replace_placeholder "__VITE_CHATBOT_WS_PORT__" "$VITE_CHATBOT_WS_PORT"