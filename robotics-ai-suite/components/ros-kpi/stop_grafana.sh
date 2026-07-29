#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
#
# Stop Grafana Dashboard Stack
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🛑 Stopping ROS2 KPI Grafana Dashboard Stack"
echo "============================================="

# Check if services are running
if docker compose ps | grep -q "Up"; then
    docker compose down
    echo "✅ Services stopped successfully!"
else
    echo "ℹ️  Services are not running"
fi

echo ""
read -p "Remove persistent data (Prometheus metrics, Grafana dashboards)? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker compose down -v
    echo "✅ Volumes removed"
else
    echo "ℹ️  Data preserved (will be available on next start)"
fi

echo ""
echo "To restart: ./start_grafana.sh"
