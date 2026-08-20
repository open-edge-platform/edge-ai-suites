#!/usr/bin/env bash
# One-time host setup: system packages, Livox-SDK2, Sophus, and vikit_common.
# Mirrors the exact commands in FAST-LIVO2/README_ROS2.md; safe to re-run
# (each third-party build is skipped once it has already been installed).
#
# Usage: ./install_deps.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

mkdir -p "${BUILD_CACHE}"

echo "==> Installing apt / ROS packages"
sudo apt-get update -qq
sudo apt-get install -y \
  libpcl-dev libeigen3-dev libopencv-dev \
  "ros-${ROS_DISTRO}-pcl-ros" \
  "ros-${ROS_DISTRO}-cv-bridge" \
  "ros-${ROS_DISTRO}-image-transport"

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

# Sophus is header-only; we only need the install step, not its test suite.
# Its bundled tests fail to compile under GCC >=13's stricter
# -Werror=array-bounds against this old Eigen/Sophus SSE-load combo (a known
# false positive, unrelated to correctness) - skip building them entirely.
clone_build_install sophus https://github.com/strasdat/Sophus.git 1.22.10 \
  -DBUILD_SOPHUS_TESTS=OFF -DBUILD_SOPHUS_EXAMPLES=OFF

# vikit_common needs the wait_for_service timeout fix before building; not a
# plain clone_build_install since the fix only applies to this repo.
VIKIT_DIR="${BUILD_CACHE}/rpg_vikit"
if [[ -f "${VIKIT_DIR}/.installed" ]]; then
  echo "==> vikit_common already installed, skipping"
else
  echo "==> Building vikit_common"
  rm -rf "${VIKIT_DIR}"
  git clone https://github.com/Robotic-Developer-Road/rpg_vikit.git "${VIKIT_DIR}"
  sed -i 's/wait_for_service(std::chrono::milliseconds(100))/wait_for_service(std::chrono::milliseconds(5000))/g' \
    "${VIKIT_DIR}/vikit_ros/include/vikit/params_helper.h"
  mkdir -p "${VIKIT_DIR}/vikit_common/build"
  ( cd "${VIKIT_DIR}/vikit_common/build" && cmake .. && make -j"$(nproc)" && sudo make install )
  touch "${VIKIT_DIR}/.installed"
fi

echo "==> Host dependencies installed."
