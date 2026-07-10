#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${1:-$HOME/ros2_ws}"
ROS_DISTRO="${ROS_DISTRO:-jazzy}"
ISAAC_ROS_BENCHMARK_REF="${ISAAC_ROS_BENCHMARK_REF:-f391b4de9805a1accac3db5a9de0baa861d88fb1}"
ROS2_BENCHMARK_REF="${ROS2_BENCHMARK_REF:-19bd05d689af273136d585215a3bbf578b274e1c}"
R2B_METADATA_SHA256="${R2B_METADATA_SHA256:-f35091aca7f53735ea243545fea143d7884afd866ad4ba13fd1e7bf347b2e56a}"
R2B_STORAGE_SHA256="${R2B_STORAGE_SHA256:-}"

log() {
  echo "[apriltag-intel-setup] $*"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

fetch_repo() {
  local repo_name="$1"
  local repo_url="$2"
  local repo_ref="$3"
  cd "$WS/src"

  if [[ -d "$repo_name" ]]; then
    log "Repository '$repo_name' already exists, keeping current contents"
    return 0
  fi

  if command -v git >/dev/null 2>&1; then
    log "Cloning $repo_name with git"
    git clone "$repo_url" "$repo_name"
    (
      cd "$repo_name"
      git checkout "$repo_ref"
    )
  else
    if [[ "$repo_ref" != "main" ]]; then
      echo "git is required to checkout pinned commit '$repo_ref' for $repo_name" >&2
      exit 1
    fi
    need_cmd wget
    need_cmd unzip
    local zip_name="${repo_name}-main.zip"
    log "git not found, downloading archive for $repo_name"
    wget -O "$zip_name" "${repo_url}/archive/refs/heads/main.zip"
    unzip -o "$zip_name" >/tmp/${repo_name}_unzip.log
    mv "${repo_name}-main" "$repo_name"
  fi
}

verify_sha256() {
  local expected_sha="$1"
  local file_path="$2"

  if [[ -z "$expected_sha" ]]; then
    log "Skipping SHA256 verification for $file_path because no expected checksum was provided"
    return 0
  fi

  echo "$expected_sha  $file_path" | sha256sum -c -
}

log "Installing required system packages"
sudo apt update
sudo apt install -y \
  ros-${ROS_DISTRO}-ros2-benchmark \
  ros-${ROS_DISTRO}-ros2-benchmark-interfaces \
  ros-${ROS_DISTRO}-apriltag \
  ros-${ROS_DISTRO}-apriltag-msgs \
  ros-${ROS_DISTRO}-apriltag-ros \
  ros-${ROS_DISTRO}-image-proc \
  ros-${ROS_DISTRO}-launch-testing \
  ros-${ROS_DISTRO}-launch-testing-ament-cmake \
  wget unzip

log "Preparing workspace at $WS"
mkdir -p "$WS/src"

fetch_repo "isaac_ros_benchmark" "https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_benchmark" "$ISAAC_ROS_BENCHMARK_REF"
fetch_repo "ros2_benchmark" "https://github.com/NVIDIA-ISAAC-ROS/ros2_benchmark" "$ROS2_BENCHMARK_REF"

log "Installing Apriltag benchmark script"
mkdir -p "$WS/src/isaac_ros_benchmark/benchmarks/isaac_ros_apriltag_benchmark/scripts"
cp "$SCRIPT_DIR/isaac_ros_apriltag_intel.py" \
  "$WS/src/isaac_ros_benchmark/benchmarks/isaac_ros_apriltag_benchmark/scripts/"

log "Downloading required r2b storage dataset"
mkdir -p "$WS/src/ros2_benchmark/assets/datasets/r2b_dataset/r2b_storage"
wget -O "$WS/src/ros2_benchmark/assets/datasets/r2b_dataset/r2b_storage/metadata.yaml" \
  "https://api.ngc.nvidia.com/v2/resources/nvidia/isaac/r2bdataset2023/versions/2/files/r2b_storage/metadata.yaml"
verify_sha256 "$R2B_METADATA_SHA256" "$WS/src/ros2_benchmark/assets/datasets/r2b_dataset/r2b_storage/metadata.yaml"
wget -O "$WS/src/ros2_benchmark/assets/datasets/r2b_dataset/r2b_storage/r2b_storage_0.db3" \
  "https://api.ngc.nvidia.com/v2/resources/nvidia/isaac/r2bdataset2023/versions/2/files/r2b_storage/r2b_storage_0.db3"
verify_sha256 "$R2B_STORAGE_SHA256" "$WS/src/ros2_benchmark/assets/datasets/r2b_dataset/r2b_storage/r2b_storage_0.db3"

log "Setup complete. To run benchmark:"
cat <<EOF
cd "$WS"
source /opt/ros/${ROS_DISTRO}/setup.bash
# Required so benchmark scripts resolve assets from the target workspace.
export ISAAC_ROS_WS="$WS"
# Optional integrity check: set expected SHA256 for r2b_storage_0.db3 before setup.
# export R2B_STORAGE_SHA256=<expected_sha256_for_r2b_storage_0.db3>
export R2B_PUBLISHER_UPPER_FPS=80
export R2B_PLAYBACK_BUFFER_SIZE=80
launch_test src/isaac_ros_benchmark/benchmarks/isaac_ros_apriltag_benchmark/scripts/isaac_ros_apriltag_intel.py
EOF
