#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.


# This script starts a Docker container for the RVC project with the necessary configurations.

# Usage: ./docker_run_rvc_img.sh [ROS_DISTRO]
# Example: ./docker_run_rvc_img.sh humble
# Example: ./docker_run_rvc_img.sh jazzy

set -e

# Parse arguments
ROS_DISTRO=${1:-humble}
CONTAINER_NAME="rvc-container-${ROS_DISTRO}"

echo "Checking for existing container: ${CONTAINER_NAME}..."

# Check if the container already exists
if [ "$(docker ps -aq -f name=^${CONTAINER_NAME}$)" ]; then
    echo "Container '${CONTAINER_NAME}' already exists."

    # If it's not running, start it
    if [ "$(docker ps -q -f name=^${CONTAINER_NAME}$)" ]; then
        echo "Container '${CONTAINER_NAME}' is already running. Attaching..."
    else
        echo "Starting container '${CONTAINER_NAME}'..."
        docker start "${CONTAINER_NAME}"
    fi

    # Attach to the container in interactive bash mode
    docker exec -it "${CONTAINER_NAME}" /bin/bash
else
    echo "Creating and running new container '${CONTAINER_NAME}'..."

    docker run -it \
        --name "${CONTAINER_NAME}" \
        --volume=/dev:/dev \
        --volume=/tmp/.X11-unix:/tmp/.X11-unix \
        --ipc=host \
        --network=host \
        --privileged \
        --device /dev/dri \
        --device /dev/accel \
        --group-add=$(stat -c "%g" /dev/dri/render* | head -n 1) -u $(id -u):$(id -g) \
        --env="DISPLAY" \
        --env="WAYLAND_DISPLAY" \
        --env="XDG_RUNTIME_DIR" \
        --env="PULSE_SERVER" \
        --device-cgroup-rule='c 189:* rmw' \
        rvc-exec:${ROS_DISTRO} \
        /bin/bash

    if [[ $? -ne 0 ]]; then
        echo "Docker run failed."
        exit 1
    fi 
fi
