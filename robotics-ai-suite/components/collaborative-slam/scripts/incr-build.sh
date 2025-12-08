#!/bin/bash

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

cd "$( dirname "$0" )" || exit

#############################################################################
# This script may be used with the development container supplied in:
# applications.robotics.mobile.amr-common/dev/dev-container/
#
# Adjust folder path below to match your development environment
#############################################################################

# Detect ROS distro
if [ -z "$ROS_DISTRO" ]; then
    if [ -f "/opt/ros/jazzy/setup.bash" ]; then
        export ROS_DISTRO="jazzy"
    elif [ -f "/opt/ros/humble/setup.bash" ]; then
        export ROS_DISTRO="humble"
    else
        echo "Error: No supported ROS distro found (humble/jazzy)"
        exit 1
    fi
fi

echo "Performing incremental build for ROS $ROS_DISTRO"

if [[ -z "${CSLAM_DIR}" ]]; then
    CSLAM_DIR=~/workspace/amr/applications.robotics.mobile.robotics-sdk/collaborative-slam
fi

LVL=1

if [ -n "$1" ]; then
    LVL=$1
fi

# Common CMake flags - dynamically set ROS paths
CMAKE_COMMON_FLAGS="-DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=None -DCMAKE_INSTALL_SYSCONFDIR=/etc -DCMAKE_INSTALL_LOCALSTATEDIR=/var -DCMAKE_EXPORT_NO_PACKAGE_REGISTRY=ON -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF -DCMAKE_FIND_PACKAGE_NO_PACKAGE_REGISTRY=ON -DCMAKE_INSTALL_RUNSTATEDIR=/run -GUnix\ Makefiles -DCMAKE_VERBOSE_MAKEFILE=ON -DCMAKE_INSTALL_LIBDIR=lib/x86_64-linux-gnu -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ros/${ROS_DISTRO} -DAMENT_PREFIX_PATH=/opt/ros/${ROS_DISTRO} -DCMAKE_PREFIX_PATH=/opt/ros/${ROS_DISTRO} -DUSE_PREBUILT_DEPS=ON"

# Note: Changes to the CMakeList.txt or Debian build rules may necessitate an update to the cmake flags below

echo "Performing incremental build for univloc msg"
cd "$CSLAM_DIR"/msgs/.obj-x86_64-linux-gnu || exit
cmake ${CMAKE_COMMON_FLAGS} .
make "$(nproc)"
sudo make install

if [ "$LVL" = "1" ]; then
    echo "Performing incremental build for univloc slam sse"
    cd "$CSLAM_DIR"/slam/openvslam/.obj-x86_64-linux-gnu-sse || exit
    cmake ${CMAKE_COMMON_FLAGS} -DBUILD_NATIVE=OFF -DUSE_SSE_ORB=1 -DUSE_SSE_FP_MATH=1 -DBUILD_SHARED_LIBS=ON .
    make "$(nproc)"
    sudo make install

    echo "Performing incremental build for univloc tracker sse"
    cd "$CSLAM_DIR"/tracker/.obj-x86_64-linux-gnu-sse || exit
    cmake ${CMAKE_COMMON_FLAGS} -DUSE_SLAM_SHAREDLIBS_PATH=/opt/ros/${ROS_DISTRO}/lib/sse -DBUILD_NATIVE=OFF -DUSE_SSE_ORB=1 -DUSE_SSE_FP_MATH=1 -DENABLE_OPENVINO_SEGMENTATION=OFF -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=ON .
    make "$(nproc)"
    sudo make install

    echo "Performing incremental build for univloc server sse"
    cd "$CSLAM_DIR"/server/.obj-x86_64-linux-gnu-sse || exit
    cmake ${CMAKE_COMMON_FLAGS} -DUSE_SLAM_SHAREDLIBS_PATH=/opt/ros/${ROS_DISTRO}/lib/sse -DBUILD_NATIVE=OFF -DUSE_SSE_ORB=1 -DUSE_SSE_FP_MATH=1 -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=ON .
    make "$(nproc)"
    sudo make install
fi

if [ "$LVL" = "2" ]; then
    echo "Performing incremental build for univloc slam lze"
    cd "$CSLAM_DIR"/slam/openvslam/.obj-x86_64-linux-gnu-lze || exit
    cmake ${CMAKE_COMMON_FLAGS} -DBUILD_NATIVE=OFF -DUSE_GPU_CM=1 -DBUILD_SHARED_LIBS=ON "-DCMAKE_CXX_FLAGS= -mavx2" "-DCMAKE_C_FLAGS= -mavx2" .
    make "$(nproc)"
    sudo make install

    echo "Performing incremental build for univloc tracker lze"
    cd "$CSLAM_DIR"/tracker/.obj-x86_64-linux-gnu-lze || exit
    cmake ${CMAKE_COMMON_FLAGS} -DUSE_SLAM_SHAREDLIBS_PATH=/opt/ros/${ROS_DISTRO}/lib/lze -DBUILD_NATIVE=OFF -DUSE_GPU_CM=1 -DENABLE_OPENVINO_SEGMENTATION=OFF -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=ON "-DCMAKE_CXX_FLAGS= -mavx2" "-DCMAKE_C_FLAGS= -mavx2" .
    make "$(nproc)"
    sudo make install

    echo "Performing incremental build for univloc server lze"
    cd "$CSLAM_DIR"/server/.obj-x86_64-linux-gnu-lze || exit
    cmake ${CMAKE_COMMON_FLAGS} -DUSE_SLAM_SHAREDLIBS_PATH=/opt/ros/${ROS_DISTRO}/lib/lze -DBUILD_NATIVE=OFF -DUSE_GPU_CM=1 -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=ON "-DCMAKE_CXX_FLAGS= -mavx2" "-DCMAKE_C_FLAGS= -mavx2" .
    make "$(nproc)"
    sudo make install
fi

if [ "$LVL" = "3" ]; then
    echo "Performing incremental build for univloc slam avx2"
    cd "$CSLAM_DIR"/slam/openvslam/.obj-x86_64-linux-gnu-avx2 || exit
    cmake ${CMAKE_COMMON_FLAGS} -DBUILD_NATIVE=OFF "-DCMAKE_CXX_FLAGS= -mavx2" "-DCMAKE_C_FLAGS= -mavx2" -DBUILD_SHARED_LIBS=ON .
    make "$(nproc)"
    sudo make install

    echo "Performing incremental build for univloc tracker avx2"
    cd "$CSLAM_DIR"/tracker/.obj-x86_64-linux-gnu-avx2 || exit
    cmake ${CMAKE_COMMON_FLAGS} -DUSE_SLAM_SHAREDLIBS_PATH=/opt/ros/${ROS_DISTRO}/lib/avx2 -DBUILD_NATIVE=OFF "-DCMAKE_CXX_FLAGS= -mavx2" "-DCMAKE_C_FLAGS= -mavx2" -DENABLE_OPENVINO_SEGMENTATION=OFF -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=ON .
    make "$(nproc)"
    sudo make install

    echo "Performing incremental build for univloc server avx2"
    cd "$CSLAM_DIR"/server/.obj-x86_64-linux-gnu-avx2 || exit
    cmake ${CMAKE_COMMON_FLAGS} -DUSE_SLAM_SHAREDLIBS_PATH=/opt/ros/${ROS_DISTRO}/lib/avx2 -DBUILD_NATIVE=OFF "-DCMAKE_CXX_FLAGS= -mavx2" "-DCMAKE_C_FLAGS= -mavx2" -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=ON .
    make "$(nproc)"
    sudo make install
fi

echo "Incremental build completed for ROS $ROS_DISTRO"
