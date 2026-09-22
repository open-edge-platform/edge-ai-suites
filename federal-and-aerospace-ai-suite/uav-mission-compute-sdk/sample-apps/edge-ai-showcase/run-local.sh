#!/bin/bash

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Run Edge AI Showcase locally without Docker (alternative if build fails)

cd "$(dirname "$0")" || exit 1

echo "🚀 Starting Edge AI Showcase Dashboard (local mode)"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi

# Create venv if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
# shellcheck disable=SC1091
source "$(dirname "$0")/venv/bin/activate"

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install flask==3.0.0 flask-sock==0.7.0 paho-mqtt==2.1.0

# Set environment
export MQTT_BROKER_HOST=localhost
export MQTT_BROKER_PORT=1884
export UAV_ID=uav-1

# Run
echo "✅ Starting dashboard at http://localhost:5002"
python app.py
