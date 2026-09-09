#!/bin/bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

# Restore object class definitions (assets) from a JSON backup file.
# For each entry in the file:
#   - if an asset with the same name already exists: PUT (update)
#   - otherwise: POST (create)

BASE_URL="${BASE_URL:-${API_BASE_URL:-}}"
USERNAME="${USERNAME:-admin}"
PASSWORD="${PASSWORD:-${SUPASS:-}}"
ASSETS_FILE="${ASSETS_FILE:-config/object-classes.json}"

if [ -z "$BASE_URL" ]; then
    echo "ERROR: BASE_URL or API_BASE_URL must be set"
    exit 1
fi

BASE_URL="${BASE_URL%/}"

is_loopback_api_base_url() {
    local url="$1"
    local host

    host="${url#https://}"
    host="${host#http://}"
    host="${host%%/*}"
    host="${host%%:*}"

    case "$host" in
        localhost|127.0.0.1|::1|[::1])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

api_curl() {
    if is_loopback_api_base_url "$BASE_URL"; then
        curl --noproxy "*" -ksS "$@"
    else
        curl -ksS "$@"
    fi
}

if [ -z "$PASSWORD" ]; then
    echo "ERROR: PASSWORD or SUPASS must be set"
    exit 1
fi

if [ ! -f "$ASSETS_FILE" ]; then
    echo "ERROR: Assets file not found: $ASSETS_FILE"
    exit 1
fi

auth_payload=$(jq -n --arg u "$USERNAME" --arg p "$PASSWORD" '{username: $u, password: $p}')
token=$(api_curl -X POST "$BASE_URL/auth" \
    -H "Content-Type: application/json" \
    -d "$auth_payload" | jq -r '.token // empty')

if [ -z "$token" ]; then
    echo "ERROR: Failed to get API token from $BASE_URL/auth"
    exit 1
fi

AUTH_HEADER="Authorization: Token $token"

# Fetch current asset list once
current=$(api_curl -H "$AUTH_HEADER" "$BASE_URL/assets")

jq -c '.[]' "$ASSETS_FILE" | while read -r asset; do
    name=$(echo "$asset" | jq -r '.name')

    # Skip if an asset with this name already exists
    existing=$(echo "$current" | jq -r --arg name "$name" \
        '.results[] | select(.name == $name) | .uid')

    if [ -n "$existing" ]; then
        echo "[SKIP] Asset already exists: $name (uid=$existing)"
        continue
    fi

    # POST with the backed-up uid; if that uid is taken, retry without it
    result=$(api_curl -w "\n%{http_code}" \
        -X POST -H "$AUTH_HEADER" -H "Content-Type: application/json" \
        -d "$asset" "$BASE_URL/assets")
    http_code=$(echo "$result" | tail -1)
    body=$(echo "$result" | head -1)

    if [ "$http_code" = "201" ]; then
        echo "[OK] Created asset: $name"
    elif echo "$body" | grep -q '"uid"'; then
        # uid conflict — retry without the uid field (server will assign one)
        asset_no_uid=$(echo "$asset" | jq 'del(.uid)')
        result2=$(api_curl -o /dev/null -w "%{http_code}" \
            -X POST -H "$AUTH_HEADER" -H "Content-Type: application/json" \
            -d "$asset_no_uid" "$BASE_URL/assets")
        if [ "$result2" = "201" ]; then
            echo "[OK] Created asset: $name (server-assigned uid)"
        else
            echo "[WARNING] Could not create asset: $name (HTTP $result2)"
        fi
    else
        echo "[WARNING] POST $name returned HTTP $http_code: $body"
    fi
done
