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


# This script builds the Docker exec image for the RVC

# Usage: ./docker_build_img.sh [--no-cache]
set -e 
if [[ "$1" == "--no-cache" ]]; then
    NO_CACHE="--no-cache"
else
    NO_CACHE=""
fi

# Build the Docker image
docker build $NO_CACHE -t rvc-humble-exec:latest -f Dockerfile.exec .
if [[ $? -ne 0 ]]; then
    echo "Docker build failed."
    exit 1
fi
