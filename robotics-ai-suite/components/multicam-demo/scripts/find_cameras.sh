#!/bin/bash
# Copyright (C) 2026 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

cd "${SCRIPT_DIR}"

append_camera_realsense()
{
    source="${1}"
 cat << EOF >> "${SCRIPT_DIR}/../config/config_camera.json"
  {
    "name": "yolov8n-seg",
    "model": "models/yolov8/FP16/yolov8n-seg.xml",
    "device": "GPU",
    "data_type": "FP16",
    "source": "${source}",
    "adapter": "yolov8",
    "width": 640,
    "height": 480,
    "format": "YUYV"
  },
EOF
}

append_camera_d3()
{
    source="${1}"
 cat << EOF >> "${SCRIPT_DIR}/../config/config_camera.json"
  {
    "name": "yolov8n-seg",
    "model": "models/yolov8/FP16/yolov8n-seg.xml",
    "device": "GPU",
    "data_type": "FP16",
    "source": "${source}",
    "adapter": "yolov8",
    "width": 1920,
    "height": 1536,
    "format": "UYVY"
  },
EOF
}

# Find camera symlinks
symlinks=($(find /dev/ -maxdepth 1 -name *video* -type l))

# Find RealSense cameras
rs_rgb_video_devices=($(for dev in $(v4l2-ctl --list-devices); do v4l2-ctl -d "${dev}" --list-framesizes=YUYV 2> /dev/null | grep -q 'Discrete' && readlink -f "${dev}"; done))
rs_link_rgb_video_devices=($(for dev in "${rs_rgb_video_devices[@]}"; do found=false; for link in "${symlinks[@]}"; do if [ "${dev}" == "$(readlink -f ${link})" ]; then found=true; echo "${link}"; continue; fi; done; if [ "${found}" == "false" ]; then echo "${dev}"; fi; done))

# Find D3 cameras
d3_link_rgb_video_devices=()
for link in "${symlinks[@]}"; do if [[ "${link}" == "/dev/video-isx031"* ]]; then d3_link_rgb_video_devices+=("${link}"); fi; done

echo "Detected video devices: ${rs_link_rgb_video_devices[*]} ${d3_link_rgb_video_devices[*]}"

echo "Creating camera configuration file for ${rs_link_rgb_video_devices[*]} ${d3_link_rgb_video_devices[*]}:"
echo "${SCRIPT_DIR}/../config/config_camera.json"

echo '[' > "${SCRIPT_DIR}/../config/config_camera.json"
for camera in "${rs_link_rgb_video_devices[@]}"; do
    append_camera_realsense "${camera}"
done
for camera in "${d3_link_rgb_video_devices[@]}"; do
    append_camera_d3 "${camera}"
done
# Remove trailing comma
sed -i "$ s/,$//" "${SCRIPT_DIR}/../config/config_camera.json"
echo ']' >> "${SCRIPT_DIR}/../config/config_camera.json"

