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
# Adjust folder paths below to match your development environment
#############################################################################

if [[ -z "${CSLAM_DIR}" ]]; then
    CSLAM_DIR=~/workspace/amr/applications.robotics.mobile.robotics-sdk/collaborative-slam
fi

if [[ -z "${DEB_PKG_DIR}" ]]; then
    DEB_PKG_DIR=~/workspace/amr/deb-packages/
fi

build_pkg()
{
    echo "Debian Package: $DEB_PKG @ $(pwd)"

    dpkg-buildpackage

    mv ../$DEB_PKG*.deb "$DEB_PKG_DIR" 2>/dev/null
    rm -f ../$DEB_PKG*
    rm -rf debian/.debhelper
    rm -rf debian/debhelper-build-stamp
    rm -rf debian/files
    rm -rf debian/$DEB_PKG*
    rm -rf debian/tmp
}

DEB_PKG=ros-humble-cslam-tutorial-common
cd "$CSLAM_DIR"/package/tutorial-common || exit
build_pkg

DEB_PKG=ros-humble-cslam-tutorial-2d-lidar
cd "$CSLAM_DIR"/package/tutorial-2d-lidar || exit
build_pkg

DEB_PKG=ros-humble-cslam-tutorial-fastmapping
cd "$CSLAM_DIR"/package/tutorial-fastmapping || exit
build_pkg

DEB_PKG=ros-humble-cslam-tutorial-multi-camera
cd "$CSLAM_DIR"/package/tutorial-multi-camera || exit
build_pkg

DEB_PKG=ros-humble-cslam-tutorial-region-remap
cd "$CSLAM_DIR"/package/tutorial-region-remap || exit
build_pkg

DEB_PKG=ros-humble-cslam-tutorial-two-robot
cd "$CSLAM_DIR"/package/tutorial-two-robot || exit
build_pkg

DEB_PKG=ros-humble-cslam-tutorial-all
cd "$CSLAM_DIR"/package/tutorial-all || exit
build_pkg
