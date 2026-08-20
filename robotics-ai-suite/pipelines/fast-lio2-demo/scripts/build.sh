#!/usr/bin/env bash
# Build fast_lio with colcon, building its livox_ros_driver2 dependency into
# the workspace on first run (fast_lio's CMakeLists.txt/package.xml depend
# on it unconditionally, even for the Velodyne-only NCLT flow this pipeline
# validates - see README.md).
#
# Usage: ./build.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

mkdir -p "${WS_DIR}/src"
ln -sfn "${FASTLIO_SRC}" "${WS_DIR}/src/fast_lio"

# ROS 2's setup.bash references internal ament/colcon trace variables that
# are never exported with a default, so it's incompatible with `set -u`;
# disable nounset just around sourcing it.
set +u
source "/opt/ros/${ROS_DISTRO}/setup.bash"
set -u

if [[ ! -d "${WS_DIR}/src/livox_ros_driver2" ]]; then
  echo "==> Fetching livox_ros_driver2"
  git clone --depth 1 -b "${LIVOX_DRIVER_TAG}" https://github.com/Livox-SDK/livox_ros_driver2.git "${WS_DIR}/src/livox_ros_driver2"
  cp "${WS_DIR}/src/livox_ros_driver2/package_ROS2.xml" "${WS_DIR}/src/livox_ros_driver2/package.xml"
fi

cd "${WS_DIR}"
colcon build --cmake-args -DROS_EDITION=ROS2 "-DDISTRO_ROS=${ROS_DISTRO}" --packages-select livox_ros_driver2
set +u
source "${WS_DIR}/install/setup.bash"
set -u

CMAKE_ARGS=()
if [[ "${ENABLE_PROFILING}" == "ON" ]]; then
  CMAKE_ARGS=(--cmake-args -DENABLE_PROFILING=ON)
fi

cd "${WS_DIR}"
colcon build --packages-select fast_lio "${CMAKE_ARGS[@]}"
echo "==> Build complete. Source it with: source ${WS_DIR}/install/setup.bash"
