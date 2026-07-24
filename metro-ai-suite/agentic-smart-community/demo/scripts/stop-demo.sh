#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Stop the demo started by demo/scripts/start-demo.sh: stop the MCP server,
# then stop the demo RTSP streams.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

bash "$REPO_DIR/scripts/mcp-server/stop.sh" || true
echo "stopping demo RTSP streams…"
bash "$REPO_DIR/demo/videos/stop_streams.sh" || true
