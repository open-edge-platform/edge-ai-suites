#!/bin/bash
# setup-ovms.sh
# Starts OVMS with the Qwen3-8B model on GPU.
# The container starts in the background — model download happens while you continue setup.

set -euo pipefail

MODEL="OpenVINO/Qwen3-8B-int4-ov"
PORT=8000
CONTAINER_NAME="teacher-assistant-ovms"
STARTUP_CHECK_SECONDS=60

echo "=== OVMS Setup ==="
echo ""

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed. Please install: https://docs.docker.com/engine/install/ubuntu/"
    exit 1
fi
if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon is not running. Please start: sudo systemctl start docker"
    exit 1
fi
if ! command -v curl &> /dev/null; then
    echo "ERROR: curl is not installed. Please run: sudo apt install -y curl"
    exit 1
fi

# Create models directory
mkdir -p ~/models

# Check if OVMS is already running on the port
if curl -s http://localhost:${PORT}/v3/models | grep -q "Qwen3-8B-int4-ov" 2>/dev/null; then
    echo "OVMS is already running and model is loaded."
    exit 0
fi

# Remove stale container with the same name (if any)
if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
    echo "Removing stale container: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" > /dev/null
fi

# Start OVMS container (runs in background, model downloads in parallel)
echo "Starting OVMS container: ${CONTAINER_NAME}"
docker run -d \
       --name "${CONTAINER_NAME}" \
       --user $(id -u):$(id -g) \
       --device /dev/dri \
       --group-add=$(stat -c "%g" /dev/dri/render* | head -n 1) \
       -p ${PORT}:${PORT} \
       -v ~/models:/models \
       openvino/model_server:2026.2-gpu \
       --source_model ${MODEL} \
       --model_repository_path /models \
       --task text_generation \
       --tool_parser hermes3 \
       --rest_port ${PORT} \
       --target_device GPU \
       --cache_size 4 > /dev/null

# Early detection: fail fast if container exits during startup/download.
echo "Checking OVMS startup status for up to ${STARTUP_CHECK_SECONDS}s..."
for _ in $(seq 1 ${STARTUP_CHECK_SECONDS}); do
    if curl -s http://localhost:${PORT}/v3/models | grep -q "Qwen3-8B-int4-ov" 2>/dev/null; then
        echo "OVMS is ready and model is loaded."
        exit 0
    fi

    if ! docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
        echo ""
        echo "ERROR: OVMS container stopped before model became ready."
        echo "This is often a transient network issue (for example HTTP/2 stream reset during model download)."
        echo ""
        echo "Check logs:"
        echo "  docker logs --tail 200 ${CONTAINER_NAME}"
        echo ""
        echo "Then retry:"
        echo "  ./setup-ovms.sh"
        exit 1
    fi

    sleep 1
done

echo ""
echo "=== OVMS container started ==="
echo "Model ${MODEL} is still downloading/loading in the background."
echo "You can proceed with OpenClaw installation."
echo ""
echo "Check readiness:"
echo "  curl -s http://localhost:${PORT}/v3/models"
echo "Check logs:"
echo "  docker logs -f ${CONTAINER_NAME}"
