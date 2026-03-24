#!/bin/bash
#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# Accept tag parameter (default to main if not provided)
TAG=${1:-main}
# Trim whitespace from TAG
TAG=$(echo "$TAG" | xargs)

cd ../.. 
echo "Cloning repository for submodules.."
git submodule update --init
# Check if the clone was successful
if [ $? -eq 0 ]; then
    echo "Submodules cloned successfully."
else
    echo "Failed to clone submodules."
    exit 1
fi

# Install test dependencies
echo "Installing test dependencies..."
pip3 install -r tests/requirements.txt
if [ $? -eq 0 ]; then
    echo "Test dependencies installed successfully."
else
    echo "Failed to install test dependencies."
    exit 1
fi
f
# checkout to specified tag/branch for edge-ai-suite and edge-ai-libraries
echo "Checking out to $TAG branch/tag for edge-ai-suites and edge-ai-libraries.."
cd edge-ai-suites
git fetch origin "$TAG" && git checkout "$TAG" && git pull origin "$TAG"
if [ $? -eq 0 ]; then
    echo "Checked out to $TAG branch/tag for edge-ai-suites."
else
    echo "Failed to checkout $TAG branch/tag for edge-ai-suites."
    exit 1
fi
cur_dir=$(pwd)
cd ../edge-ai-libraries
git fetch origin "$TAG" && git checkout "$TAG" && git pull origin "$TAG"
if [ $? -eq 0 ]; then
    echo "Checked out to $TAG branch/tag for edge-ai-libraries."
else
    echo "Failed to checkout $TAG branch/tag for edge-ai-libraries."
    exit 1
fi

# Clean up existing Docker images before building new ones
echo "Cleaning up existing Docker images..."
# Check if ia- images exist and display them
echo "Checking for existing ia- images..."
IA_IMAGES=$(docker images | grep "ia-" || true)
if [ -n "$IA_IMAGES" ]; then
    echo "Found the following ia- images:"
    echo "$IA_IMAGES"
    echo ""
    # Remove ia- images
    echo "Removing ia- images..."
    docker images | grep "ia-" | awk '{print $3}' | xargs -r docker rmi -f
    echo "ia- images removed."
else
    echo "No ia- images found."
fi

# Step to run make build
cur_dir=$(pwd)

# Step 1: Build DLStreamer Pipeline Server microservice
echo "Building DLStreamer Pipeline Server..."
cd "$cur_dir/../edge-ai-libraries/microservices/dlstreamer-pipeline-server/docker"
docker compose build
DLSPS_BUILD_RESULT=$?
if [ $DLSPS_BUILD_RESULT -ne 0 ]; then
    echo "Failed to build DLStreamer Pipeline Server"
    exit 1
fi
echo "Successfully built DLStreamer Pipeline Server"

# Step 2: Build Time Series Analytics microservice
echo "Building Time Series Analytics..."
cd "$cur_dir/../edge-ai-libraries/microservices/time-series-analytics/docker"
docker compose build # build time series analytics image
TS_BUILD_RESULT=$?
if [ $TS_BUILD_RESULT -ne 0 ]; then
    echo "Failed to build Time Series Analytics"
    exit 1
fi
echo "Successfully built Time Series Analytics"

# Step 3: Build industrial-edge-insights-time-series sample app (OPC-UA server and MQTT publisher)
echo "Building industrial-edge-insights-time-series sample app..."
cd "$cur_dir/../edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series"
make build # build the OPC-UA server and MQTT publisher sample ingestion services
BUILD_RESULT=$?
if [ $BUILD_RESULT -ne 0 ]; then
    echo "Failed to build industrial-edge-insights-time-series"
    exit 1
fi
echo "Successfully built industrial-edge-insights-time-series"

# Step 4: Build industrial-edge-insights-multimodal sample app (data simulator and fusion analytics)
echo "Building industrial-edge-insights-multimodal sample app..."
cd "$cur_dir/../edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-multimodal"
make build # builds only data simulator and fusion analytics docker images
MULTIMODAL_BUILD_RESULT=$?
if [ $MULTIMODAL_BUILD_RESULT -ne 0 ]; then
    echo "Failed to build industrial-edge-insights-multimodal"
    exit 1
fi
echo "Successfully built industrial-edge-insights-multimodal"

BUILD_RESULT=$?

if [ $BUILD_RESULT -eq 0 ]; then
    echo "Successfully built all Docker images"
else
    echo "Failed to build Docker images"
    exit 1
fi

echo "Installing k3s..."
curl -sfL https://get.k3s.io | INSTALL_K3S_SELINUX_WARN=true INSTALL_K3S_VERSION=${K3S_VERSION} \
sh -s - --disable=traefik --write-kubeconfig-mode=644
if [ $? -eq 0 ]; then
    echo "Successfully installed k3s"
else
    echo "Failed to install k3s"
    exit 1
fi

echo "Loading docker images into k3s..."
docker image ls --filter "reference=intel/ia-*" --format "table {{.CreatedAt}}\t{{.Repository}}\t{{.Tag}}" | sort -r | while read line; do
    repo=$(echo "$line" | awk '{print $2}')
    tag=$(echo "$line" | awk '{print $3}')

    # Skip header line and <none> entries
    if [ "$repo" = "REPOSITORY" ] || [ "$repo" = "<none>" ] || [ "$tag" = "<none>" ]; then
        continue
    fi

    if [ -n "$repo" ] && [ -n "$tag" ]; then
        echo "Saving image: $repo:$tag"
    fi
done
if [ $? -eq 0 ]; then
    echo "Successfully loaded images into k3s"
else
    echo "Failed to load images into k3s"
    exit 1
fi
