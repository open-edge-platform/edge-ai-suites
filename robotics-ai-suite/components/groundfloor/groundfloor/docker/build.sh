#!/bin/sh

# Copyright (C) 2025 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

# If building from scratch is required add commandline parameter '--no-cache'


BASEDIR=$(dirname "$0")

DOCKER_BUILDKIT=1 docker build \
  --build-arg DOCKER_USER=amsrl \
  --build-arg ROS_DISTRO=humble \
  --build-arg http_proxy=$http_proxy \
  --build-arg https_proxy=$https_proxy \
  "$@" \
  -t pointcloud_segmentation:$(date +"%Y%m%d") \
  -f $BASEDIR/Dockerfile \
  $BASEDIR/..
