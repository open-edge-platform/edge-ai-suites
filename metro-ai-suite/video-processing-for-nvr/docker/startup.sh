#!/bin/bash

# Check for NPU parameter
NPU_ON=${1:-false}

#build
bash build_sample.sh

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
  docker-compose up
fi
