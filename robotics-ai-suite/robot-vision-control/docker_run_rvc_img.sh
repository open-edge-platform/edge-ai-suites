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

# Usage: ./docker_run_rvc_img.sh
set -e

# Run the Docker container
docker run -it \
	--volume=/dev:/dev \
	--volume=/tmp/.X11-unix:/tmp/.X11-unix \
	--ipc=host \
    --privileged \
    --env="DISPLAY" \
    --env="WAYLAND_DISPLAY" \
    --env="XDG_RUNTIME_DIR" \
    --env="PULSE_SERVER" \
    rvc-humble-exec:latest \
    /bin/bash

if [[ $? -ne 0 ]]; then
    echo "Docker run failed."
    exit 1
fi 
