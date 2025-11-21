#!/bin/bash

# OCS2 Robotic Assets Patch Installation Script (Parameterized Version)
# Usage: ./install_ocs2_robotic_assets_patches.sh [patch-list-file]

echo "=== OCS2 Robotic Assets Patch Installation ==="

# Step 1: Initialize and update submodules
echo "Step 1: Initializing and updating git submodules..."
git submodule init && git submodule update
if [ $? -ne 0 ]; then
    echo "Error: Failed to initialize/update git submodules"
    exit 1
fi

# Step 2: Apply patches
echo "Step 2: Applying OCS2 Robotic Assets patches..."

# If patch list file is provided, use it
if [ "$#" -eq 1 ]; then
    PATCH_LIST_FILE="$1"
    
    # Check if the patch list file exists
    if [ ! -f "$PATCH_LIST_FILE" ]; then
        echo "Error: File '$PATCH_LIST_FILE' not found!"
        exit 1
    fi
    
    # Apply patches from file
    while IFS= read -r PATCH_FILE; do
        # Skip empty lines and comments
        [[ -z "$PATCH_FILE" || "$PATCH_FILE" =~ ^[[:space:]]*# ]] && continue
        
        PATCH_PATH="patches/$PATCH_FILE"
        
        if [ ! -f "$PATCH_PATH" ]; then
            echo "Warning: Patch file '$PATCH_PATH' not found, skipping..."
            continue
        fi

        echo "Applying patch: $PATCH_PATH"
        patch -d ocs2_robotic_assets -p1 < "$PATCH_PATH"

        if [ $? -ne 0 ]; then
            echo "Error: Failed to apply patch '$PATCH_PATH'"
            exit 1
        fi
    done < "$PATCH_LIST_FILE"
fi

echo "=== All OCS2 Robotic Assets patches applied successfully! ==="