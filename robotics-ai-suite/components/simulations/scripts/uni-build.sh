#!/bin/bash
set -e

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

if [ $# -eq 0 ]; then
    echo "Usage: $0 <ros_distro> [parallel_jobs]"
    echo "Example: $0 humble 4"
    exit 1
fi

ROS_DISTRO_INPUT="$1"
PARALLEL_JOBS="${2:-auto}"

# Setup environment
export DEBIAN_FRONTEND=noninteractive
export ROS_DISTRO="${ROS_DISTRO_INPUT}"

if [ "${PARALLEL_JOBS}" = "auto" ]; then
    PARALLEL_JOBS=$(nproc)
fi

export DEB_BUILD_OPTIONS="parallel=${PARALLEL_JOBS} nocheck"
export MAKEFLAGS="-j${PARALLEL_JOBS}"

echo "Building packages for ROS ${ROS_DISTRO_INPUT} with ${PARALLEL_JOBS} parallel jobs"


# Source ROS environment if available
if [ -f "/opt/ros/${ROS_DISTRO_INPUT}/setup.bash" ]; then
    # shellcheck disable=SC1090
    source "/opt/ros/${ROS_DISTRO_INPUT}/setup.bash"
    echo "✅ ROS ${ROS_DISTRO_INPUT} environment sourced"
fi

# Git config
git config --global --add safe.directory '*'

# Clean old build artifacts
echo "Cleaning old .deb files..."
find . -maxdepth 1 -name "*.deb" -delete 2>/dev/null || true
find . -maxdepth 1 -name "*.ddeb" -delete 2>/dev/null || true
find . -maxdepth 1 -name "*.buildinfo" -delete 2>/dev/null || true
find . -maxdepth 1 -name "*.changes" -delete 2>/dev/null || true

find package -name "*.deb" -delete 2>/dev/null || true
find PicknPlace -name "*.deb" -delete 2>/dev/null || true

echo "✅ Old .deb files cleaned"

# === Prepare Debian directories ===
echo "➡️ Preparing Debian directories"
current_dir="$(pwd)"

# Build ALL packages for BOTH distributions
packages="package/turtlesim_tutorial package/realsense2_tutorial PicknPlace/robot_config PicknPlace/gazebo_plugins PicknPlace/picknplace PicknPlace"

for pkg in $packages; do
    SRC_DIR="${current_dir}/${pkg}/${ROS_DISTRO_INPUT}/debian"
    echo "Setting up debian control files for $pkg ($SRC_DIR)"
    if [ ! -d "$SRC_DIR" ]; then
        echo "❌ ERROR: $SRC_DIR does not exist."
        exit 1
    fi
    rm -rf "${current_dir}/${pkg}/debian"
    cp -r "$SRC_DIR" "${current_dir}/${pkg}/debian"
done

# === Setup Gazebo Repository ===
echo "Setting up Gazebo repository for ROS: ${ROS_DISTRO_INPUT}"

# Install required tools
apt-get update
apt-get install -y lsb-release curl gnupg devscripts equivs

# Add Gazebo GPG key
echo "Adding Gazebo repository..."
curl --connect-timeout 30 --max-time 60 --retry 3 \
    --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
    https://packages.osrfoundation.org/gazebo.gpg

# Verify key was downloaded
if [ ! -f /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg ]; then
  echo "❌ Failed to download Gazebo GPG key"
  exit 1
fi
echo "✅ Gazebo GPG key downloaded successfully"

# Add Gazebo repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

# Update package list with new repository
apt-get update

# Install packages based on ROS distro
if [ "${ROS_DISTRO_INPUT}" = "humble" ]; then
  echo "🔧 Installing for ROS Humble (Ubuntu Jammy + Gazebo Fortress)"
  apt-get install -y ignition-fortress gz-sim7-cli libgz-sim7 libgz-sim7-dev ros-humble-ros-gz
elif [ "${ROS_DISTRO_INPUT}" = "jazzy" ]; then
  echo "🔧 Installing for ROS Jazzy (Ubuntu Noble + Gazebo Harmonic)"
  apt-get install -y gz-harmonic gz-sim8-cli libgz-sim8 libgz-sim8-dev ros-jazzy-ros-gz ros-jazzy-gz-sim-vendor
else
  echo "⚠️ Unsupported ROS distribution: ${ROS_DISTRO_INPUT}"
  exit 1
fi

# === Verify Gazebo Installation ===
if ! gz sim --version; then
  echo "❌ ERROR: Gazebo is not installed or not working properly"
  exit 1
fi
echo "✅ Gazebo verification successful"

# === Update dependencies ===
echo "➡️ Updating dependencies for ROS: ${ROS_DISTRO_INPUT}"
apt-get update
apt-get install -f -y
dpkg --configure -a

# Install build dependencies for ALL packages (both distributions)
for path in package/realsense2_tutorial package/turtlesim_tutorial; do
  echo "Installing dependencies for: ${path}"
  mk-build-deps -i --host-arch amd64 --build-arch amd64 -t "apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades" ${path}/debian/control
done

mk-build-deps -i --host-arch amd64 --build-arch amd64 -t "apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades" PicknPlace/robot_config/debian/control
mk-build-deps -i --host-arch amd64 --build-arch amd64 -t "apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades" PicknPlace/gazebo_plugins/debian/control
mk-build-deps -i --host-arch amd64 --build-arch amd64 -t "apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades" PicknPlace/picknplace/debian/control

# === Build All Packages ===
echo "Building packages for ${ROS_DISTRO_INPUT}"

packages=(
  "package/realsense2_tutorial:Tutorial RealSense2"
  "package/turtlesim_tutorial:Tutorial TurtleSim"
  "PicknPlace/robot_config:Robot Config"
  "PicknPlace/gazebo_plugins:Gazebo Plugins"
  "PicknPlace/picknplace:PicknPlace Main"
  "PicknPlace:Meta Package"
)

total_packages=${#packages[@]}
built_packages=0

for pkg_info in "${packages[@]}"; do
  pkg_path="${pkg_info%%:*}"
  pkg_name="${pkg_info##*:}"

  echo "🔨 [$(($built_packages + 1))/${total_packages}] Building ${pkg_name}"
  cd "${pkg_path}"
  if DEB_BUILD_OPTIONS="nocheck" dpkg-buildpackage -us -uc -b -tc -d; then
    built_packages=$((built_packages + 1))
    echo "✅ ${pkg_name} built successfully"
  else
    echo "❌ Failed to build ${pkg_name}"
    cd - > /dev/null
    exit 1
  fi
  cd - > /dev/null
done

# Verify all packages were built
if [ ${built_packages} -ne ${total_packages} ]; then
  echo "❌ ERROR: Expected ${total_packages} packages, but only ${built_packages} were built!"
  exit 1
fi

echo "ALL ${total_packages} PACKAGES BUILT SUCCESSFULLY!"
echo "📦 Generated .deb packages:"
find . -name "*.deb" -newer /tmp -type f | head -20 || echo "No .deb files found"

# === Copy built deb packages ===
echo "➡️ Collecting built packages"
mkdir -p "/tmp/${ROS_DISTRO_INPUT}_debian_packages"

# Copy packages from current directory
cp ./*.deb "/tmp/${ROS_DISTRO_INPUT}_debian_packages/" 2>/dev/null || true

# Copy packages from subdirectories
find package -name "*.deb" -exec cp {} "/tmp/${ROS_DISTRO_INPUT}_debian_packages/" \; 2>/dev/null || true
find PicknPlace -name "*.deb" -exec cp {} "/tmp/${ROS_DISTRO_INPUT}_debian_packages/" \; 2>/dev/null || true

echo "Built packages:"
ls -la "/tmp/${ROS_DISTRO_INPUT}_debian_packages/"

echo "✅ All packages built successfully for ROS ${ROS_DISTRO_INPUT}!"
