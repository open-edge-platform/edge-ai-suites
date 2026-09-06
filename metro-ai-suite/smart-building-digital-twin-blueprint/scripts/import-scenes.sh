#!/bin/bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

BASE_URL="${BASE_URL:-${API_BASE_URL:-}}"
USERNAME="${USERNAME:-admin}"
PASSWORD="${PASSWORD:-${SUPASS:-}}"
SCENES_DIR="${SCENES_DIR:-./scenes}"

if [ -z "$BASE_URL" ]; then
    echo "ERROR: BASE_URL or API_BASE_URL must be set"
    exit 1
fi

BASE_URL="${BASE_URL%/}"

summarize_body() {
    printf '%s' "$1" | tr '\n' ' ' | cut -c1-200
}

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

get_api_token() {
    local auth_payload="$1"
    local max_attempts=12
    local attempt=1

    while [ "$attempt" -le "$max_attempts" ]; do
        local response_with_status http_status response token
        response_with_status=$(api_curl -X POST "$BASE_URL/auth" \
            -H "Content-Type: application/json" \
            -d "$auth_payload" \
            -w '\n%{http_code}' || true)

        http_status=$(printf '%s\n' "$response_with_status" | tail -n1)
        response=$(printf '%s\n' "$response_with_status" | sed '$d')

        token=$(printf '%s' "$response" | jq -r '.token // empty' 2>/dev/null || true)
        if [ -n "$token" ]; then
            printf '%s\n' "$token"
            return 0
        fi

        if [ "$attempt" -lt "$max_attempts" ]; then
            sleep 5
        fi
        attempt=$((attempt + 1))
    done

    echo "ERROR: Failed to get API token from $BASE_URL/auth" >&2
    echo "Last response: HTTP ${http_status:-none} $(summarize_body "$response")" >&2
    return 1
}

if [ -z "$PASSWORD" ]; then
    echo "ERROR: PASSWORD or SUPASS must be set"
    exit 1
fi

if [ ! -d "$SCENES_DIR" ]; then
    echo "ERROR: Scenes directory not found: $SCENES_DIR"
    exit 1
fi

auth_payload=$(jq -n --arg username "$USERNAME" --arg password "$PASSWORD" '{username: $username, password: $password}')
if ! token=$(get_api_token "$auth_payload"); then
    exit 1
fi

imported_any=false

for scene_zip in "$SCENES_DIR"/*.zip; do
    [ -e "$scene_zip" ] || continue

    scene_name=$(basename "$scene_zip" .zip)
    encoded_name=$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$scene_name")

    existing_count=$(api_curl -H "Authorization: Token $token" \
        "$BASE_URL/scenes?name=$encoded_name" | jq -r '.results | length // 0')

    if [ "$existing_count" != "0" ]; then
        echo "Skipping scene import for $scene_name (already present)"
        continue
    fi

    echo "Importing scene: $scene_name"
    response_with_status=$(api_curl -X POST "$BASE_URL/import-scene/" \
        -H "Authorization: Token $token" \
        -F "zipFile=@${scene_zip}" \
        -w '\n%{http_code}')

    http_status=$(printf '%s\n' "$response_with_status" | tail -n1)
    response=$(printf '%s\n' "$response_with_status" | sed '$d')

    if [ "$http_status" -lt 200 ] || [ "$http_status" -ge 300 ]; then
        echo "ERROR: Scene import failed for $scene_name with HTTP $http_status"
        echo "$response"
        exit 1
    fi

    imported_count=$(api_curl -H "Authorization: Token $token" \
        "$BASE_URL/scenes?name=$encoded_name" | jq -r '.results | length // 0')

    if [ "$imported_count" = "0" ]; then
        echo "ERROR: Scene import for $scene_name returned success but the scene is still missing"
        echo "$response"
        exit 1
    fi

    echo "Imported scene: $scene_name"
    imported_any=true
done

if [ "$imported_any" = false ]; then
    echo "No new scenes needed import"
fi