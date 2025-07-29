#!/bin/bash

export REGISTRY_URL=${REGISTRY_URL:-}
export PROJECT_NAME=${PROJECT_NAME:-}
export TAG=${TAG:-latest}

[[ -n "$REGISTRY_URL" ]] && REGISTRY_URL="${REGISTRY_URL%/}/"
[[ -n "$PROJECT_NAME" ]] && PROJECT_NAME="${PROJECT_NAME%/}/"
REGISTRY="${REGISTRY_URL}${PROJECT_NAME}"

export REGISTRY="${REGISTRY:-}"

# Display info about the registry being used
if [ -z "$REGISTRY" ]; then
  echo -e "${YELLOW}Warning: No registry prefix set. Images will be tagged without a registry prefix.${NC}"
  echo "Using local image names with tag: ${TAG}"
else
  echo "Using registry prefix: ${REGISTRY}"
fi

# Set the tag value
tag="${REGISTRY}nvr-event-router:${TAG}"

echo "Building $tag image..."

BUILD_ARGS=""
if [ -n "${http_proxy}" ]; then
    BUILD_ARGS="${BUILD_ARGS} --build-arg http_proxy=${http_proxy}"
fi
if [ -n "${https_proxy}" ]; then
    BUILD_ARGS="${BUILD_ARGS} --build-arg https_proxy=${https_proxy}"
fi
if [ -n "${no_proxy}" ]; then
    BUILD_ARGS="${BUILD_ARGS} --build-arg no_proxy=${no_proxy}"
fi

# Add copyleft sources build arg if environment variable is set
if [ "$ADD_COPYLEFT_SOURCES" = "true" ]; then
BUILD_ARGS="$BUILD_ARGS --build-arg COPYLEFT_SOURCES=true"
fi

docker build ${BUILD_ARGS} -t "${tag}" -f docker/Dockerfile .
docker images | grep "$tag" && echo "Image ${tag} built successfully."
