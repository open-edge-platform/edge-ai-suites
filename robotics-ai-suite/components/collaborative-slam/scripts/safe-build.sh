#!/bin/bash
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0
#
# Safe build wrapper that prevents memory exhaustion during parallel builds
#
# Usage:
#   ROS_DISTRO=jazzy make safe-package                    # Use ORB from repos
#   LOCAL_ORB_PATH=/path/to/orb-extractor make safe-package  # Use local ORB
#
# Environment variables:
#   LOCAL_ORB_PATH - Optional path to local ORB extractor packages (for SYCL 8)
#   PARALLEL_JOBS  - Optional override for parallel jobs (default: auto-calculated)
#   http_proxy, https_proxy, no_proxy - Proxy configuration

set -e

# Calculate safe parallel job count based on available memory
# Rule of thumb: 2GB per parallel job for SYCL/oneAPI builds
calculate_safe_jobs() {
    local available_memory_gb
    available_memory_gb=$(free -g | awk '/^Mem:/{print $7}')

    local cpu_cores
    cpu_cores=$(nproc)

    local memory_based_jobs
    memory_based_jobs=$((available_memory_gb / 2))
    
    # Use minimum of CPU cores and memory-based limit, but at least 1
    local safe_jobs=$((memory_based_jobs < cpu_cores ? memory_based_jobs : cpu_cores))
    if [ "$safe_jobs" -lt 1 ]; then
        safe_jobs=1
    fi
    
    echo "$safe_jobs"
}

ROS_DISTRO="${1:-jazzy}"
PARALLEL_JOBS="${2:-auto}"

if [ "$PARALLEL_JOBS" = "auto" ]; then
    PARALLEL_JOBS=$(calculate_safe_jobs)
    echo "Auto-detected safe parallel jobs: $PARALLEL_JOBS (based on available memory)"
fi

echo "Building with $PARALLEL_JOBS parallel jobs..."
echo "This will take longer but prevent system crashes."
echo ""

# Prepare proxy environment variables for Docker
PROXY_ARGS=""
if [ -n "${http_proxy:-}" ]; then
    PROXY_ARGS="$PROXY_ARGS -e http_proxy=${http_proxy}"
fi
if [ -n "${https_proxy:-}" ]; then
    PROXY_ARGS="$PROXY_ARGS -e https_proxy=${https_proxy}"
fi
if [ -n "${HTTP_PROXY:-}" ]; then
    PROXY_ARGS="$PROXY_ARGS -e HTTP_PROXY=${HTTP_PROXY}"
fi
if [ -n "${HTTPS_PROXY:-}" ]; then
    PROXY_ARGS="$PROXY_ARGS -e HTTPS_PROXY=${HTTPS_PROXY}"
fi
if [ -n "${no_proxy:-}" ]; then
    PROXY_ARGS="$PROXY_ARGS -e no_proxy=${no_proxy}"
fi
if [ -n "${NO_PROXY:-}" ]; then
    PROXY_ARGS="$PROXY_ARGS -e NO_PROXY=${NO_PROXY}"
fi

echo "Proxy configuration: ${PROXY_ARGS:-none}"

# Optional: Path to local ORB extractor with SYCL 8 support
# Set LOCAL_ORB_PATH environment variable to use local packages instead of repo versions
# Example: export LOCAL_ORB_PATH=/path/to/orb-extractor
LOCAL_ORB_PATH="${LOCAL_ORB_PATH:-}"

# Prepare volume mounts and install commands
VOLUME_MOUNTS="-v $(pwd):/src"
ORB_INSTALL_COMMANDS=""

if [ -n "${LOCAL_ORB_PATH}" ]; then
    if [ ! -d "${LOCAL_ORB_PATH}" ]; then
        echo "ERROR: LOCAL_ORB_PATH is set but directory not found: ${LOCAL_ORB_PATH}"
        exit 1
    fi
    
    echo "Using local ORB extractor from: ${LOCAL_ORB_PATH}"
    echo "This ensures SYCL 8 (libsycl.so.8) linkage"
    
    VOLUME_MOUNTS="${VOLUME_MOUNTS} -v ${LOCAL_ORB_PATH}:/local-orb:ro"
    ORB_INSTALL_COMMANDS="
        echo '=== Installing dependencies for local ORB extractor ===' && \
        apt install -y intel-oneapi-runtime-dpcpp-cpp intel-oneapi-runtime-compilers intel-oneapi-runtime-openmp intel-oneapi-base-toolkit libze1 libze-dev intel-opencl-icd && \
        echo '=== Installing local ORB extractor (SYCL 8 / oneAPI 2025.x) ===' && \
        dpkg -i /local-orb/liborb-lze_*.deb /local-orb/liborb-lze-dev_*.deb || apt install -y -f && \
        dpkg -i /local-orb/liborb-lze_*.deb /local-orb/liborb-lze-dev_*.deb && \
        echo '=== ORB extractor installed, proceeding with build ===' &&"
else
    echo "Using ORB extractor from ECI/AMR repositories"
    echo "Note: Ensure repos provide SYCL 8 compatible version (liborb-lze-dev >= 2.3-2)"
fi

# Run the build through Docker with proper resource limits
# shellcheck disable=SC2086
docker run --rm -t --platform linux/amd64 \
    --memory="14g" \
    --memory-swap="16g" \
    --cpus="$PARALLEL_JOBS" \
    ${VOLUME_MOUNTS} \
    -e DEBIAN_FRONTEND=noninteractive \
    -e MK_BUILD_DEPS_AUTO=yes \
    ${PROXY_ARGS} \
    amd64/ros:"${ROS_DISTRO}"-ros-base \
    bash -c "cd /src/ && \
        curl https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg -o /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null && \
        echo 'deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/noble isar main' | sudo tee /etc/apt/sources.list.d/eci.list > /dev/null && \
        echo 'deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/noble isar main' | sudo tee -a /etc/apt/sources.list.d/eci.list > /dev/null && \
        echo 'deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/noble amr main' | sudo tee /etc/apt/sources.list.d/amr.list > /dev/null && \
        echo 'deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/noble amr main' | sudo tee -a /etc/apt/sources.list.d/amr.list > /dev/null && \
        echo 'deb [trusted=yes] http://wheeljack.ch.intel.com/apt-repos/AMR/noble amr main' | sudo tee -a /etc/apt/sources.list.d/amr.list > /dev/null && \
        echo 'deb-src [trusted=yes] http://wheeljack.ch.intel.com/apt-repos/AMR/noble amr main' | sudo tee -a /etc/apt/sources.list.d/amr.list > /dev/null && \
        curl https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | \
            gpg --yes --dearmor --output /usr/share/keyrings/oneapi-archive-keyring.gpg && \
        echo 'deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main' > /etc/apt/sources.list.d/oneAPI.list && \
        apt update && \
        ${ORB_INSTALL_COMMANDS} \
        apt install -y quilt equivs devscripts && \
        scripts/uni-build.sh ${ROS_DISTRO} ${PARALLEL_JOBS} && \
        cp -r /tmp/${ROS_DISTRO}_cslam_deb_packages/ /src/${ROS_DISTRO}_cslam_deb_packages"

echo ""
echo "Build completed successfully!"
echo "Packages available in: ${ROS_DISTRO}_cslam_deb_packages/"
