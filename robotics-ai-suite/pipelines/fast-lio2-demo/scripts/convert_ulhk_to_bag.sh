#!/usr/bin/env bash
# One-time conversion of the UrbanLoco file fetch_ulhk.sh's instructions
# produce into a standard ROS 2 bag, so run_ulhk.sh can replay it with the
# standard `ros2 bag play` instead of a bespoke reader. Safe to re-run:
# skipped if BAG_DIR already exists and looks good (pass FORCE_CONVERT=true
# to redo it anyway).
#
# UrbanLoco's public download is a ROS1 bag; conversion uses the `rosbags`
# library's `rosbags-convert` (installed by install_deps.sh) rather than a
# custom parser, since every message type here (sensor_msgs/PointCloud2,
# sensor_msgs/Imu, nav_msgs/Odometry, novatel_oem7_msgs/*, ublox_msgs/*) is
# either a standard type `rosbags` already knows, or is only read back by
# raw CDR byte offset (extract_ulhk_gt.py), so an exact typestore match for
# the custom message packages is not required downstream.
#
# Usage: ./convert_ulhk_to_bag.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

# ROS 2's setup.bash references internal ament/colcon trace variables that
# are never exported with a default, so it's incompatible with `set -u`;
# disable nounset just around sourcing it.
set +u
source "/opt/ros/${ROS_DISTRO}/setup.bash"
set -u

check_bag_topics() {
  ros2 bag info "${BAG_DIR}" | tee /dev/stderr | grep -q "${ULHK_LIDAR_TOPIC}" || {
    echo "WARNING: expected LiDAR topic ${ULHK_LIDAR_TOPIC} not found in ${BAG_DIR}." >&2
    echo "WARNING: check 'ros2 bag info ${BAG_DIR}' output above and update" >&2
    echo "WARNING: scripts/env.sh's ULHK_LIDAR_TOPIC/ULHK_IMU_TOPIC/ULHK_GT_TOPIC to match." >&2
  }
}

if [[ -d "${BAG_DIR}" && "${FORCE_CONVERT:-false}" != "true" ]]; then
  echo "==> ${BAG_DIR} already exists, checking it's a good bag before reusing (set FORCE_CONVERT=true to redo)"
  check_bag_topics
  exit 0
fi

if [[ ! -f "${ULHK_RAW_FILE}" ]]; then
  echo "UrbanLoco raw file not found at ${ULHK_RAW_FILE}. Run ./fetch_ulhk.sh" >&2
  echo "for where to download it and where to place it." >&2
  exit 1
fi

if [[ "${FORCE_CONVERT:-false}" == "true" ]]; then
  rm -rf "${BAG_DIR}"
fi

# UrbanLoco's public download is a plain ROS1 bag (single file, not a
# rosbag2 directory) - detect the rare case it's already a ROS2 bag
# (a directory) and skip straight to using it as-is.
if [[ -d "${ULHK_RAW_FILE}" ]]; then
  echo "==> ${ULHK_RAW_FILE} is already a directory (ROS2 bag); linking it as ${BAG_DIR}"
  ln -sfn "${ULHK_RAW_FILE}" "${BAG_DIR}"
else
  echo "==> Converting ROS1 bag ${ULHK_RAW_FILE} -> ROS2 bag ${BAG_DIR}"
  # `pip install --user` puts console scripts in ~/.local/bin, which isn't
  # guaranteed to be on PATH (e.g. a non-interactive SSH session) - check/
  # use it explicitly.
  PATH="${HOME}/.local/bin:${PATH}" command -v rosbags-convert >/dev/null 2>&1 \
    || pip install --user --break-system-packages rosbags
  PATH="${HOME}/.local/bin:${PATH}" rosbags-convert \
    --src "${ULHK_RAW_FILE}" \
    --dst "${BAG_DIR}"
fi

echo "==> Verifying converted bag topics"
check_bag_topics

echo "==> UrbanLoco ${ULHK_SEQUENCE} ready as a ROS2 bag at ${BAG_DIR}"
