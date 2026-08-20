#!/bin/bash

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


cd /px4 || exit 1

# Remove persisted params so defaults take effect on every boot
rm -f build/px4_sitl_default/rootfs/parameters.bson
rm -f build/px4_sitl_default/rootfs/parameters_backup.bson

# Purge old flight logs to prevent disk fill
rm -rf build/px4_sitl_default/rootfs/log/*
rm -rf build/px4_sitl_default/tmp/rootfs/log/*

echo "=== PX4 SITL + Gazebo Harmonic (Multi-Camera Perimeter Security) ==="

# Reuse the mono_cam_down airframe — multi_cam model.sdf is mounted over
# the mono_cam path at runtime via docker-compose volume mounts.
export PX4_GZ_WORLD=baylands_multicam
export HEADLESS=1

exec make px4_sitl gz_x500_mono_cam_down 2>&1 | grep --line-buffered -v "pxh>"
