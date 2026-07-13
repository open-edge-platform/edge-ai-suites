#!/bin/bash
# setup-openclaw-workspace.sh
# Copies workspace configuration files to ~/.openclaw/workspace/
# Run this script AFTER installing and configuring OpenClaw,
# but BEFORE running 'openclaw chat' or 'openclaw dashboard'.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_SRC="${SCRIPT_DIR}/workspace"
OPENCLAW_WORKSPACE="${HOME}/.openclaw/workspace"

echo "=== OpenClaw Workspace Setup ==="
echo "Source:      ${WORKSPACE_SRC}"
echo "Destination: ${OPENCLAW_WORKSPACE}"
echo ""

# Create workspace directories
echo "[1/4] Creating workspace directories..."
mkdir -p "${OPENCLAW_WORKSPACE}"
mkdir -p "${OPENCLAW_WORKSPACE}/skills/classroom_qa"

# Create incoming data directory for Smart Classroom and copy sample data
echo "[2/4] Creating Smart Classroom data directory and copying sample data..."
mkdir -p "${OPENCLAW_WORKSPACE}/smart_classroom_incoming"
cp -r "${WORKSPACE_SRC}/smart_classroom_incoming/." "${OPENCLAW_WORKSPACE}/smart_classroom_incoming/"

# Copy SOUL.md and AGENTS.md to workspace root
echo "[3/4] Copying SOUL.md and AGENTS.md to workspace..."
cp "${WORKSPACE_SRC}/SOUL.md" "${OPENCLAW_WORKSPACE}/SOUL.md"
cp "${WORKSPACE_SRC}/AGENTS.md" "${OPENCLAW_WORKSPACE}/AGENTS.md"

# Copy SKILL.md to skills/classroom_qa/
echo "[4/4] Copying SKILL.md to skills/classroom_qa/..."
cp "${WORKSPACE_SRC}/skills/classroom_qa/SKILL.md" "${OPENCLAW_WORKSPACE}/skills/classroom_qa/SKILL.md"

echo ""
echo "=== Workspace setup complete ==="
echo ""
echo "Files deployed:"
echo "  ${OPENCLAW_WORKSPACE}/SOUL.md"
echo "  ${OPENCLAW_WORKSPACE}/AGENTS.md"
echo "  ${OPENCLAW_WORKSPACE}/skills/classroom_qa/SKILL.md"
echo ""
echo "Data directory created:"
echo "  ${OPENCLAW_WORKSPACE}/smart_classroom_incoming"
echo ""
echo "You can now run: openclaw chat  OR  openclaw dashboard"
