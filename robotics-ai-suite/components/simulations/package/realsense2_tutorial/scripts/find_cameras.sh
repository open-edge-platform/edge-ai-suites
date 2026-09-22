#!/bin/bash
# Copyright (C) 2026 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0
#
# Manual pre-launch helper for realsense2_tutorial: detects whether the
# connected Intel RealSense camera is a USB device or a GMSL-bound D457, and
# prints the camera_type value to pass to realsense2_tutorial.launch.py.
#
# Usage:
#   ./scripts/find_cameras.sh
#   ros2 launch realsense2_tutorial realsense2_tutorial.launch.py camera_type:=<printed value>

# GMSL-bound D457 streams are exposed under reusable /dev/video-rs-* symlinks
# (see rs-enum-ipu.sh); USB RealSense cameras keep their raw /dev/videoN node.
symlinks=($(find /dev/ -maxdepth 1 -name '*video*' -type l 2>/dev/null))

rs_video_devices=($(for dev in $(v4l2-ctl --list-devices 2>/dev/null); do
    v4l2-ctl -d "${dev}" --list-framesizes=YUYV 2>/dev/null | grep -q 'Discrete' && readlink -f "${dev}"
done))

usb_devices=()
gmsl_devices=()
for dev in "${rs_video_devices[@]}"; do
    link=""
    for candidate in "${symlinks[@]}"; do
        if [ "${dev}" == "$(readlink -f "${candidate}")" ]; then
            link="${candidate}"
            break
        fi
    done
    if [[ "${link}" == /dev/video-rs-* ]]; then
        gmsl_devices+=("${link}")
    else
        usb_devices+=("${link:-${dev}}")
    fi
done

echo "Detected USB RealSense devices:  ${usb_devices[*]:-none}"
echo "Detected GMSL RealSense devices: ${gmsl_devices[*]:-none}"

if [ "${#usb_devices[@]}" -gt 0 ]; then
    echo "camera_type:=usb"
elif [ "${#gmsl_devices[@]}" -gt 0 ]; then
    echo "camera_type:=gmsl"
else
    echo "camera_type:=none"
fi
