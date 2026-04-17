#!/bin/bash
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
set -e
# Configure git for safe directory access
git config --global --add safe.directory '*'
NPROC=$(nproc)
export DEB_BUILD_OPTIONS="nocheck parallel=$NPROC"
export DEBIAN_FRONTEND=noninteractive
export OPENVINO_INSTALL_DIR="/opt/intel/openvino"
export OPENVINO_DOWNLOAD_MODELS="no"
export INTEL_OPENVINO_DIR="/opt/intel/openvino"

echo 'debconf debconf/frontend select Noninteractive' | sudo debconf-set-selections
echo "🚀 Building with $NPROC parallel jobs for ROS ${ROS_DISTRO}"

# Package list in dependency order (yolo_msgs must be built before yolo)
PACKAGES=(
  "segmentation_realsense_tutorial"
  "object_detection_tutorial"
  "yolov8/src/yolo_msgs"
  "yolov8/src/yolo"
)

# Prepare all debian directories first
echo "📂 Preparing debian directories..."
for pkg in "${PACKAGES[@]}"; do
  SRC_DIR="$pkg/${ROS_DISTRO}/debian"
  if [[ ! -d "$SRC_DIR" ]]; then
    echo "❌ ERROR: Missing debian directory: $SRC_DIR"
    exit 1
  fi
  rm -rf "$pkg/debian"
  cp -r "$SRC_DIR" "$pkg/debian"
  echo "  ✓ $pkg"
done

sudo apt-get update -qq
sudo dpkg --configure -a

WORK_DIR=$(pwd)
for pkg in "${PACKAGES[@]}"; do
  if [[ "$pkg" == yolov8/src/yolo* ]]; then
    echo "    Installing $pkg packages..."
    find .. -name "*.deb" -not -name "*-build-deps_*" -not -name "*-dbgsym_*" \
      -exec sudo apt-get install -f -y {} \; 2>/dev/null || true
  fi
  cd "$WORK_DIR/$pkg"
  if [[ -f debian/control ]]; then
    echo "  → $pkg"
    mk-build-deps --remove -i --host-arch amd64 --build-arch amd64 \
      -t "apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades" \
      "debian/control" || {
      echo "❌ ERROR: Failed to install dependencies for $pkg"
      exit 1
    }
  fi
  if ! dpkg-buildpackage; then
    echo "❌ ERROR: Failed to build $pkg"
    exit 1
  fi
done

echo "✅ All packages built successfully"
