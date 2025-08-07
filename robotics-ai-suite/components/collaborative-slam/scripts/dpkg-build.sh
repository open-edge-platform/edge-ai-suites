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
# Adjust folder paths below to match your development environment
#############################################################################

if [[ -z "${CSLAM_DIR}" ]]; then
    CSLAM_DIR=~/workspace/amr/applications.robotics.mobile.robotics-sdk/collaborative-slam
fi

if [[ -z "${DEB_PKG_DIR}" ]]; then
    DEB_PKG_DIR=~/workspace/amr/deb-packages/
fi

# Decide which cslam package to build based on specified cli param (default to all - 0)
LVL=0
if [ -n "$1" ]; then
    LVL=$1
fi

# Install Debian package dependencies for the .deb file in the specified folder
install_depends()
{
    cd "$CSLAM_DIR"/"$1" || exit  

    # Install dependencies of package in specified folder
    sudo mk-build-deps -i --host-arch amd64 --build-arch amd64 -t "apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades" debian/control
}

# Build the specified cslam Debian package and cleanup intermediate build files
build_cslam()
{
    CSLAM_FLDR=$CSLAM_DIR/$1
    DEB_PKG=$2

    echo ""
    echo "***********************"
    echo "* Build Debian Package: $DEB_PKG @ $CSLAM_FLDR"
    echo "***********************"
    echo ""

    cd "$CSLAM_FLDR" || exit

    # Build this package
    time dpkg-buildpackage

    # Cleanup all the intermediate build folders and files
    mv ../"$DEB_PKG"*.deb "$DEB_PKG_DIR" 2>/dev/null
    rm -f ../"$DEB_PKG"*
    rm -f "$DEB_PKG"*.buildinfo
    rm -f "$DEB_PKG"*.changes
    rm -f "$DEB_PKG"*.deb
    rm -rf debian/.debhelper
    rm -f debian/debhelper-build-stamp
    rm -f debian/files
    find debian/"$DEB_PKG"* -not -name '*.links' -delete
    rm -rf debian/tmp
    # Leave .obj-x86_64-linux-* folder available for incremental build
    # rm -rf .obj-x86_64-linux-*
}

if [ "$LVL" = "0" ]; then
    sudo apt update && apt upgrade -y

    # Uninstall of ORB Extractor and clear any prior GPU selection
    sudo apt-get -y purge liborb-lze
    sudo apt-get -y autoremove
    echo PURGE | sudo debconf-communicate liborb-lze
fi

# ~30s to build cslam msgs
if [ "$LVL" = "0" ] || [ "$LVL" = "1" ]; then
    install_depends "msgs"

    build_cslam "msgs" "ros-humble-univloc-msgs"
fi

# ~18.5m to build cslam openvslam
if [ "$LVL" = "0" ] || [ "$LVL" = "2" ]; then
    install_depends "slam/openvslam"

    # Override dependencies to force local '-msgs'
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-msgs*.deb

    build_cslam "slam/openvslam" "ros-humble-univloc-slam"
fi

# ~9m to build cslam tracker
if [ "$LVL" = "0" ] || [ "$LVL" = "3" ]; then
    install_depends "tracker"

    # Override dependencies to force local '-msgs' & 'slam-dev'
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-msgs*.deb -f "$DEB_PKG_DIR"/ros-humble-univloc-slam-dev*.deb

    build_cslam "tracker" "ros-humble-univloc-tracker"
fi

# ~4.5m to build cslam server
if [ "$LVL" = "0" ] || [ "$LVL" = "4" ]; then
    install_depends "server"

    # Override dependencies to force local '-msgs' & 'slam-dev'
    sudo apt-get install -y -f "$DEB_PKG_DIR"/ros-humble-univloc-msgs*.deb -f "$DEB_PKG_DIR"/ros-humble-univloc-slam-dev*.deb

    build_cslam "server" "ros-humble-univloc-server"
fi
