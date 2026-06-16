#!/bin/bash
# setup-ovms.sh
# Starts OVMS with the Qwen3-8B model on GPU and waits until the model is loaded.

set -e

MODEL="OpenVINO/Qwen3-8B-int4-ov"
PORT=8000

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

# Start OVMS container
echo "[1/2] Starting OVMS container..."
docker run -d --rm \
       --user $(id -u):$(id -g) \
       --device /dev/dri \
       --group-add=$(stat -c "%g" /dev/dri/render* | head -n 1) \
       -p ${PORT}:${PORT} \
       -v ~/models:/models \
       openvino/model_server:latest-gpu \
       --source_model ${MODEL} \
       --model_repository_path /models \
       --task text_generation \
       --tool_parser hermes3 \
       --rest_port ${PORT} \
       --target_device GPU \
       --cache_size 4

# Wait for model to load
echo "[2/2] Waiting for model to load (first run downloads several GB, may take 5–10 min)..."
until curl -s http://localhost:${PORT}/v3/models | grep -q "Qwen3-8B-int4-ov"; do
    sleep 5
    printf "."
done

echo ""
echo "=== OVMS is ready ==="
echo "Model: ${MODEL}"
echo "Endpoint: http://localhost:${PORT}/v3"

