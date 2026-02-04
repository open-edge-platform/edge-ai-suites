#!/bin/bash

# Check for NPU parameter
MODEL_PATH=${1-/home/vpp/yolov8n_int8/yolov8n_with_preprocess.xml}
NPU_ON=${2:-false}

#modelpath
if [[ -z "${MODEL_PATH}" ]]; then
    echo "Error: MODEL_PATH (3rd argument) is required."
    exit 1
fi

ABS_MODEL_PATH=$(realpath "$MODEL_PATH")
if [[ ! -f "$ABS_MODEL_PATH" ]]; then
    echo "Error: Model file not found: $MODEL_PATH"
    exit 1
fi
export MODEL_DIR=$(dirname "$ABS_MODEL_PATH")
export MODEL_FILE=$(basename "$ABS_MODEL_PATH")


# Get group IDs
VIDEO_GROUP_ID=$(getent group video | awk -F: '{printf "%s\n", $3}')
RENDER_GROUP_ID=$(getent group render | awk -F: '{printf "%s\n", $3}')

# Prepare extra parameters
EXTRA_PARAMS=""
if [[ -n "$VIDEO_GROUP_ID" ]]; then
  EXTRA_PARAMS+="--group-add $VIDEO_GROUP_ID "
else
  printf "\nWARNING: video group wasn't found! GPU device(s) probably won't work inside the Docker image.\n\n"
fi

if [[ -n "$RENDER_GROUP_ID" ]]; then
  EXTRA_PARAMS+="--group-add $RENDER_GROUP_ID "
fi

# Handle NPU case
if [[ "$NPU_ON" == "true" ]]; then
  echo "Running with NPU support"
  docker-compose run --rm \
    --device /dev/accel \
    --group-add $(stat -c "%g" /dev/accel/accel* | sort -u | head -n 1) \
    --env ZE_ENABLE_ALT_DRIVERS=libze_intel_vpu.so \
    vppsample
else
  docker compose up
fi
