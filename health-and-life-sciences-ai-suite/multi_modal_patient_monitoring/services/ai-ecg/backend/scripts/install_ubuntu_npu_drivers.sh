#!/bin/bash -x
#
# Copyright (c) 2026 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Script should be used only as a part of Dockerfiles.
# It installs Intel NPU user-space components (linux-npu-driver + Level Zero)
# for Ubuntu-based images.

set -o pipefail

# Default URLs for linux-npu-driver and Level Zero (can be overridden
# via environment variables or Docker build args).
: "${NPU_DRIVER_URL:=https://github.com/intel/linux-npu-driver/releases/download/v1.23.0/linux-npu-driver-v1.23.0.20250827-17270089246-ubuntu2204.tar.gz}"
: "${LEVEL_ZERO_URL:=https://github.com/oneapi-src/level-zero/releases/download/v1.22.4/level-zero_1.22.4+u22.04_amd64.deb}"

# LEVEL_ZERO_URL can be overridden or set empty to skip Level Zero
# installation if a compatible runtime is already present.

apt-get update && \
    apt-get install -y --no-install-recommends curl libtbb12 && \
    rm -rf /var/lib/apt/lists/*

mkdir -p /tmp/npu_deps && cd /tmp/npu_deps || exit 1

# Download and unpack linux-npu-driver tarball
curl -L -O "${NPU_DRIVER_URL}"
TARBALL_NAME="$(basename "${NPU_DRIVER_URL}")"
if [ ! -f "${TARBALL_NAME}" ]; then
    echo "Error: failed to download ${NPU_DRIVER_URL}"
    exit 1
fi

tar -xf "${TARBALL_NAME}"

# Install all .deb packages from linux-npu-driver bundle
if ! dpkg -i ./*.deb; then
    # Attempt to fix missing dependencies
    apt-get update && apt-get -f install -y || true
fi

# Optionally install Level Zero runtime if URL provided
if [ -n "${LEVEL_ZERO_URL}" ]; then
    curl -L -O "${LEVEL_ZERO_URL}" && \
    dpkg -i level-zero_*.deb || true
fi

apt-get clean && rm -rf /var/lib/apt/lists/*
rm -rf /tmp/npu_deps
