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
# v1.32.1 supports Meteor Lake, Arrow Lake, Lunar Lake, Panther Lake, and Wildcat Lake.
: "${NPU_DRIVER_URL:=https://github.com/intel/linux-npu-driver/releases/download/v1.32.1/linux-npu-driver-v1.32.1.20260422-24767473183-ubuntu2404.tar.gz}"
: "${LEVEL_ZERO_URL:=https://snapshot.ppa.launchpadcontent.net/kobuk-team/intel-graphics/ubuntu/20260324T100000Z/pool/main/l/level-zero-loader/libze1_1.27.0-1~24.04~ppa2_amd64.deb}"

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

# Install all .deb packages from linux-npu-driver bundle using apt
# (apt handles dependencies better than dpkg)
apt-get update
if ! apt-get install -y --no-install-recommends --allow-downgrades ./intel-*.deb 2>/dev/null; then
    # Fallback to dpkg for non-Ubuntu base images
    dpkg -i ./intel-*.deb || true
    apt-get -f install -y || true
fi

# Install Level Zero loader if URL provided
if [ -n "${LEVEL_ZERO_URL}" ]; then
    curl -L -o level-zero-loader.deb "${LEVEL_ZERO_URL}" && \
    apt-get install -y --no-install-recommends --allow-downgrades ./level-zero-loader.deb 2>/dev/null || \
    dpkg -i ./level-zero-loader.deb || true
fi

# Ensure render group exists in container (for device access)
groupadd -f render 2>/dev/null || true

# Create Level Zero ICD registration so the loader discovers the NPU driver.
# Some linux-npu-driver packages omit this; create it unconditionally.
NPU_ICD_DIR="/usr/lib/x86_64-linux-gnu/ze_intel_npu/vendors"
mkdir -p "${NPU_ICD_DIR}"
echo "/usr/lib/x86_64-linux-gnu/libze_intel_npu.so.1" > "${NPU_ICD_DIR}/libze_intel_npu.icd"

apt-get clean && rm -rf /var/lib/apt/lists/*
rm -rf /tmp/npu_deps
