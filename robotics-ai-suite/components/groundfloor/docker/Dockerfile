# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
FROM ros:humble-ros-base
SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

RUN apt update && \
    apt -y upgrade && \
    apt -y install --no-install-recommends ros-humble-ament-cmake-nose ros-humble-tf2-geometry-msgs ros-humble-depth-image-proc ros-humble-pcl-conversions libpcl-dev && \
    apt -y install --no-install-recommends ros-humble-nav2-bringup && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /ws/src

COPY src/ /ws/src/main
COPY startup/ /ws/startup/
RUN cd /ws/ && source /opt/ros/humble/setup.bash \
    && colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release

COPY docker/entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/entrypoint.sh"]


