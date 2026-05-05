#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
#
# Start Grafana Dashboard Stack for ROS2 KPI Monitoring
#
# This script starts Prometheus and Grafana using Docker Compose,
# then provides instructions for starting the metrics exporter.
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🚀 Starting ROS2 KPI Grafana Dashboard Stack"
echo "============================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Install with: sudo apt-get install docker.io docker-compose-plugin"
    exit 1
fi

# Check if Docker Compose v2 is installed
if ! docker compose version &> /dev/null; then
    echo "❌ Error: Docker Compose v2 is not installed"
    echo "Install with: sudo apt-get install docker-compose-plugin"
    exit 1
fi

# Check if user is in docker group
if ! groups | grep -q docker; then
    echo "⚠️  Warning: Your user is not in the docker group"
    echo "Run: sudo usermod -aG docker $USER"
    echo "Then logout and login again"
    echo ""
fi

# Create necessary directories
mkdir -p prometheus grafana/provisioning/datasources grafana/provisioning/dashboards grafana/dashboards

# Check if prometheus_client is installed
if ! python3 -c "import prometheus_client" 2>/dev/null; then
    echo "⚠️  Warning: prometheus_client not installed"
    echo "Install with: uv sync"
    echo ""
fi

# Pull images
echo "📦 Pulling Docker images..."
docker compose pull

# Start services
echo ""
echo "🐳 Starting Docker containers..."
docker compose up -d

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to start..."
sleep 5

# Check if services are running
if docker compose ps | grep -q "Up"; then
    echo "✅ Services started successfully!"
else
    echo "❌ Error: Services failed to start"
    docker compose logs
    exit 1
fi

# Detect host IP for remote access instructions
HOST_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1); exit}' || hostname -I | awk '{print $1}')

echo ""
echo "============================================="
echo "📊 Grafana Dashboard Stack is Running!"
echo "============================================="
echo ""
echo "🌐 Access Points (this machine):"
echo "   Grafana:    http://localhost:30000"
echo "   Prometheus: http://localhost:9090"
echo ""
echo "🌐 Access Points (from other machines):"
echo "   Grafana:    http://${HOST_IP}:30000"
echo "   Prometheus: http://${HOST_IP}:9090"
echo ""
echo "🔑 Grafana Login:"
echo "   Username: admin"
echo "   Password: admin"
echo ""
echo "🔥 If Grafana is not reachable from other machines, open the firewall:"
echo "   sudo ufw allow 30000/tcp"
echo "   sudo ufw allow 9090/tcp"
echo ""
echo "📡 Next Steps:"
echo ""
echo "1️⃣  Start ROS2 monitoring:"
echo "   uv run python src/monitor_stack.py --session grafana_demo"
echo ""
echo "2️⃣  Start metrics exporter (in another terminal):"
echo "   uv run python src/prometheus_exporter.py --session-dir monitoring_sessions/grafana_demo"
echo ""
echo "3️⃣  Open Grafana dashboard:"
echo "   Local:  firefox http://localhost:30000"
echo "   Remote: firefox http://${HOST_IP}:30000"
echo ""
echo "📚 Documentation:"
echo "   See docs/GRAFANA_SETUP.md for detailed instructions"
echo ""
echo "🛑 To stop services:"
echo "   docker compose down"
echo ""

# Optional: Open Grafana in browser
if command -v xdg-open &> /dev/null; then
    read -p "Open Grafana in browser? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sleep 2
        xdg-open "http://localhost:30000" 2>/dev/null || firefox "http://localhost:30000" 2>/dev/null || true
    fi
fi
