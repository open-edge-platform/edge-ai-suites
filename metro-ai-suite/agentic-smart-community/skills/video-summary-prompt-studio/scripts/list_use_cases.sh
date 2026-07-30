#!/usr/bin/env bash
# List registered use-case keys from the MCP server's booted config.
#
# Usage: list_use_cases.sh [config-file]
#
# CFG must be the file the MCP server booted from (its --config argument) —
# persist=true writes back to THAT file. By default that is the config.yaml in
# the server's data dir ($SMARTBUILDING_DATA_DIR or ~/.mcp-smartbuilding), not
# any config.yaml in your CWD.
set -euo pipefail

if [[ $# -ge 1 ]]; then
  CFG="$1"
else
  CFG="${SMARTBUILDING_DATA_DIR:-$HOME/.mcp-smartbuilding}/config.yaml"
fi

[[ -f "$CFG" ]] || { echo "config not found: $CFG (pass the server's booted config path explicitly)" >&2; exit 1; }

if command -v yq >/dev/null 2>&1; then
  yq '.use_case_dict | keys' "$CFG"
else
  # yq-free fallback: print the 2-space-indented keys directly under
  # `use_case_dict:` (use case ids), stopping at the next top-level key.
  awk '
    /^use_case_dict:/ { inblk=1; next }
    inblk && /^[^[:space:]#]/ { inblk=0 }
    inblk && /^  [A-Za-z0-9_]+:/ { sub(/:.*/, ""); gsub(/ /, ""); print }
  ' "$CFG"
fi
