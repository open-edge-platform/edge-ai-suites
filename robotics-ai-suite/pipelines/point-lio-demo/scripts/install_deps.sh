#!/usr/bin/env bash
# One-time host setup: system packages, Python tooling for dataset fetch/
# convert, and Livox-SDK2 (point_lio unconditionally depends on
# livox_ros_driver2 even for Velodyne-only use - see README.md "Intel
# contributions" / limitations). Safe to re-run (the third-party build is
# skipped once already installed).
#
# Usage: ./install_deps.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

mkdir -p "${BUILD_CACHE}"

echo "==> Installing apt / ROS packages"
sudo apt-get update -qq
sudo apt-get install -y \
  libpcl-dev libeigen3-dev python3-pip \
  "ros-${ROS_DISTRO}-pcl-conversions" \
  "ros-${ROS_DISTRO}-common-interfaces" \
  "ros-${ROS_DISTRO}-tf2" \
  "ros-${ROS_DISTRO}-tf2-ros" \
  "ros-${ROS_DISTRO}-tf2-geometry-msgs" \
  "ros-${ROS_DISTRO}-rosbag2" \
  "ros-${ROS_DISTRO}-rosbag2-storage-default-plugins"

# gdown: automated Google Drive download for fetch_ulhk.sh (handles the
# large-file "can't scan for viruses" confirmation-token dance that plain
# curl/wget can't). rosbags: pure-Python ROS1<->ROS2 bag conversion for
# convert_ulhk_to_bag.sh, used only if the downloaded file turns out to be a
# ROS1 bag.
pip install --user --break-system-packages gdown rosbags

# Clone, cmake-build and install a plain (non-ROS) C++ dependency, once.
# Any extra args are forwarded to the cmake configure step.
clone_build_install() {
  local name="$1" url="$2" ref="$3"
  shift 3
  local dir="${BUILD_CACHE}/${name}"
  if [[ -f "${dir}/.installed" ]]; then
    echo "==> ${name} already installed, skipping"
    return
  fi
  echo "==> Building ${name} (${ref})"
  rm -rf "${dir}"
  git clone --depth 1 -b "${ref}" "${url}" "${dir}"
  mkdir -p "${dir}/build"
  ( cd "${dir}/build" && cmake .. "$@" && make -j"$(nproc)" && sudo make install )
  touch "${dir}/.installed"
}

# v1.3.1's sdk_core tree (comm/define.h, logger_handler/file_manager.h, ...)
# uses uint8_t/uint16_t/uint64_t in several headers without including
# <cstdint>; GCC >=13's libstdc++ stopped pulling it in transitively via
# <string>/<vector>/<map>/<atomic>, so the stock tag fails to compile there.
# Force-including it for every translation unit avoids patching each affected
# header one at a time.
clone_build_install livox-sdk2 https://github.com/Livox-SDK/Livox-SDK2.git v1.3.1 \
  "-DCMAKE_CXX_FLAGS=-include cstdint"

echo "==> Host dependencies installed."
