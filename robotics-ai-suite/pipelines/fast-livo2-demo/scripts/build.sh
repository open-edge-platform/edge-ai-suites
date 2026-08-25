#!/usr/bin/env bash
# Build fast_livo2 with colcon, building its ROS 2 package dependencies
# (livox_ros_driver2, vikit_ros) into the workspace on first run unless an
# existing underlay is configured in env.sh.
#
# Usage: ./build.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

mkdir -p "${WS_DIR}/src"
ln -sfn "${FASTLIVO2_SRC}" "${WS_DIR}/src/fast_livo2"

# ROS 2's setup.bash references internal ament/colcon trace variables that
# are never exported with a default, so it's incompatible with `set -u`;
# disable nounset just around sourcing it.
set +u
source "/opt/ros/${ROS_DISTRO}/setup.bash"
set -u

if [[ -n "${UNDERLAY_SETUP}" ]]; then
  echo "==> Using pre-built underlay: ${UNDERLAY_SETUP}"
  set +u
  source "${UNDERLAY_SETUP}"
  set -u
else
  if [[ ! -d "${WS_DIR}/src/livox_ros_driver2" ]]; then
    echo "==> Fetching livox_ros_driver2"
    git clone --depth 1 -b 1.2.6 https://github.com/Livox-SDK/livox_ros_driver2.git "${WS_DIR}/src/livox_ros_driver2"
    cp "${WS_DIR}/src/livox_ros_driver2/package_ROS2.xml" "${WS_DIR}/src/livox_ros_driver2/package.xml"
  fi

  if [[ ! -d "${WS_DIR}/src/vikit_ros" ]]; then
    echo "==> Fetching vikit_ros"
    # Same wait_for_service fix applied to vikit_common in install_deps.sh -
    # this is the ROS package half of the same rpg_vikit checkout.
    rm -rf "${BUILD_CACHE}/rpg_vikit_ws_src"
    git clone https://github.com/Robotic-Developer-Road/rpg_vikit.git "${BUILD_CACHE}/rpg_vikit_ws_src"
    sed -i 's/wait_for_service(std::chrono::milliseconds(100))/wait_for_service(std::chrono::milliseconds(5000))/g' \
      "${BUILD_CACHE}/rpg_vikit_ws_src/vikit_ros/include/vikit/params_helper.h"
    cp -r "${BUILD_CACHE}/rpg_vikit_ws_src/vikit_ros" "${WS_DIR}/src/vikit_ros"
  fi

  cd "${WS_DIR}"
  colcon build --cmake-args -DROS_EDITION=ROS2 "-DDISTRO_ROS=${ROS_DISTRO}" --packages-select livox_ros_driver2
  colcon build --packages-select vikit_ros
  set +u
  source "${WS_DIR}/install/setup.bash"
  set -u
fi

CMAKE_ARGS=()
if [[ "${ENABLE_PERFRAME_TIMING}" == "ON" ]]; then
  CMAKE_ARGS=(--cmake-args -DENABLE_PERFRAME_TIMING=ON)
fi

cd "${WS_DIR}"
colcon build --packages-select fast_livo2 "${CMAKE_ARGS[@]}"
echo "==> Build complete. Source it with: source ${WS_DIR}/install/setup.bash"
