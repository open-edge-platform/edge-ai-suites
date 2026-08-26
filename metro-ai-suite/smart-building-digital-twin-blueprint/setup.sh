#!/bin/bash
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -e

# Smart Building Digital Twin Blueprint - Setup Script
# Automates deployment of Scenescape with custom models and scenes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Smart Building Digital Twin Blueprint - Setup"
echo "----------------------------------------------"
echo ""

info() { echo "[INFO] $1"; }
success() { echo "[OK] $1"; }
warning() { echo "[WARNING] $1"; }
error() { echo "[ERROR] $1"; exit 1; }

WAIT_FOR_API_LAST_SUMMARY=""
SCENESCAPE_API_BASE_URL=""
XPU_SMI_BRIDGE_PID_FILE="$SCRIPT_DIR/generated/telemetry/xpu-smi.pid"
XPU_SMI_BRIDGE_LOG_FILE="$SCRIPT_DIR/generated/telemetry/xpu-smi.log"
XPU_SMI_BRIDGE_JSON_FILE="$SCRIPT_DIR/generated/telemetry/xpu-smi.json"

read_env_var() {
    local key="$1"
    [ -f ".env" ] || return 0
    grep -E "^${key}=" .env | head -n1 | cut -d'=' -f2-
}

json_truthy() {
    jq -e '
        if type == "object" then
            [ .databaseReady?, .database_ready?, .ready? ]
            | map(
                if type == "boolean" then .
                elif type == "string" then (ascii_downcase == "true")
                else false
                end
            )
            | any
        elif type == "boolean" then .
        elif type == "string" then (ascii_downcase == "true")
        else false
        end
    ' >/dev/null 2>&1
}

auth_probe_ready() {
    jq -e '
        if type != "object" then
            false
        else
            has("token")
            or ((.non_field_errors? // []) | type == "array" and length > 0)
            or (((.detail? // "") | tostring | ascii_downcase) | test("incorrect|invalid|unauthorized"))
        end
    ' >/dev/null 2>&1
}

summarize_probe_body() {
    printf '%s' "$1" | tr '\n' ' ' | cut -c1-160
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
    if is_loopback_api_base_url "$SCENESCAPE_API_BASE_URL"; then
        curl --noproxy "*" -ksS "$@"
    else
        curl -ksS "$@"
    fi
}

get_web_health_status() {
    local container_id
    container_id=$(docker compose ps -q web 2>/dev/null || true)
    if [ -z "$container_id" ]; then
        return 0
    fi
    docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true
}

wait_for_api() {
    local max_attempts="$1"
    local attempt=1
    local auth_payload='{"username":"readiness-probe","password":"readiness-probe"}'
    local api_base_url="${SCENESCAPE_API_BASE_URL%/}"

    if [ -z "$api_base_url" ]; then
        WAIT_FOR_API_LAST_SUMMARY="API base URL is not configured"
        return 1
    fi

    while [ "$attempt" -le "$max_attempts" ]; do
        local web_health
        web_health=$(get_web_health_status)
        if [ "$web_health" = "healthy" ]; then
            WAIT_FOR_API_LAST_SUMMARY="web container healthcheck is healthy"
            return 0
        fi

        local db_response db_status db_body
        db_response=$(api_curl --max-time 10 -w $'\n%{http_code}' "${api_base_url}/database-ready" 2>/dev/null || true)
        db_status="${db_response##*$'\n'}"
        db_body="${db_response%$'\n'*}"

        if [ -n "$db_body" ] && printf '%s' "$db_body" | json_truthy; then
            WAIT_FOR_API_LAST_SUMMARY="database-ready returned ready"
            return 0
        fi

        local auth_response auth_status auth_body
        auth_response=$(api_curl --max-time 10 -H "Content-Type: application/json" -X POST -d "$auth_payload" -w $'\n%{http_code}' "${api_base_url}/auth" 2>/dev/null || true)
        auth_status="${auth_response##*$'\n'}"
        auth_body="${auth_response%$'\n'*}"

        if [ -n "$auth_body" ] && printf '%s' "$auth_body" | auth_probe_ready; then
            WAIT_FOR_API_LAST_SUMMARY="auth endpoint is responding (HTTP ${auth_status}) even though database-ready was not truthy yet"
            return 0
        fi

        WAIT_FOR_API_LAST_SUMMARY="web health ${web_health:-unknown}; database-ready HTTP ${db_status:-none}: $(summarize_probe_body "$db_body"); auth HTTP ${auth_status:-none}: $(summarize_probe_body "$auth_body")"
        sleep 5
        attempt=$((attempt + 1))
    done
    return 1
}

start_sensor_replay() {
    local scene_name="$1"
    local sensor_file="scenes/${scene_name}-sensors.json"
    local service_name="sensor-replay-showcase"
    local container_name="scenescape-sensor-replay-showcase-1"

    if [ ! -f "$sensor_file" ]; then
        return 0
    fi

    info "Starting sensor replay for ${scene_name}..."
    docker compose up -d "$service_name" >/dev/null

    sleep 2
    if docker inspect -f '{{.State.Running}}' "$container_name" 2>/dev/null | grep -q true; then
        success "Sensor replay running for ${scene_name}"
    else
        warning "Sensor replay did not stay running for ${scene_name}"
    fi
}

stop_xpu_smi_bridge() {
    local pid
    if [ ! -f "$XPU_SMI_BRIDGE_PID_FILE" ]; then
        return 0
    fi

    pid=$(cat "$XPU_SMI_BRIDGE_PID_FILE" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        for _ in 1 2 3 4 5; do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi
    rm -f "$XPU_SMI_BRIDGE_PID_FILE"
}

start_xpu_smi_bridge() {
    if ! command -v xpu-smi >/dev/null 2>&1; then
        warning "xpu-smi is not installed; Xe GPU telemetry will remain unavailable until the host dependency is installed"
        return 0
    fi

    mkdir -p "$(dirname "$XPU_SMI_BRIDGE_PID_FILE")"
    stop_xpu_smi_bridge

    info "Starting host xpu-smi telemetry bridge..."
    nohup bash -lc '
        cd "$1"
        while true; do
            python3 scripts/xpu_smi_bridge.py --output "$2"
            sleep 1
        done
    ' _ "$SCRIPT_DIR" "$XPU_SMI_BRIDGE_JSON_FILE" \
        >"$XPU_SMI_BRIDGE_LOG_FILE" 2>&1 &
    bridge_pid=$!
    echo "$bridge_pid" > "$XPU_SMI_BRIDGE_PID_FILE"

    sleep 2
    if kill -0 "$bridge_pid" 2>/dev/null; then
        success "Host xpu-smi telemetry bridge running (pid $bridge_pid)"
    else
        warning "Host xpu-smi telemetry bridge did not stay running"
        if [ -f "$XPU_SMI_BRIDGE_LOG_FILE" ]; then
            warning "Bridge log: $(tail -n 1 "$XPU_SMI_BRIDGE_LOG_FILE" 2>/dev/null || true)"
        fi
    fi
}

verify_telemetry() {
    local bridge_status="missing"
    local bridge_percent=""
    local analytics_snapshot
    local analytics_gpu_status="missing"
    local analytics_memory_status="missing"
    local analytics_storage_status="missing"

    if command -v xpu-smi >/dev/null 2>&1; then
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            if [ -s "$XPU_SMI_BRIDGE_JSON_FILE" ]; then
                bridge_status=$(python3 - "$XPU_SMI_BRIDGE_JSON_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("missing")
    raise SystemExit

percent = payload.get("percent")
status = payload.get("status") or "missing"
print(status)
print("" if percent is None else percent)
PY
)
                bridge_percent=$(printf '%s\n' "$bridge_status" | tail -n 1)
                bridge_status=$(printf '%s\n' "$bridge_status" | head -n 1)
                if [ "$bridge_status" = "ok" ]; then
                    success "Telemetry bridge ready (GPU ${bridge_percent}%)"
                    break
                fi
            fi
            sleep 1
        done

        if [ "$bridge_status" != "ok" ]; then
            warning "Telemetry bridge did not report GPU utilization after setup (status: $bridge_status)"
            warning "Bridge diagnostics: $XPU_SMI_BRIDGE_JSON_FILE and $XPU_SMI_BRIDGE_LOG_FILE"
        fi
    else
        warning "Host xpu-smi is not installed; GPU telemetry is disabled until it is installed and setup is re-run"
    fi

    if docker compose ps --services --filter "status=running" | grep -q '^scene-narrator$'; then
        analytics_snapshot=$(docker compose exec -T scene-narrator python3 -c "import sys, json; sys.path.insert(0, '/app/scripts'); from system_telemetry import SystemTelemetry; snap = SystemTelemetry().snapshot(); print(json.dumps({'gpu': snap.get('gpu', {}).get('status', 'missing'), 'cpu_power': 'ok' if snap.get('cpu', {}).get('power_watts') is not None else 'missing', 'memory': 'ok' if snap.get('memory', {}).get('total_bytes') is not None else 'missing', 'storage': 'ok' if snap.get('storage', {}).get('total_bytes') is not None else 'missing'}))" 2>/dev/null || true)
        if [ -n "$analytics_snapshot" ]; then
            analytics_gpu_status=$(printf '%s' "$analytics_snapshot" | jq -r '.gpu // "missing"' 2>/dev/null || printf 'missing')
            analytics_cpu_power_status=$(printf '%s' "$analytics_snapshot" | jq -r '.cpu_power // "missing"' 2>/dev/null || printf 'missing')
            analytics_memory_status=$(printf '%s' "$analytics_snapshot" | jq -r '.memory // "missing"' 2>/dev/null || printf 'missing')
            analytics_storage_status=$(printf '%s' "$analytics_snapshot" | jq -r '.storage // "missing"' 2>/dev/null || printf 'missing')
            if [ "$analytics_memory_status" = "ok" ] && [ "$analytics_storage_status" = "ok" ]; then
                success "Analytics telemetry available (memory=$analytics_memory_status storage=$analytics_storage_status gpu=$analytics_gpu_status cpu_power=$analytics_cpu_power_status)"
            else
                warning "Analytics telemetry check incomplete (memory=$analytics_memory_status storage=$analytics_storage_status gpu=$analytics_gpu_status cpu_power=$analytics_cpu_power_status)"
            fi
        else
            warning "Could not query analytics telemetry snapshot after setup"
        fi
    fi
}

xpu_smi_needs_host_access() {
    local output
    output=$(xpu-smi dump -d 0 -m 0 -i 1 -n 1 2>&1 || true)
    printf '%s' "$output" | grep -qi "Elevated privileges required"
}

configure_xpu_smi_host_access() {
    if ! command -v xpu-smi >/dev/null 2>&1; then
        return 0
    fi

    if ! xpu_smi_needs_host_access; then
        return 0
    fi

    if [ ! -t 0 ]; then
        warning "xpu-smi needs host permission changes for Xe telemetry, but setup is non-interactive so sudo cannot be used"
        return 0
    fi

    info "Granting host access to MEI/PMT telemetry devices for xpu-smi and RAPL power telemetry..."
    if sudo sh -c '
        for dev in /dev/mei*; do
            [ -e "$dev" ] || continue
            chmod o+rw "$dev"
        done
        find /sys/class/intel_pmt -maxdepth 2 -name telem -exec chmod o+r {} + 2>/dev/null || true
        find /sys/class/powercap -path "*/intel-rapl:*/*" \( -name energy_uj -o -name max_energy_range_uj -o -name power_uw -o -name name \) -exec chmod o+r {} + 2>/dev/null || true
    '; then
        success "Host telemetry device permissions updated for xpu-smi and RAPL"
    else
        warning "Could not update host telemetry permissions for xpu-smi and RAPL"
    fi
}

# Check prerequisites
info "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || error "Docker is not installed"
command -v docker compose >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1 || error "Docker Compose is not installed"
command -v jq >/dev/null 2>&1 || error "jq is not installed (apt-get install jq)"
command -v python3 >/dev/null 2>&1 || error "Python3 is not installed"
command -v openssl >/dev/null 2>&1 || error "OpenSSL is not installed"

success "Prerequisites check passed"

# Locate or fetch the DLStreamer GST plugin scripts needed by showcase-cameras
info "Locating DLStreamer GST plugins..."

SCENESCAPE_PLUGINS_DIR="$SCRIPT_DIR/generated/scenescape-plugins"
# SCENESCAPE_PLUGINS_REF selects the branch or tag for the gstplugins sparse clone independently of the image SCENESCAPE_IMAGE_TAG
SCENESCAPE_PLUGINS_REF="${SCENESCAPE_PLUGINS_REF:-$(grep -E '^SCENESCAPE_PLUGINS_REF=' .env 2>/dev/null | head -n1 | cut -d'=' -f2-)}"
SCENESCAPE_PLUGINS_REF="${SCENESCAPE_PLUGINS_REF:-2026.2.0-rc1}"

scenescape_valid() {
    [ -d "$1/dlstreamer-pipeline-server/user_scripts/gstplugins" ]
}

# Honour an explicit override first, then fall back to a previous sparse clone,
# then perform a new sparse shallow clone of only the gstplugins directory.
SCENESCAPE_DIR_INPUT="${SCENESCAPE_DIR:-}"
if [ -z "$SCENESCAPE_DIR_INPUT" ] && [ -f ".env" ]; then
    SCENESCAPE_DIR_INPUT=$(grep -E '^SCENESCAPE_DIR=' .env | head -n1 | cut -d'=' -f2-)
fi

if [ -n "$SCENESCAPE_DIR_INPUT" ]; then
    SCENESCAPE_DIR_INPUT=$(realpath -m "$SCENESCAPE_DIR_INPUT")
fi

if [ -n "$SCENESCAPE_DIR_INPUT" ] && scenescape_valid "$SCENESCAPE_DIR_INPUT"; then
    success "GST plugins found at: $SCENESCAPE_DIR_INPUT"
elif scenescape_valid "$SCENESCAPE_PLUGINS_DIR"; then
    SCENESCAPE_DIR_INPUT="$SCENESCAPE_PLUGINS_DIR"
    success "GST plugins found at: $SCENESCAPE_DIR_INPUT (from previous setup)"
else
    if [ -n "$SCENESCAPE_DIR_INPUT" ]; then
        warning "SCENESCAPE_DIR '$SCENESCAPE_DIR_INPUT' does not contain dlstreamer-pipeline-server/user_scripts/gstplugins"
    fi
    info "Cloning Scenescape GST plugin scripts (sparse, depth 1, ref ${SCENESCAPE_PLUGINS_REF})..."
    command -v git >/dev/null 2>&1 || error "git is required to clone the GST plugins"
    rm -rf "$SCENESCAPE_PLUGINS_DIR"
    mkdir -p "$SCENESCAPE_PLUGINS_DIR"
    git clone \
        --depth 1 \
        --filter=blob:none \
        --sparse \
        --branch "$SCENESCAPE_PLUGINS_REF" \
        https://github.com/open-edge-platform/scenescape.git \
        "$SCENESCAPE_PLUGINS_DIR" \
        || error "Failed to clone Scenescape GST plugins from GitHub"
    (cd "$SCENESCAPE_PLUGINS_DIR" && git sparse-checkout set dlstreamer-pipeline-server/user_scripts/gstplugins) \
        || error "Failed to configure sparse checkout for GST plugins"
    SCENESCAPE_DIR_INPUT="$SCENESCAPE_PLUGINS_DIR"
    success "GST plugins cloned to: $SCENESCAPE_DIR_INPUT"
fi
info "Detecting hardware..."
GPU_AVAILABLE=false
if lspci | grep -i "VGA.*Intel" >/dev/null 2>&1; then
    GPU_AVAILABLE=true
    success "Intel GPU detected - will use GPU inference"
    DEFAULT_DEVICE="GPU"
else
    warning "No Intel GPU detected - will use CPU inference"
    DEFAULT_DEVICE="CPU"
fi

# Discover scenes
info "Discovering scenes..."
SCENES=()
if [ -d "scenes" ]; then
    while IFS= read -r -d '' scene_file; do
        scene_name=$(basename "$scene_file" .zip)
        SCENES+=("$scene_name")
        info "  Found scene: $scene_name"
    done < <(find scenes -name "*.zip" -print0)
fi

if [ ${#SCENES[@]} -eq 0 ]; then
    error "No scene files found in scenes/ directory"
fi

success "Found ${#SCENES[@]} scene(s)"

# Validate scenes against datasets
info "Validating scene/dataset consistency..."
for scene in "${SCENES[@]}"; do
    scene_lower=$(echo "$scene" | tr '[:upper:]' '[:lower:]')
    if [ ! -d "datasets/$scene_lower" ]; then
        error "Scene '$scene' has no matching dataset in datasets/$scene_lower/"
    fi
    
    # Run validation script if available
    if [ -x "scripts/validate-scene.sh" ]; then
        info "  Validating $scene..."
        ./scripts/validate-scene.sh "$scene" "$scene_lower" || warning "Validation warnings for $scene"
    fi
done

success "Scene/dataset validation passed"

# Generate pipeline configurations
info "Generating pipeline configurations..."
mkdir -p generated/pipelines

for scene in "${SCENES[@]}"; do
    scene_lower=$(echo "$scene" | tr '[:upper:]' '[:lower:]')
    output_file="generated/pipelines/${scene_lower}.json"
    
    # Discover cameras from dataset
    cameras=()
    for video in datasets/$scene_lower/cam-*.ts; do
        if [ -f "$video" ]; then
            cam_id=$(basename "$video" .ts)
            cameras+=("$cam_id")
        fi
    done
    
    if [ ${#cameras[@]} -eq 0 ]; then
        warning "No cameras found for scene $scene"
        continue
    fi
    
    info "  Generating $scene_lower.json with ${#cameras[@]} camera(s)..."
    python3 scripts/generate_pipeline.py \
        --cameras "${cameras[@]}" \
        --device "$DEFAULT_DEVICE" \
        --output "$output_file"
    
    success "  Generated $output_file"
done

# Create/update .env file
if [ ! -f ".env" ]; then
    info "Creating environment configuration..."
    touch .env
fi

CURRENT_PUBLIC_HOSTNAME="${PUBLIC_HOSTNAME:-}"
if [ -z "$CURRENT_PUBLIC_HOSTNAME" ]; then
    CURRENT_PUBLIC_HOSTNAME=$(read_env_var "PUBLIC_HOSTNAME")
fi
if [ -z "$CURRENT_PUBLIC_HOSTNAME" ]; then
    CURRENT_PUBLIC_HOSTNAME=$(hostname -f 2>/dev/null || hostname -s 2>/dev/null || true)
fi
CURRENT_PUBLIC_HOSTNAME="${CURRENT_PUBLIC_HOSTNAME#https://}"
CURRENT_PUBLIC_HOSTNAME="${CURRENT_PUBLIC_HOSTNAME#http://}"
CURRENT_PUBLIC_HOSTNAME="${CURRENT_PUBLIC_HOSTNAME%%/*}"
if [ -z "$CURRENT_PUBLIC_HOSTNAME" ]; then
    error "Could not determine PUBLIC_HOSTNAME. Export PUBLIC_HOSTNAME before running setup.sh"
fi

CURRENT_DASHBOARD_PORT="${DASHBOARD_PORT:-}"
if [ -z "$CURRENT_DASHBOARD_PORT" ]; then
    CURRENT_DASHBOARD_PORT=$(read_env_var "DASHBOARD_PORT")
fi
if [ -z "$CURRENT_DASHBOARD_PORT" ]; then
    CURRENT_DASHBOARD_PORT="7000"
fi

CURRENT_API_BASE_URL="${API_BASE_URL:-}"
if [ -z "$CURRENT_API_BASE_URL" ]; then
    CURRENT_API_BASE_URL=$(read_env_var "API_BASE_URL")
fi
if [ -z "$CURRENT_API_BASE_URL" ]; then
    CURRENT_API_BASE_URL="https://localhost/api/v1"
fi
CURRENT_API_BASE_URL="${CURRENT_API_BASE_URL%/}"
if ! is_loopback_api_base_url "$CURRENT_API_BASE_URL"; then
    warning "API_BASE_URL '$CURRENT_API_BASE_URL' is not local; setup will use https://localhost/api/v1 for host-side API calls"
    CURRENT_API_BASE_URL="https://localhost/api/v1"
fi

CURRENT_SCENESCAPE_UI_URL="${SCENESCAPE_UI_URL:-}"
if [ -z "$CURRENT_SCENESCAPE_UI_URL" ]; then
    CURRENT_SCENESCAPE_UI_URL=$(read_env_var "SCENESCAPE_UI_URL")
fi
if [ -z "$CURRENT_SCENESCAPE_UI_URL" ]; then
    CURRENT_SCENESCAPE_UI_URL="https://${CURRENT_PUBLIC_HOSTNAME}"
fi
CURRENT_SCENESCAPE_UI_URL="${CURRENT_SCENESCAPE_UI_URL%/}"

CURRENT_DASHBOARD_URL="${DASHBOARD_URL:-}"
if [ -z "$CURRENT_DASHBOARD_URL" ]; then
    CURRENT_DASHBOARD_URL=$(read_env_var "DASHBOARD_URL")
fi
if [ -z "$CURRENT_DASHBOARD_URL" ]; then
    CURRENT_DASHBOARD_URL="http://${CURRENT_PUBLIC_HOSTNAME}:${CURRENT_DASHBOARD_PORT}"
fi
CURRENT_DASHBOARD_URL="${CURRENT_DASHBOARD_URL%/}"

SCENESCAPE_API_BASE_URL="$CURRENT_API_BASE_URL"

# Get passwords from environment or .env, or prompt if not set
# DATABASE_PASSWORD: Check environment first, then .env, then prompt
CURRENT_DATABASE_PASSWORD="${DATABASE_PASSWORD:-}"
if [ -z "$CURRENT_DATABASE_PASSWORD" ]; then
    CURRENT_DATABASE_PASSWORD=$(grep -E '^DATABASE_PASSWORD=' .env | head -n1 | cut -d'=' -f2-)
fi

# SUPASS: Check environment only (intentionally ephemeral, not written to .env)
SUPASS_INPUT="${SUPASS:-}"

echo ""
echo -e "${YELLOW}Password Configuration:${NC}"
echo ""

# Prompt for SUPASS if not set
if [ -z "$SUPASS_INPUT" ]; then
    if [ -t 0 ]; then
        while [ -z "$SUPASS_INPUT" ]; do
            read -sp "Scenescape admin password (SUPASS, not stored): " SUPASS_INPUT
            echo ""
            read -sp "Retype SUPASS: " SUPASS_CONFIRM
            echo ""
            if [ -z "$SUPASS_INPUT" ]; then
                warning "SUPASS cannot be empty"
            elif [ "$SUPASS_INPUT" != "$SUPASS_CONFIRM" ]; then
                warning "SUPASS entries do not match. Please try again."
                SUPASS_INPUT=""
            fi
        done
        success "SUPASS set"
    else
        error "SUPASS is required in non-interactive mode. Export SUPASS before running setup.sh"
    fi
else
    success "SUPASS provided via environment"
fi

# Prompt for DATABASE_PASSWORD if not set
if [ -z "$CURRENT_DATABASE_PASSWORD" ]; then
    if [ -t 0 ]; then
        while [ -z "$CURRENT_DATABASE_PASSWORD" ]; do
            read -sp "Database password (stored in .env): " CURRENT_DATABASE_PASSWORD
            echo ""
            read -sp "Retype database password: " DB_PASSWORD_CONFIRM
            echo ""
            if [ -z "$CURRENT_DATABASE_PASSWORD" ]; then
                warning "Database password cannot be empty"
            elif [ "$CURRENT_DATABASE_PASSWORD" != "$DB_PASSWORD_CONFIRM" ]; then
                warning "Database passwords do not match. Please try again."
                CURRENT_DATABASE_PASSWORD=""
            fi
        done
        success "Database password set"
    else
        error "DATABASE_PASSWORD is required in non-interactive mode. Export DATABASE_PASSWORD before running setup.sh"
    fi
else
    success "DATABASE_PASSWORD provided via environment"
fi

echo ""

# Determine defaults for generated fields
PRIMARY_DATASET=$(echo "${SCENES[0]}" | tr '[:upper:]' '[:lower:]')
MODEL_NAME="${MODEL_NAME:-$(read_env_var "MODEL_NAME")}"
MODEL_NAME="${MODEL_NAME:-smartbuilding-int8}"

# Upsert helper for .env key-value pairs
upsert_env_var() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" .env; then
        sed -i "s|^${key}=.*|${key}=${value}|" .env
    else
        echo "${key}=${value}" >> .env
    fi
}

# Delete helper for legacy keys in .env
delete_env_var() {
    local key="$1"
    sed -i "/^${key}=/d" .env
}

# Keep DB password persisted, keep SUPASS ephemeral
delete_env_var "SUPASS"
delete_env_var "INTERNAL_BROKER_HOST"
delete_env_var "INTERNAL_WEB_HOST"
delete_env_var "INTERNAL_AUTOCALIBRATION_HOST"
upsert_env_var "DATABASE_PASSWORD" "$CURRENT_DATABASE_PASSWORD"
upsert_env_var "SCENESCAPE_IMAGE_TAG" "2026.2.0-rc1"
upsert_env_var "SCENESCAPE_DIR" "$SCENESCAPE_DIR_INPUT"
upsert_env_var "PRIMARY_SCENE" "${SCENES[0]}"
upsert_env_var "PRIMARY_DATASET" "$PRIMARY_DATASET"
upsert_env_var "MODEL_NAME" "$MODEL_NAME"
upsert_env_var "DETECTION_DEVICE" "$DEFAULT_DEVICE"
upsert_env_var "INFERENCE_DEVICE" "$DEFAULT_DEVICE"
upsert_env_var "PUBLIC_HOSTNAME" "$CURRENT_PUBLIC_HOSTNAME"
upsert_env_var "API_BASE_URL" "$CURRENT_API_BASE_URL"
upsert_env_var "SCENESCAPE_UI_URL" "$CURRENT_SCENESCAPE_UI_URL"
upsert_env_var "DASHBOARD_PORT" "$CURRENT_DASHBOARD_PORT"
upsert_env_var "DASHBOARD_URL" "$CURRENT_DASHBOARD_URL"
upsert_env_var "XPU_SMI_JSON_PATH" "/app/generated/telemetry/xpu-smi.json"

if ! grep -q '^COMPOSE_PROJECT_NAME=' .env; then
    echo "COMPOSE_PROJECT_NAME=scenescape" >> .env
fi
if ! grep -q '^TZ=' .env; then
    echo "TZ=UTC" >> .env
fi

success "Environment file ready"

# Ensure Scenescape secrets exist and use the same DB password as .env
if [ ! -f "certs/scenescape-ca.pem" ] || [ ! -f "certs/django/secrets.py" ] || [ ! -f "certs/scenescape-autocalibration.crt" ] || [ ! -f "certs/scenescape-autocalibration.key" ] || [ ! -f "certs/calibration.auth" ]; then
    info "Generating TLS certificates and secrets..."
    chmod +x scripts/generate-certs.sh
    DATABASE_PASSWORD="$CURRENT_DATABASE_PASSWORD" ./scripts/generate-certs.sh
    success "Certificates and secrets generated"
else
    if ! grep -q "^DATABASE_PASSWORD='${CURRENT_DATABASE_PASSWORD}'$" certs/django/secrets.py; then
        info "Synchronizing DATABASE_PASSWORD in certs/django/secrets.py..."
        ESCAPED_DB_PASSWORD=$(printf '%s' "$CURRENT_DATABASE_PASSWORD" | sed 's/[&|]/\\&/g')
        sed -i "s|^DATABASE_PASSWORD=.*|DATABASE_PASSWORD='${ESCAPED_DB_PASSWORD}'|" certs/django/secrets.py
    fi
    success "Certificates already exist"
fi

# Pull all containers from Docker Hub
info "Pulling Docker images..."
docker compose pull --ignore-pull-failures 2>/dev/null || true
success "Docker images ready"

# Verify Scenescape images are available (pulled from Docker Hub)
info "Verifying Scenescape images are available..."
REQUIRED_IMAGE_VERSION="${SCENESCAPE_IMAGE_TAG:-$(read_env_var "SCENESCAPE_IMAGE_TAG")}"
REQUIRED_IMAGE_VERSION="${REQUIRED_IMAGE_VERSION:-2026.2.0-rc1}"
missing_images=()
for img in scenescape-manager scenescape-controller scenescape-autocalibration scenescape-analytics; do
    if ! docker image inspect "intel/${img}:${REQUIRED_IMAGE_VERSION}" >/dev/null 2>&1; then
        missing_images+=("intel/${img}:${REQUIRED_IMAGE_VERSION}")
    fi
done
if [ ${#missing_images[@]} -gt 0 ]; then
    error "Missing Scenescape images: ${missing_images[*]}. Check your internet connection and re-run ./setup.sh to pull from Docker Hub."
fi
success "Scenescape images available"

# Seed media volume so web init glob copy does not fail on first boot
info "Seeding media volume..."
docker volume create scenescape_vol-media >/dev/null
docker run --rm -u 0 -v scenescape_vol-media:/media alpine:3.23.5 sh -c 'touch /media/bootstrap.txt && chown -R 1000:1000 /media && chmod -R ug+rwX /media' >/dev/null
success "Media volume ready"

# Start services
info "Starting Scenescape services..."
echo ""
export SUPASS="$SUPASS_INPUT"
docker compose up -d ntpserv pgserver broker mediaserver showcase-streams showcase-cameras web

# Wait for API readiness
info "Waiting for Scenescape API to become ready..."
if wait_for_api 30; then
    success "Scenescape API is ready"
else
    [ -n "$WAIT_FOR_API_LAST_SUMMARY" ] && warning "$WAIT_FOR_API_LAST_SUMMARY"
    error "Scenescape API did not become ready in time"
fi

# Ensure admin password matches SUPASS provided to setup
if [ -n "$SUPASS_INPUT" ]; then
    info "Applying admin password from setup input..."
    if docker compose exec -T -e SUPASS="$SUPASS_INPUT" -e DBHOST='pgserver' -e DBPORT='5432' web /home/scenescape/Scenescape/manage.py shell -c "import os; from django.contrib.auth import get_user_model; u=get_user_model().objects.get(username='admin'); u.set_password(os.environ['SUPASS']); u.save(); print('admin password synchronized')" >/dev/null 2>&1; then
        success "Admin password synchronized from setup input"
    else
        warning "Could not synchronize admin password automatically"
    fi
fi

# Import scenes once API is ready and auth works
info "Importing scenes..."
chmod +x scripts/import-scenes.sh
PASSWORD="$SUPASS_INPUT" BASE_URL="$SCENESCAPE_API_BASE_URL" SCENES_DIR="./scenes" ./scripts/import-scenes.sh
success "Scene import complete"

# Resolve and persist scene UUID(s) so analytics subscribes to the right topic.
# Scenescape assigns a new UUID each time a scene is imported, so we fetch it
# from the API and write it to .env for the analytics container to consume.
info "Resolving scene UUIDs from API..."
_auth_payload=$(jq -n --arg u "admin" --arg p "$SUPASS_INPUT" '{username: $u, password: $p}')
_api_token=$(api_curl -X POST "$SCENESCAPE_API_BASE_URL/auth" \
    -H "Content-Type: application/json" \
    -d "$_auth_payload" | jq -r '.token // empty')
if [ -n "$_api_token" ]; then
    _scenes_json=$(api_curl -H "Authorization: Token $_api_token" "$SCENESCAPE_API_BASE_URL/scenes")
    for scene in "${SCENES[@]}"; do
        _uuid=$(echo "$_scenes_json" | jq -r --arg name "$scene" '.results[] | select(.name == $name) | .uid')
        if [ -n "$_uuid" ] && [ "$_uuid" != "null" ]; then
            upsert_env_var "SCENE_ID" "$_uuid"
            success "Scene UUID: $scene → $_uuid"

            # Write resolved UUIDs to config/resolved-uuids.json so the
            # analytics container can resolve names at runtime without any
            # hardcoded UUIDs in source code.
            _scene_detail=$(api_curl -H "Authorization: Token $_api_token" "$SCENESCAPE_API_BASE_URL/scene/$_uuid")
            mkdir -p config
            python3 - "$_scene_detail" "$_uuid" <<'PYEOF'
import sys, json, pathlib

data     = json.loads(sys.argv[1])
scene_id = sys.argv[2]

regions   = {r["name"]: r["uid"] for r in data.get("regions",  [])}
tripwires = {t["name"]: t["uid"] for t in data.get("tripwires", [])}

out = {"scene_id": scene_id, "regions": regions, "tripwires": tripwires}
pathlib.Path("config/resolved-uuids.json").write_text(json.dumps(out, indent=2) + "\n")
print(f"  Resolved {len(regions)} region(s) and {len(tripwires)} tripwire(s)")
PYEOF
            success "UUID map written to config/resolved-uuids.json"
        else
            warning "Could not resolve UUID for scene '$scene' — analytics may subscribe to the wrong topic"
        fi
    done
else
    warning "Could not get API token to resolve scene UUIDs — run setup.sh again or set SCENE_ID manually"
fi

# Restore object class library (person, luggage, door)
if [ -f "config/object-classes.json" ]; then
    info "Restoring object class library..."
    chmod +x scripts/restore-assets.sh
    PASSWORD="$SUPASS_INPUT" BASE_URL="$SCENESCAPE_API_BASE_URL" ASSETS_FILE="./config/object-classes.json" ./scripts/restore-assets.sh
    success "Object class library ready"
fi

# Start runtime services after scenes exist
info "Starting scene controller, autocalibration, analytics, and narrator..."
docker compose up -d scene autocalibration analytics scene-narrator

configure_xpu_smi_host_access
start_xpu_smi_bridge
verify_telemetry

for scene in "${SCENES[@]}"; do
    scene_lower=$(echo "$scene" | tr '[:upper:]' '[:lower:]')
    start_sensor_replay "$scene" "$scene_lower"
done

# Check service status
info "Checking service health..."
SERVICES=("ntpserv" "pgserver" "broker" "web" "scene" "autocalibration" "mediaserver" "analytics" "scene-narrator")
ALL_HEALTHY=true

for service in "${SERVICES[@]}"; do
    if docker compose ps --services --filter "status=running" | grep -q "^${service}$"; then
        success "  $service: running"
    else
        warning "  $service: not running"
        ALL_HEALTHY=false
    fi
done

echo ""
if [ "$ALL_HEALTHY" = true ]; then
    success "All core services are running"
else
    warning "Some services may not be healthy - check logs with: docker compose logs"
fi

# Display access information
echo ""
echo ""
echo "Setup complete."
echo ""
echo "  Scenescape Web UI: $CURRENT_SCENESCAPE_UI_URL"
echo "  Analytics dashboard: $CURRENT_DASHBOARD_URL"
echo "  Username: admin"
echo "  Password: (the SUPASS you set)"
echo "  Note: accept the self-signed certificate in your browser"
echo "  Note: SideDoorEntry baseline learning begins after the first completed replay loop"
if command -v xpu-smi >/dev/null 2>&1; then
echo "  Note: host xpu-smi bridge is managed by setup.sh and writes to $XPU_SMI_BRIDGE_JSON_FILE"
else
echo "  Note: install host dependency 'xpu-smi' and re-run ./setup.sh to enable Panther Lake Xe3 GPU telemetry"
fi
echo ""
echo "Useful commands:"
echo "  docker compose up -d          # start all services"
echo "  docker compose down           # stop all services"
echo "  docker compose ps             # check service status"
echo "  docker compose logs -f        # view all logs"
echo "  ./cleanup.sh                  # stop and remove all generated files and volumes"
