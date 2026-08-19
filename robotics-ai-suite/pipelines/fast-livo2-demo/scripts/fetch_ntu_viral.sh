#!/usr/bin/env bash
# Fetch the NTU VIRAL sequence configured in env.sh and convert its ROS1 bag
# to a ROS2 bag fast_livo2 can play back.
#
# The raw-data zip (containing the ROS1 .bag) is downloaded straight from
# NTU's Dataverse REST API, and the ground-truth leica_pose.csv from the
# viral_eval GitHub repo - both are public, stable URLs that need no login.
# This script then handles the ROS1->ROS2 conversion documented in
# FAST-LIVO2/README_ROS2.md.
#
# Usage: ./fetch_ntu_viral.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

SEQ="${NTU_VIRAL_SEQUENCE}"
BAG_ROS1="${DATASET_DIR}/${SEQ}.bag"
BAG_ROS2="${DATASET_DIR}/${SEQ}"
GT_CSV="${DATASET_DIR}/leica_pose_${SEQ}.csv"
GT_URL="https://raw.githubusercontent.com/ntu-aris/viral_eval/master/result_${SEQ}/leica_pose.csv"

mkdir -p "${DATASET_DIR}"

# Print bytes as a human-readable size (e.g. "1.9 GiB"); "unknown size" if
# the server didn't report a Content-Length (e.g. chunked transfer).
human_size() {
  local bytes="${1:-}"
  if [[ -z "${bytes}" || "${bytes}" == "0" ]]; then
    echo "unknown size"
    return
  fi
  awk -v b="${bytes}" 'BEGIN {
    split("B KiB MiB GiB TiB", units)
    u = 1
    while (b >= 1024 && u < 5) { b /= 1024; u++ }
    printf "%.1f %s\n", b, units[u]
  }'
}

# Downloads $1 to $2, printing the size upfront and curl's live progress
# meter while the transfer runs; removes a partial file on failure.
download_with_progress() {
  local url="$1" dest="$2" size_bytes
  size_bytes="$(curl -sIL "${url}" | grep -i '^content-length:' | tail -1 | tr -d '\r' | awk '{print $2}')"
  echo "==> Downloading $(basename "${dest}") ($(human_size "${size_bytes}")) from ${url}"
  curl -fL -o "${dest}" "${url}" || { rm -f "${dest}"; return 1; }
}

if [[ ! -f "${BAG_ROS1}" ]]; then
  DATAFILE_ID="$(ntu_viral_datafile_id "${SEQ}")"
  if [[ -z "${DATAFILE_ID}" ]]; then
    cat >&2 <<EOF
No known NTU Dataverse file id for sequence ${SEQ}.

Download it manually from the official NTU VIRAL dataset page:
  https://ntu-aris.github.io/ntu_viral_dataset/
(Nguyen et al., "NTU VIRAL: A Visual-Inertial-Ranging-Lidar Dataset, From an
Aerial Vehicle Viewpoint", IJRR 2022) and save it as ${BAG_ROS1},
then re-run this script.
EOF
    exit 1
  fi
  command -v unzip >/dev/null || { echo "unzip is required to extract the downloaded dataset (apt install unzip)" >&2; exit 1; }

  ZIP_PATH="${DATASET_DIR}/${SEQ}.zip"
  download_with_progress "https://researchdata.ntu.edu.sg/api/access/datafile/${DATAFILE_ID}" "${ZIP_PATH}"

  echo "==> Extracting ${SEQ}.bag from ${ZIP_PATH}"
  BAG_IN_ZIP="$(unzip -Z1 "${ZIP_PATH}" | grep -E '\.bag$' | head -1)"
  if [[ -z "${BAG_IN_ZIP}" ]]; then
    echo "No .bag file found inside ${ZIP_PATH}" >&2
    exit 1
  fi
  unzip -p "${ZIP_PATH}" "${BAG_IN_ZIP}" > "${BAG_ROS1}"
  rm -f "${ZIP_PATH}"
fi

if [[ ! -f "${GT_CSV}" ]]; then
  download_with_progress "${GT_URL}" "${GT_CSV}"
fi

if [[ -d "${BAG_ROS2}" ]]; then
  echo "==> ${BAG_ROS2} already converted, skipping"
  exit 0
fi

echo "==> Converting ${SEQ}.bag to a ROS 2 bag"
python3 -c "import rosbags" 2>/dev/null || pip install --user --break-system-packages rosbags
# `pip install --user` puts console scripts in ~/.local/bin, which isn't
# guaranteed to be on PATH (e.g. a non-interactive SSH session) - use it
# explicitly rather than relying on rosbags-convert already being on PATH.
PATH="${HOME}/.local/bin:${PATH}" rosbags-convert --src "${BAG_ROS1}" --dst "${BAG_ROS2}"

METADATA="${BAG_ROS2}/metadata.yaml"
echo "==> Patching ${METADATA} for ROS2 message types (no-op for sensors already in ROS2 form)"
# Leave offered_qos_profiles as the empty list rosbags-convert emits - rosbag2's
# yaml-cpp metadata reader on this ROS distro parses it as a native sequence,
# and rewriting it to an empty string ("") makes it a "bad conversion" parse
# error at load time (confirmed via `ros2 bag info` on the converted bag).
sed -i \
  -e 's#type: livox_ros_driver/msg/CustomMsg#type: livox_ros_driver2/msg/CustomMsg#' \
  "${METADATA}"

echo "==> Dataset ready: ${BAG_ROS2} (ground truth: ${GT_CSV})"
