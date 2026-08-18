#!/usr/bin/env bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Stop the demo started by demo/quick-start/start-demo.sh: stop the demo RTSP
# streams, then stop the app tier (MCP server + analytics + multilevel) while
# leaving vllm-ipex-serving running so its multi-minute recompile is not repaid.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "stopping demo RTSP streams…"
bash "$REPO_DIR/demo/videos/stop_streams.sh" || true

echo "stopping app tier (keeping vllm-ipex-serving warm)…"
bash "$REPO_DIR/setup_docker.sh" --light-down || true
