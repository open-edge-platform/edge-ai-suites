#!/bin/bash

# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: APACHE-2.0

# MuJoCo ROS Utils Patch Installation Script (Parameterized Version)
# Usage: ./install_mujoco_ros_utils_patches.sh [patch-list-file]

echo "=== MuJoCo ROS Utils Patch Installation ==="

# Step 1: Initialize and update submodules
echo "Step 1: Initializing and updating git submodules..."
git submodule init && git submodule update
if [ $? -ne 0 ]; then
    echo "Error: Failed to initialize/update git submodules"
    exit 1
fi

# Step 2: Apply patches
echo "Step 2: Applying MuJoCo ROS Utils patches..."

# If patch list file is provided, use it
if [ "$#" -eq 1 ]; then
    PATCH_LIST_FILE="$1"
    
    # Apply patches from file (no existence check as requested)
    while IFS= read -r PATCH_FILE; do
        # Skip empty lines and comments
        [[ -z "$PATCH_FILE" || "$PATCH_FILE" =~ ^[[:space:]]*# ]] && continue
        
        PATCH_PATH="patches/$PATCH_FILE"
        
        if [ ! -f "$PATCH_PATH" ]; then
            echo "Warning: Patch file '$PATCH_PATH' not found, skipping..."
            continue
        fi

        echo "Applying patch: $PATCH_PATH"
        patch -d MujocoRosUtils -p1 < "$PATCH_PATH"

        if [ $? -ne 0 ]; then
            echo "Error: Failed to apply patch '$PATCH_PATH'"
            exit 1
        fi
    done < "$PATCH_LIST_FILE"
fi

echo "=== All MuJoCo ROS Utils patches applied successfully! ==="
