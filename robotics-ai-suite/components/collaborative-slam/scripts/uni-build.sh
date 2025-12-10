#!/bin/bash
set -e
# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

if [ $# -eq 0 ]; then
    echo "Usage: $0 <ros_distro>"
    exit 1
fi

ROS_DISTRO_INPUT="$1"
# shellcheck disable=SC1090
source /opt/ros/"${ROS_DISTRO_INPUT}"/setup.bash
git config --global --add safe.directory '*'

export ROS_DISTRO="${ROS_DISTRO_INPUT}"
export DEBIAN_FRONTEND=noninteractive
export ROS_PACKAGE_PATH=/opt/ros/"${ROS_DISTRO_INPUT}"/share
export CMAKE_PREFIX_PATH=/opt/ros/"${ROS_DISTRO_INPUT}"
export LD_LIBRARY_PATH=/opt/ros/"${ROS_DISTRO_INPUT}"/lib
export PATH=/opt/ros/"${ROS_DISTRO_INPUT}"/bin:$PATH

PARALLEL_JOBS="${2:-auto}"

if [ "${PARALLEL_JOBS}" = "auto" ]; then
    PARALLEL_JOBS=$(nproc)
fi

export DEB_BUILD_OPTIONS="parallel=${PARALLEL_JOBS} nocheck"
export MAKEFLAGS="-j${PARALLEL_JOBS}"

if [ "${ROS_DISTRO_INPUT}" = "jazzy" ]; then
    export PYTHONPATH=/opt/ros/"${ROS_DISTRO_INPUT}"/lib/python3.12/site-packages
else
    export PYTHONPATH=/opt/ros/"${ROS_DISTRO_INPUT}"/lib/python3.10/site-packages
fi

echo "Cleaning old .deb files..."
find . -maxdepth 1 -name "*.deb" -delete
find . -maxdepth 1 -name "*.ddeb" -delete
find . -maxdepth 1 -name "*.buildinfo" -delete
find . -maxdepth 1 -name "*.changes" -delete

find slam -name "*.deb" -delete 2>/dev/null || true
find msgs -name "*.deb" -delete 2>/dev/null || true
find tracker -name "*.deb" -delete 2>/dev/null || true
find server -name "*.deb" -delete 2>/dev/null || true
find package -name "*.deb" -delete 2>/dev/null || true

rm -rf /tmp/*_cslam_deb_packages/

echo "✅ Old .deb files cleaned"

echo "ROS ${ROS_DISTRO_INPUT} environment ready!"
echo "ROS_DISTRO: ${ROS_DISTRO}"
echo "Working directory: $(pwd)"

apt-get update --allow-unauthenticated

# === Build packages ===

current_dir="$(pwd)"

# Function to build package with distro-specific debian
build_package() {
  local package_path="$1"
  local package_name
  package_name=$(basename "${package_path}")

  echo "Building ${package_name} for ${ROS_DISTRO_INPUT}"
  cd "${package_path}"

  mk-build-deps -i --host-arch amd64 --build-arch amd64 \
    -t "apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends" \
    "${ROS_DISTRO_INPUT}/debian/control"

  cp -r "${ROS_DISTRO_INPUT}"/debian ./

  dpkg-buildpackage -us -uc

  rm -rf ./debian

  cd "${current_dir}"
}

# Build in dependency order
build_package "slam/openvslam"

# Install openvslam dev packages
find slam -name "ros-${ROS_DISTRO_INPUT}-*univloc-slam-dev_*" -not -name "*-build-deps_*" -not -name "*-dbgsym_*" \
  -exec dpkg -i {} \;

if ! dpkg -l | grep -q "ros-${ROS_DISTRO}-univloc-slam-dev"; then
    echo "ERROR: ros-${ROS_DISTRO}-univloc-slam-dev not installed!"
    echo "This may cause tracker/server builds to fail"
    exit 1
else
    echo "✅ ros-${ROS_DISTRO}-univloc-slam-dev successfully installed"
fi

build_package "msgs"

# Install msgs packages
find . -name "ros-${ROS_DISTRO_INPUT}-*-msgs_*.deb" -not -name "*-build-deps_*" -not -name "*-dbgsym_*" \
  -exec dpkg -i {} \;

if ! dpkg -l | grep -q "ros-${ROS_DISTRO}-univloc-msgs"; then
    echo "ERROR: ros-${ROS_DISTRO}-univloc-msgs not installed!"
    echo "This may cause tracker/server builds to fail"
    exit 1
else
    echo "✅ ros-${ROS_DISTRO}-univloc-msgs successfully installed"
fi

# Build remaining packages
for package_path in tracker server package/metapackage package/tutorial-*; do
  build_package "${package_path}"
done

# === Copy built deb packages ===
mkdir -p /tmp/"${ROS_DISTRO_INPUT}"_cslam_deb_packages
cd slam
cp ./*.deb /tmp/"${ROS_DISTRO_INPUT}"_cslam_deb_packages/ 2>/dev/null || true
cd "${current_dir}"
cp ./*.deb /tmp/"${ROS_DISTRO_INPUT}"_cslam_deb_packages/ 2>/dev/null || true
cd package
cp ./*.deb /tmp/"${ROS_DISTRO_INPUT}"_cslam_deb_packages/ 2>/dev/null || true
cd "${current_dir}"

echo "Built packages:"
ls -la /tmp/"${ROS_DISTRO_INPUT}"_cslam_deb_packages/

# === Verify package count ===
EXPECTED_PACKAGES=25
ACTUAL_PACKAGES=$(find /tmp/"${ROS_DISTRO_INPUT}"_cslam_deb_packages/ -name "*.deb" -not -name "*-build-deps_*" -not -name "*-dbgsym_*" | wc -l)

echo "Expected: ${EXPECTED_PACKAGES}, Actual: ${ACTUAL_PACKAGES}"

if [ "${ACTUAL_PACKAGES}" -ne "${EXPECTED_PACKAGES}" ]; then
    echo "❌ ERROR: Package count mismatch!"
    exit 1
fi

echo "✅ All ${EXPECTED_PACKAGES} packages built successfully!"
