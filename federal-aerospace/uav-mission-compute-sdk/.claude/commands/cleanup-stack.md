<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# cleanup-stack

Stop and clean up all running Docker containers and volumes for the UAV simulation stack.

## Implementation

```bash
#!/bin/bash
set -e

echo "Cleaning up UAV simulation stack..."

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

# Stop sample apps + helpers first (they hold the shared network open)
if [ -f sample-apps/docker-compose.yml ]; then
    echo "Stopping sample apps + helpers..."
    docker compose -f sample-apps/docker-compose.yml down -v --remove-orphans 2>/dev/null || true
fi

# Stop core infra
if [ -f docker-compose.yml ]; then
    echo "Stopping core infra..."
    docker compose -f docker-compose.yml down -v --remove-orphans
fi

# Clean up any remaining containers
echo "Removing any remaining fedaero containers..."
docker ps -a --filter "name=uav-mission-compute-sdk" --format "{{.Names}}" | xargs -r docker rm -f

# Clean up networks
echo "Removing Docker networks..."
docker network rm uav-mission-compute-sdk_default 2>/dev/null || true

# Prune stopped containers and dangling images
echo "Pruning stopped containers..."
docker container prune -f

echo "Cleanup complete!"
echo ""
echo "To start fresh, run: /start-stack"
```

## Usage

```bash
/cleanup-stack
```

## Notes

- Stops sample-apps layer first, then core infra
- Removes volumes with `-v` flag
- Removes orphaned containers
- Safe to run even if services are already stopped
