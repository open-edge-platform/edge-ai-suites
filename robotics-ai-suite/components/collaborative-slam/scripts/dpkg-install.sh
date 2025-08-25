#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

cd "$( dirname "$0" )" || exit

#############################################################################
# This script may be used with the development container supplied in:
# applications.robotics.mobile.amr-common/dev/dev-container/
#
# Adjust folder path below to match your development environment
#############################################################################

if [[ -z "${DEB_PKG_DIR}" ]]; then
    DEB_PKG_DIR=~/workspace/amr/deb-packages/
fi

LVL=1

if [ -n "$1" ]; then
    LVL=$1
fi

sudo apt remove -y ros-humble-univloc-msgs ros-humble-univloc-slam-* ros-humble-univloc-tracker-* ros-humble-univloc-server-*

sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-msgs*.deb

if [ "$LVL" = "1" ]; then
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-slam-sse*.deb
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-tracker-sse*.deb
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-server-sse*.deb
    sudo apt-get install -y ros-humble-collab-slam-sse
fi

if [ "$LVL" = "2" ]; then
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-slam-lze*.deb
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-tracker-lze*.deb
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-server-lze*.deb
    sudo apt-get install -y ros-humble-collab-slam-lze
fi

if [ "$LVL" = "3" ]; then
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-slam-avx2*.deb
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-tracker-avx2*.deb
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-server-avx2*.deb
    sudo apt-get install -y ros-humble-collab-slam-avx2
fi

apt search ros-humble-univloc
apt search ros-humble-collab-slam
