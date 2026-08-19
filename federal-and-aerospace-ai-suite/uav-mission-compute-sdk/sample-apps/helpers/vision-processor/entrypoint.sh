#!/bin/bash

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Conditional entrypoint for vision processor

if [ "$USE_RTSP" = "true" ]; then
    echo "Starting vision processor in RTSP mode..."
    exec python3 -u /app/detector_multicam_rtsp.py
else
    echo "Starting vision processor in MQTT mode..."
    exec python3 -u /app/detector_multicam.py
fi
