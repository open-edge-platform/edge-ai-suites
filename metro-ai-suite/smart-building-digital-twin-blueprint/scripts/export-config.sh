#!/bin/bash
set -euo pipefail

# Export object class definitions and scene configurations from the live API.
# Run this after making changes in the Scenescape UI to capture the current
# state for version control.
#
# Outputs:
#   config/object-classes.json     — all asset/object-class definitions
#   config/scenes/{name}.json      — full scene config (cameras, regions, etc.)
#
# These files are consumed by:
#   scripts/restore-assets.sh      — on setup to recreate object classes
#   (scene JSON is for reference; re-import uses the zip in scenes/)

BASE_URL="${BASE_URL:-${API_BASE_URL:-}}"
USERNAME="${USERNAME:-admin}"
PASSWORD="${PASSWORD:-${SUPASS:-}}"
OUTPUT_DIR="${OUTPUT_DIR:-.}"

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

# ── Auth ──────────────────────────────────────────────────────────────────────
auth_payload=$(jq -n --arg u "$USERNAME" --arg p "$PASSWORD" '{username: $u, password: $p}')
token=$(api_curl -X POST "$BASE_URL/auth" \
    -H "Content-Type: application/json" \
    -d "$auth_payload" | jq -r '.token // empty')

if [ -z "$token" ]; then
    echo "ERROR: Failed to get API token from $BASE_URL/auth"
    exit 1
fi

AUTH_HEADER="Authorization: Token $token"

# ── Export assets ─────────────────────────────────────────────────────────────
ASSETS_FILE="$OUTPUT_DIR/config/object-classes.json"
mkdir -p "$(dirname "$ASSETS_FILE")"

echo "Exporting object class library..."
response=$(api_curl -H "$AUTH_HEADER" "$BASE_URL/assets")
count=$(echo "$response" | jq -r '.count // 0')
echo "$response" | jq '[.results[]]' > "$ASSETS_FILE"
echo "[OK] $count asset(s) → $ASSETS_FILE"

# ── Export scenes ─────────────────────────────────────────────────────────────
SCENES_DIR="$OUTPUT_DIR/config/scenes"
mkdir -p "$SCENES_DIR"

echo "Exporting scene configurations..."
scenes=$(api_curl -H "$AUTH_HEADER" "$BASE_URL/scenes")
scene_count=$(echo "$scenes" | jq -r '.count // 0')

echo "$scenes" | jq -c '.results[]' | while read -r scene; do
    uid=$(echo "$scene" | jq -r '.uid')
    name=$(echo "$scene" | jq -r '.name')
    outfile="$SCENES_DIR/${name}.json"

    api_curl -H "$AUTH_HEADER" "$BASE_URL/scene/$uid" | jq '.' > "$outfile"
    echo "[OK] Scene: $name → $outfile"
done

echo "Done — $scene_count scene(s) exported."
