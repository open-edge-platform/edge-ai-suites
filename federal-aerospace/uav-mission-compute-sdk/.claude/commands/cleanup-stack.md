<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# cleanup-stack

Stop and clean up running Docker resources for the UAV stack.

## Implementation

```bash
#!/bin/bash
set -e

echo "Cleaning up UAV simulation stack..."

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

# Stop sample apps + helpers first (they hold the shared network open)
if [ -f sample-apps/docker-compose.yml ]; then
    echo "Stopping sample apps + helpers..."
    docker compose --env-file .env -f sample-apps/docker-compose.yml down --remove-orphans 2>/dev/null || true
fi

# Stop core infra (both camera profiles)
if [ -f docker-compose.yml ]; then
    echo "Stopping core infra..."
    docker compose -f docker-compose.yml --profile sim-camera --profile usb-camera down --remove-orphans
fi

echo "Running Makefile cleanup target..."
make clean

echo "Cleanup complete!"
echo ""
echo "For deeper cleanup (compose volumes + all unused images), run: make clean-all"
echo "To start fresh, run: /start-stack"
```

## Usage

```bash
/cleanup-stack
```

## Notes

- Stops sample-apps layer first, then core infra
- Uses `make clean` by default (safe cleanup)
- Use `make clean-all` when you explicitly want to remove compose volumes + all unused images
- Safe to run even if services are already stopped
