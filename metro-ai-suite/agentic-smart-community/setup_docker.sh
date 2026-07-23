#!/bin/bash

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -e

# Smart-Community on-device Docker setup.
#
# Orchestrates the full three-service stack defined in docker/compose.yaml:
#   1. vllm-ipex-serving          (:41091) — on-device model serving (VLM+LLM)
#   2. multilevel-video-understanding (:8192) — video summary microservice
#   3. videostream-analytics      (host net) — RTSP capture + NPU YOLO prefilter,
#                                              POSTs events to the MCP webhook :3101
# The third service is pulled in via `include:` in docker/compose.yaml, so a plain
# `docker compose` here manages all three as one project.

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"

# Load deployment env (group ids, model, ports, SMARTBUILDING_DATA_DIR, MODEL_DIR,
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

# The multilevel-video-understanding build context lives in the external
# open-edge-platform edge-ai-libraries repo, which is NOT vendored here. Clone it
# on demand (shallow + partial + sparse: only the one microservice, no LFS blobs)
# into the fixed path .external/edge-ai-libraries, which docker/compose.yaml
# `extends` from — so EVERY compose command (config/build/up/down) needs it present,
# not just build. Fixed constants; to change source/version, edit them here.
EDGE_AI_LIBRARIES_DIR="${SCRIPT_DIR}/.external/edge-ai-libraries"
EDGE_AI_LIBRARIES_REPO="https://github.com/open-edge-platform/edge-ai-libraries.git"
EDGE_AI_LIBRARIES_REF="main"
MULTILEVEL_SUBPATH="microservices/multilevel-video-understanding"

ensure_edge_ai_libraries() {
  if [ -f "${EDGE_AI_LIBRARIES_DIR}/${MULTILEVEL_SUBPATH}/docker/Dockerfile" ]; then
    echo "edge-ai-libraries present: ${EDGE_AI_LIBRARIES_DIR}"
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
  --build                Build the local images (multilevel + videostream-analytics), no start
  --build-prod           Build, then start all three services
  --down                 Stop and remove all containers, networks, volumes
  -h, --help             Show this help

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
VSA_IMAGE="videostream-analytics:latest"

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
  echo "Building local images (multilevel-video-understanding + videostream-analytics)..."
  $DOCKER_CMD build --no-cache multilevel-video-understanding videostream-analytics
  echo "==== Build complete! ===="
fi

# --- up -----------------------------------------------------------------------
if [ "$UP_CONTAINERS" = true ]; then
  # Both locally-built images must exist before we start.
  missing=false
  for img in "$MULTILEVEL_IMAGE" "$VSA_IMAGE"; do
    if ! docker image inspect "$img" >/dev/null 2>&1; then
      echo -e "${RED}Error: image '$img' not found.${NC}"
      missing=true
    fi
  done
  if [ "$missing" = true ]; then
    echo "Build first:  $0 --build   (or one-shot:  $0 --build-prod)"
    exit 1
  fi

  if [ "$LIGHT_MODE" = true ]; then
    # Reuse an already-warm serving; start only the app + analytics.
    if is_vllm_healthy; then
      echo "Model serving already healthy at ${VLLM_HEALTH_URL} — starting multilevel + videostream-analytics only."
      $DOCKER_CMD up -d --no-deps multilevel-video-understanding videostream-analytics
    elif [ "$USE_LOCAL_VLLM" = true ]; then
      echo "Local vllm-ipex-serving not healthy yet — starting the full stack instead."
      echo "(first run pulls/compiles the model — this can take 3-20+ min)"
      $DOCKER_CMD up -d
    else
      echo "Warning: external serving not reachable at ${VLLM_HEALTH_URL}; starting multilevel + videostream-analytics anyway (they retry at runtime)."
      $DOCKER_CMD up -d --no-deps multilevel-video-understanding videostream-analytics
    fi
  else
    # End-to-end: bring up serving + app + analytics together.
    echo "Starting all three services..."
    echo "(first run pulls/compiles the model in vllm-ipex-serving — this can take 3-20+ min)"
    $DOCKER_CMD up -d
  fi

  echo -e "${GREEN}==== Setup complete! ====${NC}"
  echo "  multilevel-video-understanding : http://localhost:${SERVICE_PORT}/v1  (docs: /docs)"
  echo "  videostream-analytics          : host network, POSTs to ${WEBHOOK_URL:-http://localhost:3101/events}"
  echo "To stop: $0 --down"
fi

# --- down ---------------------------------------------------------------------
if [ "$DOWN_CONTAINERS" = true ]; then
  echo "Stopping and removing all containers..."
  $DOCKER_CMD down
  echo "==== Containers stopped and removed! ===="
fi
