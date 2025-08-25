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

# Function to stop cslam processes
stop_cslam_processes()
{
    # Provide terminal feedback
    if [ -z "$1" ]; then
        echo ""
        echo "**********************************************************************"
        echo "*** Please wait a few moments for this C-SLAM tutorial to shutdown ***"
        echo "**********************************************************************"
        echo ""
    else
        echo "Cleanup from prior execution"
    fi

    # Give all the processes a chance to end cleanly
    kill -SIGINT "$(cat /tmp/cslam.pid)"
    sleep 3

    # Any processes not yet stopped are immediately terminated
    kill -9 "$(cat /tmp/cslam.pid)" 2>/dev/null
    rm /tmp/cslam.pid 2>/dev/null

    # Exit this script when done
    if [ -z "$1" ]; then
        exit
    fi
}

# Ctrl-C signal handler
ctrl_c () {
    # Release Ctrl-C trap
    trap - SIGINT

    # Call function to stop cslam processes
    stop_cslam_processes
}

# Trap Ctrl-C
trap ctrl_c SIGINT

# If tmp file exists from a prior execution then cleanup first
if [ -e /tmp/cslam.pid ]
then
    stop_cslam_processes 1
fi
