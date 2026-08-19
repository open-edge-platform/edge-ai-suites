#!/bin/bash

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -e

# Get absolute path to script directory (works from any location)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Workspace is the directory where you run 'claude' command
# Default to parent directory of poc-space if not specified
if [ -z "$1" ]; then
    # Auto-detect workspace: go up from mcp-server to find parent
    WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    WORKSPACE_DIR="$(cd "$1" && pwd)"
fi

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${BLUE}i${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
error()   { echo -e "${RED}✗${NC} $1"; exit 1; }

echo "Setting up FedAero UAV SDK MCP server"
echo "Script location: $SCRIPT_DIR"
echo "Workspace: $WORKSPACE_DIR"
echo ""

# ---------------------------------------------------------------------------
# Ensure uv is available
# ---------------------------------------------------------------------------
ensure_uv() {
    if command -v uv &>/dev/null; then
        return 0
    fi

    info "uv not found — installing..."

    if command -v curl &>/dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    elif command -v wget &>/dev/null; then
        wget -qO- https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    else
        error "curl or wget is required to install uv. Install manually: https://docs.astral.sh/uv/getting-started/installation/"
    fi

    command -v uv &>/dev/null || error "uv installed but not found in PATH. Open a new shell and re-run."
    success "uv $(uv --version) installed"
}

ensure_uv

# ---------------------------------------------------------------------------
# Clone dependency repositories
# ---------------------------------------------------------------------------
cd "$WORKSPACE_DIR"

if [ ! -d "dlstreamer" ]; then
    info "Cloning dlstreamer..."
    git clone https://github.com/dlstreamer/dlstreamer.git
    success "dlstreamer cloned"
else
    success "dlstreamer"
fi

if [ ! -d "anomalib" ]; then
    info "Cloning anomalib..."
    git clone https://github.com/openvinotoolkit/anomalib.git
    success "anomalib cloned"
else
    success "anomalib"
fi

if [ ! -d "edge-ai-suites" ]; then
    info "Cloning edge-ai-suites..."
    git clone https://github.com/open-edge-platform/edge-ai-suites.git
    success "edge-ai-suites cloned"
else
    success "edge-ai-suites"
fi

echo ""

# ---------------------------------------------------------------------------
# Install dependencies with uv (no venv needed)
# ---------------------------------------------------------------------------
info "Installing dependencies with uv..."
cd "$SCRIPT_DIR"
uv pip install --quiet -e . 2>&1 | grep -v "already satisfied" || true
success "Dependencies installed"

# ---------------------------------------------------------------------------
# Write .mcp.json with uv run command
# ---------------------------------------------------------------------------
UV_BIN="$(command -v uv)"

cat > "$WORKSPACE_DIR/.mcp.json" << EOF
{
  "mcpServers": {
    "edge-ai-skills": {
      "type": "stdio",
      "command": "$UV_BIN",
      "args": ["--directory", "$SCRIPT_DIR", "run", "server.py"],
      "env": {
        "WORKSPACE_DIR": "$WORKSPACE_DIR"
      }
    }
  }
}
EOF
success ".mcp.json written to $WORKSPACE_DIR/.mcp.json"

# ---------------------------------------------------------------------------
# Verify tool discovery
# ---------------------------------------------------------------------------
echo ""
info "Discovering tools from tool_configs/..."
cd "$SCRIPT_DIR"
tool_count=$(uv run python -c "
import yaml
from pathlib import Path
count = 0
for config_file in Path('$SCRIPT_DIR/tool_configs').glob('*.yaml'):
    data = yaml.safe_load(config_file.read_text())
    n = len(data.get('tools', []))
    print(f'  {config_file.stem}: {n} tools')
    count += n
print(f'\n  Total: {count} tools')
" 2>/dev/null)
echo "$tool_count"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Ready"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo " Usage: run 'claude' from $WORKSPACE_DIR"
echo " Claude Code will auto-discover all tools via MCP."
echo ""
echo " Run setup from anywhere:"
echo "   $SCRIPT_DIR/setup.sh [workspace_dir]"
echo ""
echo " Test manually:"
echo "   cd $SCRIPT_DIR && uv run server.py"
echo ""
