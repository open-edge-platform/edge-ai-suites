#!/bin/bash

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -e

# Smart-Community on-device Docker setup.
#
# Orchestrates the full four-service stack defined in docker/compose.yaml:
#   1. vllm-ipex-serving          (:41091) — on-device model serving (VLM+LLM)
#   2. multilevel-video-understanding (:8192) — video summary microservice
#   3. videostream-analytics      (host net) — RTSP capture + NPU YOLO prefilter,
#                                              POSTs events to the MCP webhook :3101
#   4. smart-community-mcp-server   (host net) — MCP server (:3100 MCP+UI, :3101 events)
# videostream-analytics is pulled in via `include:` in docker/compose.yaml, so a
# plain `docker compose` here manages all four as one project.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"

# Load deployment env (group ids, model, ports, SMART_COMMUNITY_DATA_DIR, MODEL_DIR,
# WEBHOOK_URL, ...). Sourcing here makes the script self-contained.
if [ -f "${DOCKER_DIR}/set_env.sh" ]; then
  # shellcheck disable=SC1091
  source "${DOCKER_DIR}/set_env.sh"
fi

SERVICE_PORT=${SERVICE_PORT:-8192}
VLLM_SERVICE_PORT=${VLLM_SERVICE_PORT:-41091}

# Default action flags
BUILD_IMAGE=false
UP_CONTAINERS=true
DOWN_CONTAINERS=false
LIGHT_MODE=false
LIGHT_DOWN=false
FETCH_ONLY=false

# Decide whether we manage the bundled on-device serving or the user has pointed
# the stack at an external OpenAI-compatible serving. Driven by VLM/LLM base URL.
VLLM_ENDPOINT="${VLM_BASE_URL:-${LLM_BASE_URL:-http://vllm-ipex-serving:8000/v1}}"
case "$VLLM_ENDPOINT" in
  *vllm-ipex-serving*) USE_LOCAL_VLLM=true ;;   # bundled service on app-network
  *)                   USE_LOCAL_VLLM=false ;;  # external / remote serving
esac

# Host-reachable readiness probe. The in-network name `vllm-ipex-serving` is not
# resolvable from the host, so probe the mapped port; a remote endpoint directly.
if [ "$USE_LOCAL_VLLM" = true ]; then
  VLLM_HEALTH_URL="http://localhost:${VLLM_SERVICE_PORT}/v1/models"
else
  VLLM_HEALTH_URL="${VLLM_ENDPOINT%/}/models"
fi

is_vllm_healthy() {
  curl -s --max-time 5 "$VLLM_HEALTH_URL" 2>/dev/null | grep -q '"id"'
}

# --- serving startup recovery --------------------------------------------------
# compose.yaml gives vllm-ipex-serving `restart: always`, and multilevel/mcp-server
# depend on it with `condition: service_healthy`. If the serving dies mid-weight-load
# — most often the transient Intel Xe device-lost fault — compose abandons the whole
# `up` immediately, while Docker restarts the container in the background and the
# next attempt usually succeeds. The helpers below keep the script in step with that
# background retry instead of exiting with a bare compose error.
VLLM_CONTAINER="${VLLM_CONTAINER:-vllm-ipex-serving}"
# Seconds to keep waiting for the restart policy to bring the serving back. 0 = don't wait.
# A restart redoes the whole weight download + FP8 compile (about 30 min on a cold
# cache), so leave roughly double that before calling it dead.
VLLM_RETRY_TIMEOUT="${VLLM_RETRY_TIMEOUT:-3600}"

vllm_inspect()  { docker inspect -f "$1" "$VLLM_CONTAINER" 2>/dev/null || true; }
vllm_state()    { vllm_inspect '{{.State.Status}}'; }
vllm_health()   { vllm_inspect '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}'; }
vllm_restarts() { vllm_inspect '{{.RestartCount}}'; }
vllm_policy()   { vllm_inspect '{{.HostConfig.RestartPolicy.Name}}'; }

human_duration() {
  if [ "$1" -ge 60 ]; then echo "$(($1 / 60)) min"; else echo "$1 s"; fi
}

vllm_is_up() {
  case "$(vllm_health)" in
    healthy) return 0 ;;
    none)    is_vllm_healthy ;;
    *)       return 1 ;;
  esac
}

# True while Docker will still restart the container on its own.
vllm_retry_pending() {
  case "$(vllm_policy)" in
    always|unless-stopped|on-failure) ;;
    *) return 1 ;;
  esac
  case "$(vllm_state)" in
    running|restarting|created|exited) return 0 ;;
    *) return 1 ;;
  esac
}

vllm_hit_gpu_fault() {
  docker logs --tail 400 "$VLLM_CONTAINER" 2>&1 \
    | grep -qE 'UR_RESULT_ERROR_DEVICE_LOST|DEVICE_LOST|level_zero backend failed|exec queue reset'
}

show_vllm_logs() {
  echo "---- docker logs --tail 40 ${VLLM_CONTAINER} ----"
  docker logs --tail 40 "$VLLM_CONTAINER" 2>&1 | sed 's/^/  /' || true
  echo "------------------------------------------------"
}

vllm_recovery_hints() {
  echo
  echo "How to recover:"
  if vllm_hit_gpu_fault; then
    cat <<EOF
  The serving lost the GPU (level-zero UR_RESULT_ERROR_DEVICE_LOST) while transferring
  weights. Confirm the driver-side reset on the host:
      dmesg -T | grep -iE 'xe .*(exec queue reset|VM worker error)'
  This fault is usually transient and clears on the next attempt. If it keeps repeating:
    * Release the GPU from other users:  sudo fuser -v /dev/dri/renderD128
    * Lower the peak memory of the transfer in docker/set_env.sh, then re-source it:
        export GPU_MEM_UTIL=0.6       # default 0.7
        export MAX_MODEL_LEN=32768    # default 61440
    * Confirm at least 32 GB of swap is active ('free -h');
      see docs/user-guide/how-to-guides/add-swap.md
    * If the GPU stays wedged across restarts, reboot the host to reset the xe driver.
EOF
  else
    cat <<EOF
  Read the serving log above for the first error, then check the usual causes:
    * Weights still downloading or the Hugging Face endpoint is unreachable (HF_ENDPOINT).
    * Not enough RAM + swap for ${LLM_MODEL:-the model} — see docs/user-guide/how-to-guides/add-swap.md
    * GPU not visible in the container: ls -l /dev/dri, and check VIDEO_GROUP_ID / RENDER_GROUP_ID.
EOF
  fi
  cat <<EOF

  Full serving log:          docker logs -f ${VLLM_CONTAINER}
  Re-check readiness:        curl -fsS ${VLLM_HEALTH_URL}
  Resume once it is warm:    bash $0 --light
  Start over:                bash $0
EOF
}

# Poll until the serving reports healthy, or Docker stops retrying, or we run out
# of budget. Reports progress so a long wait does not look like a hang.
wait_for_vllm_healthy() {
  local started=$SECONDS
  local deadline=$((SECONDS + VLLM_RETRY_TIMEOUT))
  local next_report=0

  while [ "$SECONDS" -lt "$deadline" ]; do
    vllm_is_up && return 0
    vllm_retry_pending || return 1
    if [ "$SECONDS" -ge "$next_report" ]; then
      printf '  [%5ds] %s state=%s health=%s restarts=%s\n' \
        "$((SECONDS - started))" "$VLLM_CONTAINER" \
        "$(vllm_state)" "$(vllm_health)" "$(vllm_restarts)"
      next_report=$((SECONDS + 30))
    fi
    sleep 5
  done
  return 1
}

# `docker compose up -d`, but recover from the serving crashing out from under a
# `service_healthy` dependency instead of reporting a bare failure to the user.
compose_up() {
  local arg vllm_in_play=false

  if [ "$USE_LOCAL_VLLM" = true ]; then
    vllm_in_play=true
    for arg in "$@"; do
      [ "$arg" = "--no-deps" ] && vllm_in_play=false
    done
  fi

  if $DOCKER_CMD up -d "$@"; then
    return 0
  fi

  if [ "$vllm_in_play" != true ] || [ -z "$(vllm_state)" ]; then
    echo -e "${RED}Error: 'docker compose up -d' failed.${NC}"
    echo "  Service states: docker compose -f ${DOCKER_DIR}/compose.yaml ps"
    echo "  Service logs:   docker compose -f ${DOCKER_DIR}/compose.yaml logs --tail 50"
    return 1
  fi

  echo
  echo -e "${YELLOW}Compose gave up waiting for '${VLLM_CONTAINER}' (state=$(vllm_state) health=$(vllm_health) restarts=$(vllm_restarts)).${NC}"
  show_vllm_logs

  if [ "$VLLM_RETRY_TIMEOUT" -le 0 ] || ! vllm_retry_pending; then
    echo -e "${RED}'${VLLM_CONTAINER}' is not being restarted — the stack is down.${NC}"
    vllm_recovery_hints
    return 1
  fi

  echo
  echo -e "${YELLOW}This is not necessarily fatal: Docker's restart policy ('$(vllm_policy)') is already${NC}"
  echo -e "${YELLOW}retrying the serving in the background, and this crash usually clears on the retry.${NC}"
  echo "Waiting up to $(human_duration "$VLLM_RETRY_TIMEOUT") for it to come back."
  echo "Ctrl-C is safe — the retry continues without this script; resume with 'bash $0 --light'."
  echo

  trap 'echo; echo "Interrupted. ${VLLM_CONTAINER} keeps restarting in the background."; echo "Re-check: curl -fsS ${VLLM_HEALTH_URL}   Resume: bash $0 --light"; exit 130' INT
  local recovered=true
  wait_for_vllm_healthy || recovered=false
  trap - INT

  if [ "$recovered" != true ]; then
    echo
    echo -e "${RED}'${VLLM_CONTAINER}' did not become healthy within $(human_duration "$VLLM_RETRY_TIMEOUT").${NC}"
    show_vllm_logs
    vllm_recovery_hints
    return 1
  fi

  echo -e "${GREEN}'${VLLM_CONTAINER}' recovered after $(vllm_restarts) restart(s) — starting the remaining services.${NC}"
  if ! $DOCKER_CMD up -d "$@"; then
    echo -e "${RED}Error: the stack still failed to start after the serving recovered.${NC}"
    echo "  Service states: docker compose -f ${DOCKER_DIR}/compose.yaml ps"
    echo "  Service logs:   docker compose -f ${DOCKER_DIR}/compose.yaml logs --tail 50"
    return 1
  fi
}

# The multilevel-video-understanding build context lives in the external
# open-edge-platform edge-ai-libraries repo, which is NOT vendored here. Clone it
# on demand (shallow + partial + sparse: only the one microservice, no LFS blobs)
# into the fixed path .external/edge-ai-libraries, which docker/compose.yaml
# `extends` from — so EVERY compose command (config/build/up/down) needs it present,
# not just build. Fixed constants; to change source/version, edit them here.
EDGE_AI_LIBRARIES_DIR="${SCRIPT_DIR}/.external/edge-ai-libraries"
EDGE_AI_LIBRARIES_REPO="https://github.com/open-edge-platform/edge-ai-libraries.git"
EDGE_AI_LIBRARIES_REF="release-2026.2.0"
MULTILEVEL_SUBPATH="microservices/multilevel-video-understanding"

ensure_edge_ai_libraries() {
  if git -C "${EDGE_AI_LIBRARIES_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
      && [ -f "${EDGE_AI_LIBRARIES_DIR}/${MULTILEVEL_SUBPATH}/docker/Dockerfile" ]; then
    echo "Using existing directory: ${EDGE_AI_LIBRARIES_DIR}"
    echo "To use the latest version, delete: ${EDGE_AI_LIBRARIES_DIR}"
    return 0
  fi
  echo "Fetching edge-ai-libraries (${EDGE_AI_LIBRARIES_REF}) from ${EDGE_AI_LIBRARIES_REPO}"
  echo "  -> ${EDGE_AI_LIBRARIES_DIR} (shallow, sparse: ${MULTILEVEL_SUBPATH} only)"
  rm -rf "${EDGE_AI_LIBRARIES_DIR}"
  mkdir -p "$(dirname "${EDGE_AI_LIBRARIES_DIR}")"
  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --filter=blob:none --sparse \
    --branch "${EDGE_AI_LIBRARIES_REF}" \
    "${EDGE_AI_LIBRARIES_REPO}" "${EDGE_AI_LIBRARIES_DIR}"
  git -C "${EDGE_AI_LIBRARIES_DIR}" sparse-checkout set "${MULTILEVEL_SUBPATH}"
  if [ ! -f "${EDGE_AI_LIBRARIES_DIR}/${MULTILEVEL_SUBPATH}/docker/Dockerfile" ]; then
    echo -e "${RED}Error: ${MULTILEVEL_SUBPATH} not found after clone.${NC}"
    exit 1
  fi
  echo -e "${GREEN}edge-ai-libraries ready.${NC}"
}

show_help() {
  cat <<EOF
Smart-Community Docker Setup

Usage: $0 [option]

Options:
  (no option) | --prod   End-to-end: build-less start of all three services
                         (vllm-ipex-serving + multilevel-video-understanding + videostream-analytics)
  --light                Reuse an already-healthy serving at VLM_BASE_URL/LLM_BASE_URL;
                         start multilevel-video-understanding + videostream-analytics only
  --fetch                Only clone/refresh edge-ai-libraries (multilevel build context), no build/start
  --build                Build the local images (multilevel + videostream-analytics
                         + smart-community-mcp-server), no start
  --build-prod           Build, then start all four services
  --down                 Stop and remove all containers, networks, volumes
  --light-down           Stop multilevel + videostream-analytics + smart-community-mcp-server,
                         but leave vllm-ipex-serving running (avoids its 3-20 min recompile)
  -h, --help             Show this help

Environment:
  VLLM_RETRY_TIMEOUT     Seconds to keep waiting when vllm-ipex-serving crashes during
                         startup and Docker's restart policy is retrying it in the
                         background (default: 3600 — a retry redoes the full ~30 min
                         weight load). Set to 0 to fail immediately.

Examples:
  source docker/set_env.sh   # optional; the script also sources it itself
  $0                         # start everything
  $0 --light                 # skip vllm if it is already warm
  $0 --build-prod            # rebuild then start
  $0 --down                  # tear down
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-prod) BUILD_IMAGE=true;  UP_CONTAINERS=true;  DOWN_CONTAINERS=false; shift ;;
    --build)      BUILD_IMAGE=true;  UP_CONTAINERS=false; DOWN_CONTAINERS=false; shift ;;
    --prod)       BUILD_IMAGE=false; UP_CONTAINERS=true;  DOWN_CONTAINERS=false; shift ;;
    --light)      BUILD_IMAGE=false; UP_CONTAINERS=true;  DOWN_CONTAINERS=false; LIGHT_MODE=true; shift ;;
    --fetch)      BUILD_IMAGE=false; UP_CONTAINERS=false; DOWN_CONTAINERS=false; FETCH_ONLY=true; shift ;;
    --down)       BUILD_IMAGE=false; UP_CONTAINERS=false; DOWN_CONTAINERS=true;  shift ;;
    --light-down) BUILD_IMAGE=false; UP_CONTAINERS=false; DOWN_CONTAINERS=false; LIGHT_DOWN=true; shift ;;
    -h|--help)    show_help; exit 0 ;;
    *) echo -e "${RED}Unknown option: $1${NC}"; show_help; exit 1 ;;
  esac
done

echo "==== Smart-Community Docker Setup ===="

# Normalise registry prefix exactly like the multilevel service does, so the
# resolved image tag matches compose.yaml's `${REGISTRY:-}multilevel-...`.
[[ -n "$REGISTRY_URL" ]] && REGISTRY_URL="${REGISTRY_URL%/}/"
[[ -n "$PROJECT_NAME" ]] && PROJECT_NAME="${PROJECT_NAME%/}/"
export REGISTRY="${REGISTRY_URL}${PROJECT_NAME}"

MULTILEVEL_IMAGE="${REGISTRY:-}multilevel-video-understanding:${TAG:-latest}"
VSA_IMAGE="${REGISTRY:-}videostream-analytics:${TAG:-latest}"
MCP_IMAGE="${REGISTRY:-}smart-community-mcp-server:${TAG:-latest}"
DEFAULT_PREFILTER_MODEL="${HOME}/models/openvino/yolo11s/FP16/yolo11s.xml"
MODEL_DIR="${MODEL_DIR:-${HOME}/models}"
export MODEL_DIR

prepare_videostream_config() {
  local prefilter_bin prefilter_model runtime_config source_config helper_script model_dir

  prefilter_model="${PREFILTER_MODEL:-$DEFAULT_PREFILTER_MODEL}"
  case "$prefilter_model" in
    '~') prefilter_model="$HOME" ;;
    '~/'*) prefilter_model="$HOME/${prefilter_model#~/}" ;;
  esac

  if [[ "$prefilter_model" != *.xml ]]; then
    echo "PREFILTER_MODEL must reference a .xml OpenVINO IR; using ${DEFAULT_PREFILTER_MODEL}."
    prefilter_model="$DEFAULT_PREFILTER_MODEL"
  fi

  prefilter_model="$(realpath -m "$prefilter_model")"
  prefilter_bin="${prefilter_model%.xml}.bin"
  if [[ ! -s "$prefilter_model" || ! -s "$prefilter_bin" ]]; then
    echo "Prefilter model is missing or incomplete: ${prefilter_model}"
    echo "Preparing the YOLO11s OpenVINO IR automatically..."
    helper_script="${SCRIPT_DIR}/scripts/helpers/prepare_yolo11s.sh"
    PREFILTER_MODEL="$prefilter_model" bash "$helper_script"
  fi

  if [[ ! -s "$prefilter_model" || ! -s "$prefilter_bin" ]]; then
    echo -e "${RED}Error: prefilter preparation did not create a complete IR pair: ${prefilter_model}${NC}"
    exit 1
  fi
  prefilter_model="$(realpath -e "$prefilter_model")"

  model_dir="$(realpath -m "$MODEL_DIR")"
  if [[ "$prefilter_model" != "$model_dir/"* ]]; then
    echo -e "${RED}Error: PREFILTER_MODEL must be under MODEL_DIR (${model_dir}) so the container can read it.${NC}"
    exit 1
  fi

  source_config="${SCRIPT_DIR}/videostream-analytics/config/config.yaml"
  runtime_config="${SCRIPT_DIR}/.docker/videostream-analytics.config.yaml"
  mkdir -p "$(dirname "$runtime_config")"
  PREFILTER_MODEL="$prefilter_model" python3 - "$source_config" "$runtime_config" <<'PY'
import os
import sys
import tempfile

import yaml

source_path, output_path = sys.argv[1:]
with open(source_path, encoding="utf-8") as source_file:
    config = yaml.safe_load(source_file) or {}

config.setdefault("defaults", {}).setdefault("prefilter", {})["model_path"] = os.environ["PREFILTER_MODEL"]
output_dir = os.path.dirname(output_path)
with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_dir, delete=False) as output_file:
    yaml.safe_dump(config, output_file, default_flow_style=False, sort_keys=False)
    temporary_path = output_file.name
os.replace(temporary_path, output_path)
PY

  export PREFILTER_MODEL="$prefilter_model"
  export VIDEOSTREAM_CONFIG_FILE="$runtime_config"
  echo "Using prefilter model: ${PREFILTER_MODEL}"
  echo "Using runtime videostream configuration: ${VIDEOSTREAM_CONFIG_FILE}"
}

cd "$DOCKER_DIR" || { echo -e "${RED}Error: cannot cd to $DOCKER_DIR${NC}"; exit 1; }
DOCKER_CMD="docker compose -f compose.yaml"

# compose.yaml `extends` the upstream service defs from .external/edge-ai-libraries,
# so it must exist before ANY compose command below can even parse the file.
ensure_edge_ai_libraries

# --- fetch-only ---------------------------------------------------------------
if [ "$FETCH_ONLY" = true ]; then
  exit 0
fi

# --- build --------------------------------------------------------------------
if [ "$BUILD_IMAGE" = true ]; then
  echo "Building local images (multilevel-video-understanding + videostream-analytics + smart-community-mcp-server)..."
  $DOCKER_CMD build --no-cache multilevel-video-understanding videostream-analytics smart-community-mcp-server
  echo "==== Build complete! ===="
fi

# --- up -----------------------------------------------------------------------
if [ "$UP_CONTAINERS" = true ]; then
  prepare_videostream_config

  # Compose pulls a missing image itself, and only builds from source if that pull
  # fails — so a missing image is not fatal. But the build fallback is a long, silent
  # detour, so name the absent images up front instead of letting it surprise anyone.
  missing=()
  for img in "$MULTILEVEL_IMAGE" "$VSA_IMAGE" "$MCP_IMAGE"; do
    docker image inspect "$img" >/dev/null 2>&1 || missing+=("$img")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    echo -e "${YELLOW}${#missing[@]} image(s) not present locally:${NC}"
    printf '  %s\n' "${missing[@]}"
    echo "Compose will pull them, and build from source if a pull fails (much slower)."
    echo "Tag mismatch? TAG=${TAG:-latest}; export TAG before 'source docker/set_env.sh'."
  fi

  if [ "$LIGHT_MODE" = true ]; then
    # Reuse an already-warm serving; start only the app + analytics.
    if is_vllm_healthy; then
      echo "Model serving already healthy at ${VLLM_HEALTH_URL} — starting multilevel + videostream-analytics + smart-community-mcp-server only."
      compose_up --no-deps multilevel-video-understanding videostream-analytics smart-community-mcp-server || exit 1
    elif [ "$USE_LOCAL_VLLM" = true ]; then
      echo "Local vllm-ipex-serving not healthy yet — starting the full stack instead."
      echo "(first run pulls/compiles the model — this can take about 30 mins)"
      compose_up || exit 1
    else
      echo "Warning: external serving not reachable at ${VLLM_HEALTH_URL}; starting multilevel + videostream-analytics + smart-community-mcp-server anyway (they retry at runtime)."
      compose_up --no-deps multilevel-video-understanding videostream-analytics smart-community-mcp-server || exit 1
    fi
  else
    # End-to-end: bring up serving + app + analytics together.
    echo "Starting all three services..."
    echo "(first run pulls/compiles the model in vllm-ipex-serving — this can take about 30 mins)"
    compose_up || exit 1
  fi

  echo -e "${GREEN}==== Setup complete! ====${NC}"
  echo "  multilevel-video-understanding : http://localhost:${SERVICE_PORT}/v1  (docs: /docs)"
  echo "  videostream-analytics          : host network, POSTs to ${WEBHOOK_URL:-http://localhost:3101/events}"
  echo "  smart-community-mcp-server       : UI http://localhost:3100/  MCP http://localhost:3100/mcp  events http://localhost:3101/events"
  echo "To stop: $0 --light-down   (keep vllm warm)   |   $0 --down   (full teardown)"
  echo "Service states: docker compose -f ${DOCKER_DIR}/compose.yaml ps"
fi

# --- down ---------------------------------------------------------------------
if [ "$DOWN_CONTAINERS" = true ]; then
  echo "Stopping and removing all containers, networks, and named volumes..."
  $DOCKER_CMD down --volumes --remove-orphans
  echo "==== Full stack stopped and removed! ===="
fi

# --- light-down ---------------------------------------------------------------
# Stop the app tier but keep vllm-ipex-serving running so its multi-minute FP8
# recompile is not paid again on the next start. Mirror of --light on the up side.
if [ "$LIGHT_DOWN" = true ]; then
  echo "Stopping smart-community-mcp-server + videostream-analytics + multilevel-video-understanding (leaving vllm-ipex-serving running)..."
  $DOCKER_CMD rm -sf smart-community-mcp-server videostream-analytics multilevel-video-understanding
  echo "==== App tier stopped; vllm-ipex-serving left running. ===="
fi
