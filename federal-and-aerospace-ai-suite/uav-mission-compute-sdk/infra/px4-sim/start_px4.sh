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

echo "=== PX4 SITL + Gazebo Harmonic (official make target) ==="

# Use the official make target — handles Gazebo launch, model spawn,
# gz_bridge, lockstep, and spherical_coordinates correctly.
export PX4_GZ_WORLD=baylands_detection
export HEADLESS=1

exec make px4_sitl gz_x500_mono_cam_down 2>&1 | grep --line-buffered -v "pxh>"
