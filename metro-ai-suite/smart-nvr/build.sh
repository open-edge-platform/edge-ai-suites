#!/usr/bin/env bash
set -euo pipefail

# --- Color helpers (only if stdout is a TTY) ---
if [ -t 1 ]; then
  YELLOW='\033[1;33m'; GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
else
  YELLOW=''; GREEN=''; RED=''; CYAN=''; NC=''
fi

usage() {
  cat <<'EOF'
Build the nvr-event-router multi-mode image.

Environment variables:
  REGISTRY_URL         Optional registry prefix (e.g. registry.local:5000)
  PROJECT_NAME         Optional project namespace/repo (e.g. myteam)
  TAG                  Image tag (default: latest)
  ADD_COPYLEFT_SOURCES=true  Include copyleft source collection layer
  http_proxy / https_proxy / no_proxy  Proxy settings passed as build args

Flags:
  -t <tag>             Override TAG
  --push               Push image after successful build
  --nocache            Disable layer cache
  -h|--help            Show this help
EOF
}

PUSH=false
NOCACHE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -t)
      TAG="$2"; shift 2 ;;
    --push)
      PUSH=true; shift ;;
    --nocache)
      NOCACHE=true; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo -e "${RED}Unknown argument: $1${NC}" >&2
      usage; exit 1 ;;
  esac
done

export REGISTRY_URL=${REGISTRY_URL:-}
export PROJECT_NAME=${PROJECT_NAME:-}
export TAG=${TAG:-latest}

[[ -n "$REGISTRY_URL" ]] && REGISTRY_URL="${REGISTRY_URL%/}/"
[[ -n "$PROJECT_NAME" ]] && PROJECT_NAME="${PROJECT_NAME%/}/"
REGISTRY="${REGISTRY_URL}${PROJECT_NAME}"
export REGISTRY="${REGISTRY:-}"

if ! command -v docker >/dev/null 2>&1; then
  echo -e "${RED}docker not found in PATH. Aborting.${NC}" >&2
  exit 1
fi

DOCKERFILE_PATH="docker/Dockerfile"
if [ ! -f "$DOCKERFILE_PATH" ]; then
  echo -e "${RED}Dockerfile not found at $DOCKERFILE_PATH${NC}" >&2
  exit 1
fi

if [ -z "$REGISTRY" ]; then
  echo -e "${YELLOW}Warning: No registry prefix set. Images will be tagged locally.${NC}"
else
  echo -e "${CYAN}Using registry prefix:${NC} ${REGISTRY}"  
fi

IMAGE_NAME="${REGISTRY}nvr-event-router:${TAG}"
echo -e "${CYAN}Building image:${NC} ${IMAGE_NAME}"

BUILD_ARGS=( )

# Proxy build args (both lower + upper so Dockerfile ARGs can map either way)
for VAR in http_proxy https_proxy no_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY; do
  VAL="${!VAR:-}" || true
  if [ -n "$VAL" ]; then
    BUILD_ARGS+=("--build-arg" "${VAR}=${VAL}")
  fi
done

# Copyleft toggle
if [ "${ADD_COPYLEFT_SOURCES:-}" = "true" ]; then
  BUILD_ARGS+=("--build-arg" "COPYLEFT_SOURCES=true")
fi

# Optional no-cache
if $NOCACHE; then
  BUILD_ARGS+=("--no-cache")
fi

echo -e "${CYAN}Docker build args:${NC} ${BUILD_ARGS[*]:-(none)}"

# Enable BuildKit if not already
export DOCKER_BUILDKIT=${DOCKER_BUILDKIT:-1}

set -x
docker build "${BUILD_ARGS[@]}" -t "${IMAGE_NAME}" -f "$DOCKERFILE_PATH" .
set +x

if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE_NAME}$"; then
  echo -e "${GREEN}Image ${IMAGE_NAME} built successfully.${NC}"
else
  echo -e "${RED}Image ${IMAGE_NAME} build appears to have failed.${NC}" >&2
  exit 1
fi

if $PUSH; then
  if [ -z "$REGISTRY" ]; then
    echo -e "${RED}Cannot push: REGISTRY_URL / PROJECT_NAME not set (image has no remote prefix).${NC}" >&2
    exit 1
  fi
  echo -e "${CYAN}Pushing image:${NC} ${IMAGE_NAME}"
  docker push "${IMAGE_NAME}"
fi

echo -e "${GREEN}Done.${NC}"
