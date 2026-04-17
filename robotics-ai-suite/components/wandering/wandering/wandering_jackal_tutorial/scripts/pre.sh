#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation

# Function to stop processes of the wandering_jackal tutorial
stop_my_processes()
{
    # Provide terminal feedback
    if [ -z "$1" ]; then
        echo ""
        echo "***************************************************************"
        echo "*** Please wait a few moments for this tutorial to shutdown ***"
        echo "***************************************************************"
        echo ""
    else
        echo "Cleanup from prior execution"
    fi

    # Give all the processes a chance to end cleanly
    kill -SIGINT "$(cat /tmp/wandering_jackal.pid)"
    sleep 3

    # Any processes not yet stopped are immediately terminated
    kill -9 "$(cat /tmp/wandering_jackal.pid)" 2>/dev/null
    rm /tmp/wandering_jackal.pid 2>/dev/null

    # Exit this script when done
    if [ -z "$1" ]; then
        exit
    fi
}

# Ctrl-C signal handler
ctrl_c () {
    # Release Ctrl-C trap
    trap - SIGINT

    # Call function to stop processes
    stop_my_processes
}

# Trap Ctrl-C
trap ctrl_c SIGINT

# If tmp file exists from a prior execution then cleanup first
if [ -e  /tmp/wandering_jackal.pid ]
then
    stop_my_processes 1
fi
